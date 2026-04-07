from llama_index.core import Settings
from state import AgentState
import datetime
import tiktoken
from config import PROJECT_CONFIG
import os
import re
from utils import get_index

# ==============================================================
# ------ FUNCTION FOR EXTRACTING HOLES FROM FCOV -------
# ==============================================================
def extract_coverage_holes(path: str)->str:
    # parse txt raport and return a list with uncovered bins

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
            return "".join(lines[-600:])
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


# ==================================
# ------- ANALYZER NODE ------
# ==================================
def analyzer_node(state: AgentState):

    mode = state.get("analyzer_mode","")
    print(f"\n[ANALYZER]: Executing mode -> [{mode}]")

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")
    
    #====================================
    # ---- BUILDING HOLES LIST ----
    #====================================
    if mode == "build_holes_list":
        fcov_path = state.get("fcov_report_path", "")
    
        # ---- PARSE FCOV REPORT ----
        raw_holes = extract_coverage_holes(fcov_path)
        '''
        print("\n--- DEBUG RAW HOLES ---")
        print(raw_holes)
        print("-----------------------\n")
        '''
        if "No obvious coverage holes" in raw_holes or raw_holes.strip() == "":
            print("[ANALYZER]: Target reached! No holes found.")
            return {
                "coverage_holes": raw_holes,
                "holes_list": [],
                "status": "ANALYSIS_COMPLETE" 
            }
        else:
            # --- EXTRACT LIST OF HOLES ---
            holes_lines = [line.strip() for line in raw_holes.split("\n") if line.strip().startswith("-")]
            structured_list = []
            for idx, line in enumerate(holes_lines):
                structured_list.append({
                    "id": idx + 1,
                    "description": line
                })
            
            print(f"[ANALYZER]: Found {len(structured_list)} holes.")
            
            return {
                "coverage_holes": raw_holes, 
                "holes_list": structured_list,
                "status": "ANALYSIS_COMPLETE"
            }
    #====================================
    # ---- ROOT CAUSE ----
    #====================================
    elif mode == "root_cause":
        current_hole = state.get("current_hole",{})
        hole_description = current_hole.get('description', 'Unknown Hole')

        print(f"[ANALYZER]: Investigating root cause for -> {hole_description}")

        rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
        env_code = read_env(PROJECT_CONFIG.get("tb_dir", ""))
        sim_log = read_simulation_log(state.get("simulation_log_path", ""))

        specs = state.get("dut_specs", "")
        run_script = read_run_script(PROJECT_CONFIG.get("run_script_path", ""))
        # ---- SAVING EXPERIENCE -----
        #past_experience = query_analyzer_memory(hole_description)
        #memory_section = f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}" if past_experience else ""
        prompt = f"""You are an Expert UVM Verification Architect.
                    We have a specific coverage hole in our FCOV report. Your job is to act as a detective and find out WHY it is happening and HOW to fix it.
        
                    --- TARGET COVERAGE HOLE ---
                    {hole_description}
        
                    --- SIMULATION LOG (xsim.log summary) ---
                    {sim_log}
        
                    --- RTL DESIGN & UVM TESTBENCH FILES ---
                    {rtl_code}
                    {env_code}

                    --- RUN SCRIPT (Execution context) ---
                    {run_script}
                    --- DUT SPECIFICATIONS ---
                    {specs}
        
                    INSTRUCTIONS FOR UVM DIAGNOSTIC:
                    Perform a holistic check of the provided environment. Regardless of the DUT, apply these universal UVM debugging rules:
                    1. Run-Time Check: Look at the RUN SCRIPT. What test is currently being executed? Does this test actually instantiate and start the sequence needed to cover the hole?
                    2. Topology Check: Look at the testbench environment. Is the monitor's analysis port correctly connected to the coverage collector/subscriber?
                    3. Stimulus Generation: If the hole requires new stimulus, DO NOT just hardcode narrow constraints into existing base/general sequences. Instead, suggest creating a NEW directed sequence class. 
                    CRITICAL RULE: Always APPEND new sequence classes or test classes into the ALREADY EXISTING files (e.g., sequence.sv, test.sv). DO NOT create brand new .sv files for them!
                    1. Run-Time & Regression Check: 
                    - Check the RUN SCRIPT (.bat). If it only runs one test, check if other tests in test.sv could cover the hole.
                    - If a REGRESSION is needed, instruct the Generator to rewrite the .bat file using this EXACT logic:
             
                    EXAMPLE OF VIVADO REGRESSION SYNTAX:
                    call xsim top_sim -R -testplusarg UVM_TESTNAME=test_case_1 -cov_db_dir ./cov_1 -cov_db_name db1
                    call xsim top_sim -R -testplusarg UVM_TESTNAME=test_case_2 -cov_db_dir ./cov_2 -cov_db_name db2
                    call xcrg -dir ./cov_1 -dir ./cov_2 -db_name merged -report_format text -report_dir ./coverage_report_text
             
                    - IMPORTANT: For this to work, top.sv must use 'run_test();' without arguments.
                    ACTION PLAN REQUIREMENTS:
                    Write a detailed ACTION PLAN explaining the root cause and the exact logic to be added/changed.
                    If you need to create a new sequence, instruct the Generator to append it inside the existing sequence file, and modify the existing test file (or script) to run it.
                    DO NOT write the final SystemVerilog code yourself. Only provide the deep analysis and clear instructions for the Generator.

                    CRITICAL OUTPUT FORMAT:
                    Identify the EXACT FILE(S) that need to be modified. You can specify one or multiple files.
                    You MUST include a line in your response exactly like this:
                    TARGET_FILES: <filename1.sv>, <filename2.sv>                    
                    """
        
        response = llm.complete(prompt)
        # prompt tokens 
        prompt_tokens = len(encoding.encode(prompt))

        #responde tokens
        response_tokens = len(encoding.encode(response.text))

        current_tokens = state.get("iteration_tokens", 0)
        total_tokens = prompt_tokens + response_tokens + current_tokens

        target_file_match = re.search(r'TARGET_FILES?:\s*(.+)', response.text, re.IGNORECASE)
        target_file = target_file_match.group(1).strip() if target_file_match else "unknown_file.sv"

        return {
            "root_cause_hole": "LLM Analysis Generated", 
            "action_plan": response.text, 
            "target_file": target_file,
            "iteration_tokens": total_tokens,
            "status": "ANALYSIS_COMPLETE"
        }

    #====================================
    # ---- SYNTAX DEBUG ----
    #====================================
    elif mode == "syntax_debug":
        print("[ANALYZER]: Syntax error detected. Preparing data for human review/generator fix.")
        return {
            "status": "FAILED",  
            "analyzer_mode": "syntax_debug"
        }
    
    #====================================
    # ---- COMPARE RESULTS ----
    #====================================
    elif mode == "compare_results":
        print("[ANALYZER]: Comparing new FCOV report with previous state...")

        fcov_path = state.get("fcov_report_path", "")
        new_holes_str = extract_coverage_holes(fcov_path)

        target_hole = state.get("current_hole", {}).get("description", "")

        analysis_result = ""
        if target_hole and target_hole not in new_holes_str:
            analysis_result = f" SUCCESS! The hole '{target_hole}' was successfully fixed and covered."
        else:
            analysis_result = f" FAILED. The code compiled, but '{target_hole}' is STILL UNCOVERED."
            
            
        holes_lines = [line.strip() for line in new_holes_str.split("\n") if line.strip().startswith("-")]
        updated_list = [{"id": idx + 1, "description": line} for idx, line in enumerate(holes_lines)]

        return {
            "coverage_holes": new_holes_str,
            "holes_list": updated_list,
            "root_cause_hole": analysis_result, 
            "status": "ANALYSIS_COMPLETE",
            "analyzer_mode": "compare_results" # Forțăm păstrarea acestui mod
        }
    
    else:
        print(f"Unknown Mode '{mode}'")
        return {
            "status":"FAILED"
        }