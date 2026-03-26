import os
import re
import time
import datetime
import subprocess
from state import AgentState
from config import VIVADO_BIN_PATH
from utils import extract_code, save_code, save_to_csv, save_to_file

# function for extracting information from coverage raport
def extract_coverage_holes(path: str)->str:
    # parse txt raport and return a list with uncovered bins
    holes = []
    try:
        with open(path,'r') as file:
            content = file.read()
        
        # looking for coverpoints
        point_tables = re.finditer(r"Cover Point Table for Inst :.*?, Variable :,\s*(.*?)\n.*?Uncovered bins\s*\n.*?\n(.*?)Covered bins", content, re.DOTALL | re.IGNORECASE)
        
        for table in point_tables:
            var_name = table.group(1).strip()
            bins_data = table.group(2).strip().split('\n')

            #extract names of bins
            missed = [line.split(',')[0].strip() for line in bins_data if line.strip() and ',' in line and line.split(',')[0].strip() != "Name"]

            if missed:
                holes.append(f"- Variable '{var_name}' missed bins: {', '.join(missed)}")

        # looking for cross coverage table
        cross_tables = re.finditer(r"Cross Cover Point Table for Inst :.*?, Variable :,\s*(.*?)\n.*?Auto Uncovered bins\s*\n.*?\n(.*?)Auto Covered bins", content, re.DOTALL | re.IGNORECASE)
        for table in cross_tables:
            cross_name = table.group(1).strip()
            holes.append(f"- Cross coverage '{cross_name}' missed state combinations.")
            
        if not holes:
            return "No obvious coverage holes found in text report."
            
        return "\n".join(holes)    
    
    except FileNotFoundError:
        return f"Warning: Coverage report file not found at '{path}'. Did xcrg generate it?"
    except PermissionError:
        return f"Warning: Permission denied. The file '{path}' might be locked by Vivado."
    except Exception as e:
        return f"Warning: Could not read coverage report due to an unexpected error: {str(e)}"
            
