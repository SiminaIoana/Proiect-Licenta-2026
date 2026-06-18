import os
import re
from state import AgentState
from config import PROJECT_CONFIG
from utils_files.file_ops import extract_code

"""Code injection and rollback utilities."""

def inject_generated_code(state: AgentState):
    """ Extracts generated code blocks and injects them into the matching project files."""
    generated_code = state.get("generated_code", "")
    extracted_files = extract_code(generated_code)

    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")
    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))

    for filename, file_content in extracted_files.items():
        if not filename or "unknown_file" in filename:
            continue

        file_path_to_save = find_file_in_dirs(filename, [tb_dir, rtl_dir, bat_dir])

        if file_path_to_save:
            apply_smart_injection(file_path_to_save, file_content)
        else:
            print(f"[ERROR] Target file {filename} not found on disk for injection.")


def find_file_in_dirs(filename: str, dirs: list):
    """ search for files and provided directory"""
    for directory in dirs:
        if not directory or not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if filename in files:
                return os.path.join(root, filename)

    return None


def replace_sv_coverpoint(file_content: str, coverpoint_name: str, new_coverpoint_code: str) -> str:
    """ Replaces a named SystemVerilog coverpoint block:
    cp_name: coverpoint ... {
    }
    It uses brace matching so it can safely replace the full coverpoint body.
    """
    start_pattern = re.compile(
        rf"\b{re.escape(coverpoint_name)}\s*:\s*coverpoint\b",
        flags=re.MULTILINE
    )

    match = start_pattern.search(file_content)

    if not match:
        raise ValueError(f"Could not find coverpoint '{coverpoint_name}' for replacement.")

    start_idx = match.start()

    brace_start = file_content.find("{", match.end())
    if brace_start == -1:
        raise ValueError(f"Coverpoint '{coverpoint_name}' has no opening brace.")

    depth = 0
    end_idx = None

    for i in range(brace_start, len(file_content)):
        char = file_content[i]

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                end_idx = i + 1

                while end_idx < len(file_content) and file_content[end_idx].isspace():
                    end_idx += 1

                if end_idx < len(file_content) and file_content[end_idx] == ";":
                    end_idx += 1

                break

    if end_idx is None:
        raise ValueError(f"Could not find end of coverpoint '{coverpoint_name}'.")

    return (
        file_content[:start_idx]
        + new_coverpoint_code.strip()
        + file_content[end_idx:]
    )


def create_rollback_checkpoint(state: AgentState):
    """Checkpoint for the initial code"""
    generated_code = state.get("generated_code", "")
    extracted_files = extract_code(generated_code)
    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))
    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")

    rollback_files = {}

    for filename in extracted_files.keys():
        if not filename or "unknown_file" in filename:
            continue

        file_path = find_file_in_dirs(filename, [tb_dir, rtl_dir, bat_dir])

        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                rollback_files[file_path] = f.read()

    return rollback_files


def restore_rollback_files(state: AgentState):
    """ Restores the files saved in the rollback checkpoint."""
    rollback_files = state.get("rollback_files", {})
    if not rollback_files:
        return {
        "ui_message": "Rollback failed: no checkpoint was found.",
        "rollback_files": {}
        }
    for file_path, old_content in rollback_files.items():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(old_content)

    return {
        "rollback_files": {},
        "ui_message": "Rollback completed. Previous code version was restored."
    }


