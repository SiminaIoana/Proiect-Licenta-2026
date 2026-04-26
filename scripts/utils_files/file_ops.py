import os
import re
import glob
from scripts.config import PROJECT_CONFIG
    
# ============================================================
# ------- FUNCTION FOR READING RTL FILES ------
# ============================================================
def read_rtl(rtl_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not rtl_dir or not os.path.exists(rtl_dir):
        return content

    for root, _, files in os.walk(rtl_dir):
        for file in files:
            # RTL-ul poate fi si Verilog si SystemVerilog
            if file.endswith(".v") or file.endswith(".sv"): 
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content += f"\n--- RTL FILE: {file} ---\n{f.read()}\n"
                except Exception as e:
                    pass
    return content


# ============================================================
# ------- FUNCTION FOR READING TESTBENCH FILES ------
# ============================================================
def read_env(tb_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not tb_dir or not os.path.exists(tb_dir):
        return content

    for root, _, files in os.walk(tb_dir):
        for file in files:
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



# ============================================================
# ------- FUNCTION FOR READING SPECIFIC TARGET FILES ---------
# ============================================================
def read_specific_files(target_files_str: str, search_dirs: list) -> str:
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

# ============================================================
# ------- FUNCTION FOR READING RUN SCRIPT ------
# ============================================================
def read_run_script(bat_file_path: str) -> str:
    if not bat_file_path or not os.path.exists(bat_file_path):
        return "Warning: Run script not found."
    try:
        with open(bat_file_path, "r", encoding="utf-8") as f:
            script_name = os.path.basename(bat_file_path)
            return f"\n--- RUN SCRIPT: {script_name} ---\n{f.read()}\n"
    except Exception as e:
        return f"Warning: Could not read run script: {e}"
    

# ================================================
# ------- FUNCTION FOR READING XSIM.LOG ------
# ================================================
def read_simulation_log(log_path: str) -> str:

    # Încearcă mai întâi folderul din log_path
    log_dir = os.path.dirname(os.path.abspath(log_path)) if log_path else ""
    
    # Dacă nu găsește, încearcă directorul de rulare din config
    per_test_logs = sorted(glob.glob(os.path.join(log_dir, "xsim_test*.log")))
    
    if not per_test_logs:
        run_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))
        per_test_logs = sorted(glob.glob(os.path.join(run_dir, "xsim_test*.log")))

    # Fallback final pe xsim.log clasic
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

        # Numărăm din Report Summary (ultima apariție), nu din tot fișierul
        # altfel numărăm fiecare linie de log individual
        fatals   = sum(1 for l in lines if "UVM_FATAL"   in l and "Report counts" not in l)
        errors   = sum(1 for l in lines if "UVM_ERROR"   in l and "Report counts" not in l)
        warnings = sum(1 for l in lines if "UVM_WARNING" in l and "Report counts" not in l)
        status   = "FAILED" if (fatals > 0 or errors > 0) else "PASSED"

        part  = f"[{test_name}] STATUS={status} | Errors={errors} Fatals={fatals} Warnings={warnings}\n"
        part += "\n".join(f"  >> {l}" for l in important_lines[:20])
        summary_parts.append(part)

    return "\n\n".join(summary_parts)
    

# ==============================================================
# ------ FUNCTION FOR EXTRACTING CODE------
# ==============================================================
def extract_code(original_code: str) -> dict:
    extracted_files = {}
    
    # Caută toate blocurile de cod (indiferent dacă sunt systemverilog, tcl sau goale)
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", original_code, re.DOTALL)
    
    if not blocks:
        # Dacă nu găsește markdown, returnează tot codul ca un fișier generic
        return {"unknown_file.sv": original_code}

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
            
        first_line = lines[0].strip()
        
        # // FILE: nume_fisier.ext"
        file_match = re.search(r'//\s*FILE:\s*([a-zA-Z0-9_.]+\.[a-zA-Z0-9]+)', first_line, re.IGNORECASE)
        
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



# function for saving the code on disk
def save_code(original_code: str, file_path:str) ->str:
    with open(file_path, 'w') as file:
        file.write(original_code)
    print(f"\nSystemVerilog code saved in {file_path}\n")


def apply_smart_injection(file_path: str, generated_code: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r'<<<< SEARCH\n(.*?)\n==== REPLACE\n(.*?)\n>>>>'
        matches = re.findall(pattern, generated_code, re.DOTALL)
        
        if matches:
            for search_text, replace_text in matches:
                if search_text in content:
                    content = content.replace(search_text, replace_text)
                    print(f"[INJECTOR] Replaced specific lines in {file_path}")
                else:
                    print(f"[WARNING] Could not find the exact lines to replace in {file_path}")
        
        else:
            idx = content.rfind("`endif")
            if idx != -1:
                content = content[:idx] + "\n" + generated_code + "\n" + content[idx:]
            else:
                content = content + "\n\n" + generated_code + "\n"
            print(f"[INJECTOR] Appended new classes to {file_path}")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    except Exception as e:
        print(f"[INJECTOR ERROR] Failed to process {file_path}: {e}")