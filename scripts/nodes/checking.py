import os
import re
import time
import datetime
import subprocess
from state import AgentState
from utils import extract_code, save_code, save_to_csv, save_to_file
from config import PROJECT_CONFIG


# =====================================================
# ------ FUNCTION FOR VIVADO EXECUTION------
# =====================================================
def execute_vivado(bat_file_path: str, working_dir: str):
    start_time = time.time()            # counting time for metrics

    try:
        result = subprocess.run(
            [bat_file_path], 
            cwd=working_dir,      
            capture_output=True, 
            text=True, 
            shell=True,
            timeout = 300      
        )

        # gettinf compilation errors and return code generated
        raw_errors = result.stdout + "\n" + result.stderr
        returncode = result.returncode

    except subprocess.TimeoutExpired:
        print("VIVADO timeout")
        raw_errors = "ERROR: Timeout - Vivado simulation or compilation hanged."
        returncode = 1

    end_time = time.time()
    exec_time = round(end_time - start_time, 2)

    return returncode, raw_errors, exec_time



# =====================================================
# ------ FUNCTION FOR SAVING METRICS ------
# =====================================================
def save_checker_metrics(state: AgentState, status: str, exec_time: float, coverage_val: str, error_summary: str, raw_errors: str ):
    '''Save experimental data in csv and txt files'''
    results_dir = os.path.join("..","results")
    os.makedirs(results_dir, exist_ok=True)

    ''' TXT and CSV file path'''
    raport_path = os.path.join(results_dir, "raport_experimental.txt")
    csv_path = os.path.join(results_dir, "experimental_metrics_FIFO3.csv")

    timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M")
    it = state.get("iterations", 0)
    tokens = state.get("iteration_tokens", 0)

    # Save to TXT
    content_txt = f"[{timestamp}] Iteration: {it} | Status: {status} | Coverage: {coverage_val} | Time_exec: {exec_time}s\n"
    if status == "FAILED":
        content_txt += f"Errors:\n{raw_errors}\n"
    save_to_file(content_txt, raport_path)

    # Save to CSV
    content_csv = [timestamp, it, status, exec_time, coverage_val, error_summary, tokens]
    save_to_csv(content_csv, csv_path)


# =====================================================
# ------- CHECKER NODE ------
# =====================================================
def checker_node(state: AgentState):
    print("\n[CHECKER]: Validate code...")

    # prepared paths
    bat_file_path = PROJECT_CONFIG["bat_file_path"]             # batch file path
    working_dir = os.path.dirname(bat_file_path)                # working directory
    report_file_path = os.path.join(working_dir, "coverage_report_text", "functionalCoverageReport", "xcrg_func_cov_report.txt")
    sim_log_path = os.path.join(working_dir, "xsim.log")
    
    code = state.get("generated_code", "")
    previous_error = state.get("compilation_error", "")
    clean_code = extract_code(code) if code else ""

    # variables for saving metrics
    coverage_float = 0.0
    coverage_val = "N/A"
    status = "FAILED"
    error_summary = "N/A"
    errors = ""
    holes = ""
    analyzer_mode = ""

    # ---- RUNNING VIVADO ----
    returncode, raw_output, exec_time = execute_vivado(bat_file_path,working_dir)

    # -------------------------------------------
    # ------- COMPILATION ERRORS --------
    # -------------------------------------------
    if returncode != 0 or "ERROR:" in raw_output:       
        if "not recognized" in raw_output:
            errors = f"SYSTEM ERROR: Vivado path incorrect."
            error_summary = "System/Path Error"
        else:
            errors = "\n".join([l for l in raw_output.split('\n') if "ERROR:" in l][:15])
            error_summary = "Syntax/Compilation Error"

        print(f"Compilation FAILED (Time: {exec_time}s): \n {errors}")  
        analyzer_mode = "syntax_debug"
    
    else:
        if previous_error and "SYSTEM ERROR" not in previous_error:
            # ----------------------------------------------
            # ----- SAVING ERRORS IN LONG TERM MEMORY -----
            # ----------------------------------------------
            exp_dir = os.path.join("..", "results", "experience_data")
            os.makedirs(exp_dir, exist_ok=True)

            clean_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            exp_file_path = os.path.join(exp_dir, f"fix_{clean_ts}.txt")

            memory_entry = (
                f"VIVADO_ERROR_DESCRIPTION:\n{previous_error}\n\n"
                f"VERIFIED_WORKING_CODE:\n{clean_code}\n"
            )
            
            with open(exp_file_path, "w", encoding="utf-8") as f:
                f.write(memory_entry)
            
            print(f"[LONG TERM MEMORY]: Experience saved in {exp_file_path}")

        
        # ----------------------------------------------
        # ----- EXTRACT COVERAGE -----
        # ----------------------------------------------
        cov_match = re.search(r'MY_COVERAGE.*?(\d+\.\d+|\d+)', raw_output)

        if cov_match:
            coverage_float = float(cov_match.group(1))
            coverage_val = f"{coverage_float}%"

            status = "SUCCESS"
            error_summary = "None"
            analyzer_mode = "build_holes_list"
            print(f"Compilation & Simulation SUCCESSFUL | Time exec: {exec_time} sec | COVERAGE : {coverage_val}\n")

        else:
            coverage_val = "Extraction coverage value FAILED"
            analyzer_mode = "syntax_debug"
            status = "FAILED"
            error_summary = "Coverage Parse Error"
            errors = "Compilation successful, but could not extract MY_COVERAGE from logs. Make sure check_phase prints it."
            print(f"Error: {errors}")

    # ---- SAVE METRICS  -----
    save_checker_metrics(state, status, exec_time, coverage_val, error_summary, errors)
            
    # ---- RETURN FINAL STATE -----
    return {
        "status": status, 
        "compilation_error": errors, 
        "coverage_holes": holes,
        "coverage_value": coverage_float,
        "fcov_report_path": report_file_path if status != "FAILED" else "",
        "simulation_log_path": sim_log_path if status != "FAILED" else "",
        "analyzer_mode": analyzer_mode
    }