# NODE 3 checking
def checker_node(state: AgentState):
    print("\nNode 3 Checker: Validate generated code...")
    code = state.get("generated_code", "")
    previous_error = state.get("compilation_error", "")

    # extract the code
    clean_code = extract_code(code)

    # write the file on disk (create or open file first)
    file_path = r"C:\Users\Simina\An4\Licenta\LICENTA\FIFO_SIMULATION\TB-FIFO\coverage_container.sv"
    save_code(clean_code, file_path)

    # batch file path
    bat_file_path = r"C:\Users\Simina\An4\Licenta\LICENTA\FIFO_SIMULATION\SIM-FIFO\MakeSVfile.bat"

    #working directory
    working_dir = os.path.dirname(bat_file_path)

    # verify write function using verilog simulator
    print(f"\nCompiling {file_path} using VIVADO...")

    # execution time VIVADO
    start_time = time.time()
    try:
        result = subprocess.run(
            [bat_file_path], 
            cwd=working_dir,      
            capture_output=True, 
            text=True, 
            shell=True,
            timeout = 60      
        )

        raw_errors = result.stdout + "\n" + result.stderr
        returncode = result.returncode

    except subprocess.TimeoutExpired:
        print("VIVADO timeout")
        raw_errors = "ERROR: Timeout - Vivado simulation or compilation hanged."
        returncode = 1

    end_time = time.time()
    execution_time = time.time()
    exec_time = round(end_time - start_time, 2)

    results_dir = os.path.join("..", "results")
    raport_path = os.path.join(results_dir, "raport_experimental.txt")
    csv_path = os.path.join(results_dir, "experimental_metrics_FIFO3.csv")
    memory_path = os.path.join(results_dir, "experience_memory.txt")
    it = state.get("iterations", 0)

    # date, time for saving metrics
    timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M")
    tokens = state.get("iteration_tokens", 0)
    coverage_val = "N/A"
    status = "FAILED"
    error_summary = "N/A"


    if returncode != 0 or "ERROR:" in raw_errors:
        status = "FAILED"        
        if "not recognized" in raw_errors:
            errors = f"SYSTEM ERROR: Vivado path is incorrect or access denied. Path used: {VIVADO_BIN_PATH}"
            error_summary = "System/Path Error"
        else:
            errors = "\n".join([l for l in raw_errors.split('\n') if "ERROR:" in l or "coverage_container.sv" in l][:15])
            error_summary = "Syntax/Compilation Error"

        print(f"Compilation FAILED (Time: {exec_time}s): \n {errors}")   
        #save errors
        content_txt = f"[{timestamp}]  Iteration: {it} | Erors: {errors}  | Time_exec: {exec_time}\n"
        save_to_file(content_txt, raport_path )
        #save metrics
        content_csv = [timestamp, it, status, exec_time, coverage_val, error_summary, tokens]
        save_to_csv(content_csv, csv_path)

        return {"status": status, "compilation_error": errors, "coverage_holes": ""}
    else:
        if previous_error and "SYSTEM ERROR" not in previous_error:
            print("\nNode 3 Checker: Generating Long-Term Memory (LTM) entry...")

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
            
            print(f"Node 3 Checker: Experience saved in {exp_file_path}")

        status = "SUCCESS"
        error_summary = "None"

        #coverage status
        cov_match = re.search(r'MY_COVERAGE.*?(\d+\.\d+|\d+)', raw_errors)

        if cov_match:
            coverage_float = float(cov_match.group(1))
            coverage_val = f"{coverage_float}%"
            target = state.get("target_coverage", 100.0)
            if coverage_float < target:
                status = "LOW COVERAGE"
                error_summary= "Coverage below target!"
                print(f"Compilation SUCCESSFUL, but COVERAGE IS TOO LOW: {coverage_float}. Target is 75%.")

                report_file_path = os.path.join(working_dir, "coverage_report_text", "xcrg_func_cov_report.txt")
                holes = extract_coverage_holes(report_file_path)

                # save errors
                content_txt = f"[{timestamp}]  Iteration: {it} | Coverage: {coverage_val} \n Coverage Holes Sent to Analyzer: {holes}\n" + "-" * 50
                save_to_file(content_txt, raport_path)
                #save metrics
                content_csv = [timestamp, it, status, exec_time, coverage_val, error_summary, tokens]
                save_to_csv(content_csv,csv_path)
                
                return {"status": status, "compilation_error": "", "coverage_holes": holes} 
                       
            else:
                status = "SUCCESS"
                error_summary = "None"
                print(f"Compilation SUCCESSFUL, Target reached | Time exec: {exec_time} sec | COVERAGE : {coverage_val}\n")

                #save errors
                content_txt = f"[{timestamp}]  Iteration: {it} | Coverage: {coverage_val}\n" + "-" * 50   
                save_to_file(content_txt, raport_path)
                #save metricss
                content_csv = [timestamp, it, status, exec_time, coverage_val, error_summary, tokens]
                save_to_csv(content_csv, csv_path)
 
                return {"status": status, "compilation_error": "", "coverage_holes": ""}
        else:
            coverage_val = "Extraction coverage  value FAILED"
            status = "FAILED"
            error_summary = "Coverage Parse Error"
            errors = "Compilation successful, but could not extract MY_COVERAGE from logs. Make sure check_phase prints it."
            print(f"Error: {errors}")

            #save errors
            content_txt = f"[{timestamp}]  Iteration: {it} | Coverage: {coverage_val} \n Feedback send to agent: {errors}\n" + "-" * 50            
            save_to_file(content_txt, raport_path)
            #save metrics
            content_csv = [timestamp, it, status, exec_time, coverage_val, error_summary, tokens]
            save_to_csv(content_csv, csv_path)

            return {"status": status, "compilation_error": errors, "coverage_holes": ""}