def apply_smart_injection(file_path: str, new_content: str):
    """ Applies generated code to a target file.
    BAT files are updated near the coverage-report section, while SystemVerilog
    files support class, covergroup and coverpoint replacement markers.
    If no replacement marker is found, the new code is appended.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        old_content = f.read()

    filename = os.path.basename(file_path).lower()

    replace_class_name = None
    replace_coverpoint_name = None
    replace_covergroup_name = None

    # Remove injector marker lines and detect replacement markers
    lines = new_content.strip().splitlines()
    clean_lines = []

    for line in lines:
        if "FILE:" in line:
            continue

        class_match = re.match(
            r"\s*//\s*REPLACE_CLASS:\s*([a-zA-Z_][a-zA-Z0-9_$]*)\s*;?\s*$",
            line
        )
        if class_match:
            replace_class_name = class_match.group(1)
            continue

        coverpoint_match = re.match(
            r"\s*//\s*REPLACE_COVERPOINT:\s*([a-zA-Z_][a-zA-Z0-9_$]*)\s*;?\s*$",
            line
        )
        if coverpoint_match:
            replace_coverpoint_name = coverpoint_match.group(1)
            continue

        covergroup_match = re.match(
            r"\s*//\s*REPLACE_COVERGROUP:\s*([a-zA-Z_][a-zA-Z0-9_$]*)\s*;?\s*$",
            line
        )
        if covergroup_match:
            replace_covergroup_name = covergroup_match.group(1)
            continue

        clean_lines.append(line)

    new_content = "\n".join(clean_lines).strip()

    if not new_content.strip():
        print(f"[INJECTOR] Empty content, skipping injection for {file_path}")
        return

    # Special handling for MakeSVfile.bat
    if filename.endswith(".bat"):
        marker = ":: functional coverage report"

        if new_content in old_content:
            print(f"[INJECTOR] BAT content already exists in {file_path}")
            return

        if marker in old_content:
            updated_content = old_content.replace(
                marker,
                new_content + "\n\n" + marker,
                1
            )
            print(f"[INJECTOR] Inserted BAT commands before coverage report in {file_path}")
        else:
            updated_content = old_content + "\n\n" + new_content
            print(f"[INJECTOR] Appended BAT commands to {file_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        return

    # SystemVerilog handling
    if filename.endswith(".sv"):

        if new_content in old_content:
            print(f"[INJECTOR] SV content already exists in {file_path}")
            return
        
        # REPLACE_CLASS
        if replace_class_name:
            class_pattern = re.compile(
                r"(^[ \t]*(?:virtual\s+)?class\s+"
                + re.escape(replace_class_name)
                + r"\b.*?^[ \t]*endclass\b[^\n]*(?:\n|$))",
                re.MULTILINE | re.DOTALL
            )

            updated_content, replacements = class_pattern.subn(
                new_content.rstrip() + "\n",
                old_content,
                count=1
            )

            if replacements:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

                print(f"[INJECTOR] Replaced class {replace_class_name} in {file_path}")
                return

            raise ValueError(
                f"[INJECTOR ERROR] Class {replace_class_name} not found in {file_path}. "
                "Replacement marker was present, so append is not allowed."
            )

        # REPLACE_COVERGROUP
        if replace_covergroup_name:
            covergroup_pattern = re.compile(
                r"(^[ \t]*covergroup\s+"
                + re.escape(replace_covergroup_name)
                + r"\b.*?^[ \t]*endgroup\b[^\n]*(?:\n|$))",
                re.MULTILINE | re.DOTALL
            )

            updated_content, replacements = covergroup_pattern.subn(
                new_content.rstrip() + "\n",
                old_content,
                count=1
            )

            if replacements:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

                print(f"[INJECTOR] Replaced covergroup {replace_covergroup_name} in {file_path}")
                return

            raise ValueError(
                f"[INJECTOR ERROR] Covergroup {replace_covergroup_name} not found in {file_path}. "
                "Replacement marker was present, so append is not allowed."
            )

        # REPLACE_COVERPOINT
        if replace_coverpoint_name:
            updated_content = replace_sv_coverpoint(
                old_content,
                replace_coverpoint_name,
                new_content
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            print(f"[INJECTOR] Replaced coverpoint {replace_coverpoint_name} in {file_path}")
            return

        # Default APPEND behavior for SV files
        if "`endif" in old_content:
            idx = old_content.rfind("`endif")
            updated_content = (
                old_content[:idx].rstrip()
                + "\n\n"
                + new_content
                + "\n\n"
                + old_content[idx:]
            )
            print(f"[INJECTOR] Inserted SV code before `endif in {file_path}")
        else:
            updated_content = old_content.rstrip() + "\n\n" + new_content + "\n"
            print(f"[INJECTOR] Appended SV code to {file_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        return

    # Default behavior for non-SV / non-BAT files
    updated_content = old_content + "\n\n" + new_content

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"[INJECTOR] Appended new code to {file_path}")