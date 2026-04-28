
from state import AgentState
from utils_files.file_ops import extract_code
from config import PROJECT_CONFIG
import os

def inject_generated_code(state: AgentState):
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
    for directory in dirs:
        if not directory or not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if filename in files:
                return os.path.join(root, filename)

    return None


def create_rollback_checkpoint(state: AgentState):
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
    with open(file_path, "r", encoding="utf-8") as f:
        old_content = f.read()

    filename = os.path.basename(file_path).lower()

    # remove FILE marker line
    lines = new_content.strip().splitlines()
    clean_lines=[]
    for line in lines:
        if "FILE:" in line:
            continue
        clean_lines.append(line)
    new_content = "\n".join(clean_lines).strip()

    if not new_content.strip():
        print(f"[INJECTOR] Empty content, skipping injection for {file_path}")
        return

    # special handling for MakeSVfile.bat
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
    
    if filename.endswith(".sv"):

        if new_content in old_content:
            print(f"[INJECTOR] SV content already exists in {file_path}")
            return

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

    # default behavior for files
    updated_content = old_content + "\n\n" + new_content

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"[INJECTOR] Appended new code to {file_path}")