import os
import re
import glob
from scripts.config import PROJECT_CONFIG


def read_rtl(rtl_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not rtl_dir or not os.path.exists(rtl_dir):
        return content

    for root, _, files in os.walk(rtl_dir):
        for file in files:
            # RTLcan be Verilog or SystemVerilog
            if file.endswith(".v") or file.endswith(".sv"): 
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content += f"\n--- RTL FILE: {file} ---\n{f.read()}\n"
                except Exception as e:
                    pass
    return content


def read_env(tb_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not tb_dir or not os.path.exists(tb_dir):
        return content

    for root, _, files in os.walk(tb_dir):
        for file in files:
            # Files can be Verilog or SystemVerilog
            if file.endswith(".sv") or file.endswith(".v"):
                if "DEBUG" in file or "ai_proposed" in file or "unknown_file" in file:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content += f"\n--- TB FILE: {file} ---\n{f.read()}\n"
                except Exception as e:
                    pass
    return content


def read_specific_files(target_files_str: str, search_dirs: list) -> str:
    """Reads only the files requested by the Generator from the given directories."""
    target_files = [f.strip() for f in target_files_str.split(',')]
    content = ""
    
    for target_file in target_files:
        if not target_file:
            continue
            
        file_found = False
        for directory in search_dirs:
            if not directory or not os.path.exists(directory): 
                continue
                
            for root, _, files in os.walk(directory):
                if target_file in files:
                    file_path = os.path.join(root, target_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content += f"\n--- TARGET FILE: {target_file} ---\n{f.read()}\n"
                            file_found = True
                        break
                    except Exception as e:
                        pass
            if file_found: 
                break
                
        if not file_found:
            content += f"\n--- TARGET FILE: {target_file} (WARNING: NOT FOUND ON DISK) ---\n"
            
    return content


def read_run_script(bat_file_path: str) -> str:
    """Reads the Vivado/XSim run script."""
    if not bat_file_path or not os.path.exists(bat_file_path):
        return "Warning: Run script not found."
    try:
        with open(bat_file_path, "r", encoding="utf-8") as f:
            script_name = os.path.basename(bat_file_path)
            return f"\n--- RUN SCRIPT: {script_name} ---\n{f.read()}\n"
    except Exception as e:
        return f"Warning: Could not read run script: {e}"
    

def read_simulation_log(log_path: str) -> str:
    """Builds a compact summary from the available XSim simulation logs."""
    # check first log file
    log_dir = os.path.dirname(os.path.abspath(log_path)) if log_path else ""
    
    # check in config file
    per_test_logs = sorted(glob.glob(os.path.join(log_dir, "xsim_test*.log")))
    
    if not per_test_logs:
        run_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))
        per_test_logs = sorted(glob.glob(os.path.join(run_dir, "xsim_test*.log")))

    # check xsim_logs
    if not per_test_logs:
        if log_path and os.path.exists(log_path):
            per_test_logs = [log_path]
        else:
            return "No simulation logs found."

    summary_parts = []

    for log_file in per_test_logs:
        test_name = os.path.basename(log_file).replace(".log", "")
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue

        important_lines = []
        for line in lines:
            line_s = line.strip()
            if any(tag in line_s for tag in [
                "UVM_ERROR", "UVM_FATAL", "UVM_WARNING",
                "Running test", "INVTST", "BDTYP",
                "MON_SPECIAL_EVENT", "MY_COVERAGE"
            ]):
                important_lines.append(line_s)

        # counting appeared errors
        fatals   = sum(1 for l in lines if "UVM_FATAL"   in l and "Report counts" not in l)
        errors   = sum(1 for l in lines if "UVM_ERROR"   in l and "Report counts" not in l)
        warnings = sum(1 for l in lines if "UVM_WARNING" in l and "Report counts" not in l)
        status   = "FAILED" if (fatals > 0 or errors > 0) else "PASSED"

        part  = f"[{test_name}] STATUS={status} | Errors={errors} Fatals={fatals} Warnings={warnings}\n"
        part += "\n".join(f"  >> {l}" for l in important_lines[:20])
        summary_parts.append(part)

    return "\n\n".join(summary_parts)
    

def extract_code(original_code: str) -> dict:
    """Extracts generated code blocks and maps them to target file names."""
    extracted_files = {}
    # Search in every code block
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", original_code, re.DOTALL)
    
    if not blocks:
        # Not found markdown
        return {"unknown_file.sv": original_code}

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
            
        first_line = lines[0].strip()
        # // FILE: file_named.ext"
        file_match = re.search(r'(?:\/\/|::|#|REM)\s*FILE:\s*([a-zA-Z0-9_.]+\.[a-zA-Z0-9]+)',first_line,re.IGNORECASE)
        
        if file_match:
            filename = file_match.group(1).strip()
            extracted_files[filename] = block.strip()
        else:
            if any(line.strip().startswith("@echo") for line in lines):
                temp_name = f"extracted_temp_{len(extracted_files)}.bat"
            else:
                temp_name = f"extracted_temp_{len(extracted_files)}.sv"
            extracted_files[temp_name] = block.strip()
            
    return extracted_files


def save_code(original_code: str, file_path:str) ->str:
    # save code on disk
    with open(file_path, 'w') as file:
        file.write(original_code)
    print(f"\nSystemVerilog code saved in {file_path}\n")


def find_file_in_project(file_name: str) -> str:
    """Searches for a file in the configured RTL/TB/run-script directories."""
    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))

    search_dirs = [
        PROJECT_CONFIG.get("tb_dir", ""),
        PROJECT_CONFIG.get("rtl_dir", ""),
        bat_dir,
    ]

    for directory in search_dirs:
        if not directory or not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if file_name in files:
                return os.path.join(root, file_name)

    return ""


