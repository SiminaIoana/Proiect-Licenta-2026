import os
import re
import csv
import datetime
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

# ==============================================================
# ------ FUNCTION FOR EXTRACTING HOLES FROM FCOV -------
# ==============================================================
def extract_coverage_holes(path: str)->str:
    # REGEX 
    var_pattern = re.compile(r'Variable\s*[:,\s]+([^\n,]+)')
    uncovered_header_pattern = re.compile(r'(Auto|User)?\s*Uncovered bins', re.IGNORECASE)
    stop_pattern = re.compile(r'(Covered bins|Summary)', re.IGNORECASE)

    holes = {}
    current_var = None
    in_uncovered_section = False

    try:
        with open(path,'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if not line: 
                    continue

                var_match = var_pattern.search(line)
                if var_match:
                    current_var = var_match.group(1)
                    if current_var not in holes:
                        holes[current_var] = []
                    in_uncovered_section = False
                    continue

                if uncovered_header_pattern.search(line):
                    in_uncovered_section = True
                    continue

                if stop_pattern.search(line):
                    in_uncovered_section = False
                    continue

                if in_uncovered_section:
                    if "Hit Count" in line or "Name" in line or "AtLeast" in line:
                        continue

                    parts = [p.strip() for p in line.split(',')]
                    parts = [p for p in parts if p] 

                    if len(parts) >= 2: 
                        bin_name = ", ".join(parts[:-2]) if len(parts) > 2 else parts[0]
                        
                        if current_var is not None:
                            clean_var = current_var.strip()
                            holes[clean_var].append(bin_name)

        if not holes or all(len(v) == 0 for v in holes.values()):
            return "No obvious coverage holes found in text report."
            
        formatted_holes = []
        for var, missed in holes.items():
            if missed:
                unique_missed = list(dict.fromkeys(missed))
                formatted_holes.append(f"- Variable '{var}' missed bins: {', '.join(unique_missed)}")                
        return "\n".join(formatted_holes)
                
    except FileNotFoundError:
        print(f"[Extract holes] PATH NOT FOUND: {path}")
        return "ERROR: file_not_found" 
        
    except Exception as e:
        print(f"[Extract holes] ERROR while parsing: {str(e)}")
        return f"ERROR: {str(e)}"
            

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
# ------- FUNCTION FOR READING RUN SCRIPT (.bat / .tcl) ------
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
    if not os.path.exists(log_path):
        return "Warning: xsim.log not found."

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        target_keywords = ["UVM_WARNING", "UVM_ERROR", "UVM_FATAL", "MON_COVERAGE_RISK", "MON_SPECIAL_EVENT"]
        relevant_logs = []

        for line in lines:
            if any(keyword in line for keyword in target_keywords):
                relevant_logs.append(line.strip())

        summary_lines = lines[-100:]
        
        output = "--- RELEVANT SIMULATION EVENTS (UVM) ---\n"
        if relevant_logs:
            output += "\n".join(relevant_logs) + "\n\n"
        else:
            output += "No specific UVM warnings or errors detected during simulation.\n\n"
            
        output += "--- SIMULATION END SUMMARY ---\n"
        output += "".join(summary_lines)

        return output

    except Exception as e:
        return f"Warning: Could not read xsim.log: {e}"
# ============================================================
# ------- FUNCTION FOR QUERYING LTM MEMORY --------
# ============================================================
def query_analyzer_memory(hole_description: str,action_plan, success_code) -> str:

    exp_dir = os.path.join("..", "results", "LTM_analyzer")
    os.makedirs(exp_dir, exist_ok=True)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(exp_dir, f"coverage_fix_{timestamp}.txt")

    memory_entry = (
        f"COVERAGE_HOLE_DESCRIPTION:\n{hole_description}\n\n"
        f"ANALYZER_PROPOSED_PLAN:\n{action_plan}\n\n"
        f"VERIFIED_STIMULUS_CODE:\n{success_code}\n"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(memory_entry)
    
    print(f"[ANALYZER LTM]: Good experience saved in:{file_path}")


#create or load index
def get_index(data_dir: str, storage_dir: str, index_name: str):
    """
    Verify the directories, read documents and create the index. If the index exist, it will be loaded
    """
    if not os.path.exists(data_dir) or not os.listdir(data_dir):
        print(f"[INDEXER INFO]: Source folder for '{index_name}' is empty or missing.")
        return None
    
    try:
        if os.path.exists(storage_dir) and os.listdir(storage_dir):
            #print(f"[INDEXER]: Loading existing '{index_name}' from storage...")
            storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
            index = load_index_from_storage(storage_context)
            #print(f"[INDEXER]: '{index_name}' loaded successfully!")
            return index
    except Exception as e:
        print(f"[INDEXER WARNING]: Failed to load '{index_name}' cache: {e}")

    try:
        #print(f"[INDEXER]: Building new index for '{index_name}' from '{data_dir}'...")
        documents = SimpleDirectoryReader(input_dir=data_dir).load_data()
        index = VectorStoreIndex.from_documents(documents)

        # Save index for future runs
        os.makedirs(storage_dir, exist_ok=True)
        index.storage_context.persist(persist_dir=storage_dir)
        #print(f"[INDEXER]: '{index_name}' saved to storage.")
        return index
    except Exception as e:
        print(f"[INDEXER ERROR]: Critical failure creating '{index_name}': {e}")
        return None


# function for extract SV code
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
        
        # Caută comentariul "// FILE: nume_fisier.ext"
        file_match = re.search(r'//\s*FILE:\s*([a-zA-Z0-9_.]+\.[a-zA-Z0-9]+)', first_line, re.IGNORECASE)
        
        if file_match:
            filename = file_match.group(1).strip()
            # Salvăm tot blocul (inclusiv prima linie, dacă vrei s-o păstrezi, sau o poți exclude)
            extracted_files[filename] = block.strip()
        else:
            # Dacă uită să pună comentariul, îi dăm un nume temporar
            temp_name = f"extracted_temp_{len(extracted_files)}.sv"
            extracted_files[temp_name] = block.strip()
            
    return extracted_files
    
# function for saving the code on disk
def save_code(original_code: str, file_path:str) ->str:
    with open(file_path, 'w') as file:
        file.write(original_code)
    print(f"\nSystemVerilog code saved in {file_path}\n")

# function for saving metrics in csv
def save_to_csv(data_row , path):
    file_exists = os.path.exists(path)
    with open(path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Iteration", "Status", "Time_Execution_sec", "Coverage", "Error_type", "Tokens_Used"])
        writer.writerow(data_row)

#function for saving error status in txt
def save_to_file(content, path):
    with open(path, "a", encoding="utf-8") as file:
        file.write(content + "\n" + "="*50 + "\n\n")

import re

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