def read_source_context(file_path: str, line_no: int, radius: int = 4) -> str:
    """Reads a small source-code window around the error line."""

    if not file_path or not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return ""

    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)

    context_lines = []
    for idx in range(start, end + 1):
        marker = ">>" if idx == line_no else "  "
        code_line = lines[idx - 1].rstrip()
        context_lines.append(f"{marker} {idx:4d}: {code_line}")

    return "\n".join(context_lines)


def build_source_error_context(error_text: str) -> tuple[str, str]:
    """
    Builds source-code context for the files and lines mentioned in Vivado errors.
    Returns: markdown/code text for UI and separated target files
    """

    locations = extract_error_file_locations(error_text)

    if not locations:
        return "", ""

    sections = []
    target_files = []

    for loc in locations:
        file_name = loc["file_name"]
        line_no = loc["line"]

        # ignore top.sv if the error is "ignored due to previous errors"
        if file_name == "top.sv" and "ignored due to previous errors" in error_text.lower():
            continue

        file_path = find_file_in_project(file_name)
        source_context = read_source_context(file_path, line_no)
        target_files.append(file_name)

        if source_context:
            sections.append(
                f"File: {file_name}, line {line_no}\n"
                f"{source_context}"
            )
        else:
            sections.append(
                f"File: {file_name}, line {line_no}\n"
                "Source context could not be read from disk."
            )

    target_files = list(dict.fromkeys(target_files))
    return "\n\n".join(sections), ", ".join(target_files)


def extract_error_file_locations(error_text: str) -> list[dict]:
    """
    Extracts file and line references from Vivado/XSim errors.
    """
    locations = []
    
    pattern = re.compile(
        r"\[([^\[\]]+\.(?:sv|v|svh|vh|bat)):(\d+)\]",
        re.IGNORECASE,
    )

    for match in pattern.finditer(error_text or ""):
        raw_path = match.group(1).replace("\\", "/")
        line_no = int(match.group(2))
        file_name = os.path.basename(raw_path)

        locations.append(
            {
                "raw_path": raw_path,
                "file_name": file_name,
                "line": line_no,
            }
        )

    # remove duplicates, keep order
    unique = []
    seen = set()

    for loc in locations:
        key = (loc["file_name"], loc["line"])
        if key not in seen:
            unique.append(loc)
            seen.add(key)

    return unique

# used for prompts
def safe_format(template: str, **kwargs):
    # escape all {}
    template = template.replace("{", "{{").replace("}", "}}")
    # correct variable
    for key in kwargs:
        template = template.replace("{{" + key + "}}", "{" + key + "}")

    return template.format(**kwargs)
