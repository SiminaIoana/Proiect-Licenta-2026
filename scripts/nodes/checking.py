import os
import time
import datetime
import subprocess
from state import AgentState
from scripts.utils_files.results_saving import save_to_csv, save_to_file
from utils_files.memory import save_negative_experience
from utils_files.file_ops import extract_code
from utils_files.status import Status
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
def save_checker_metrics(state: AgentState, status: Status, exec_time: float, coverage_val: str, error_summary: str, raw_errors: str ):
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
    content_txt = f"[{timestamp}] Iteration: {it} | Status: {status.value} | Coverage: {coverage_val} | Time_exec: {exec_time}s\n"
    if status == Status.FAILED:
        content_txt += f"Errors:\n{raw_errors}\n"
    save_to_file(content_txt, raport_path)

    # Save to CSV
    content_csv = [timestamp, it, status.value, exec_time, coverage_val, error_summary, tokens]
    save_to_csv(content_csv, csv_path)


def prepare_checker_paths():
    bat_file_path = PROJECT_CONFIG["bat_file_path"]
    working_dir = os.path.dirname(bat_file_path)

    return {
        "bat_file_path": bat_file_path,
        "working_dir": working_dir,
        "report_file_path": os.path.join(
            working_dir,
            "coverage_report_text",
            "functionalCoverageReport",
            "xcrg_func_cov_report.txt"
        ),
        "sim_log_path": os.path.join(working_dir, "xsim.log")
    }


def has_vivado_error(returncode: int, raw_output: str) -> bool:
    return returncode != 0 or "ERROR:" in raw_output


def parse_vivado_failure(raw_output: str):
    if "not recognized" in raw_output:
        return "SYSTEM ERROR: Vivado path incorrect.", "System/Path Error"

    errors = "\n".join(
        [line for line in raw_output.split("\n") if "ERROR:" in line][:15]
    )
    return errors, "Syntax/Compilation Error"


def save_error_experience_if_fixed(state: AgentState):
    previous_error = state.get("compilation_error", "")
    code = state.get("generated_code", "")
    clean_code = extract_code(code) if code else ""

    if not previous_error or "SYSTEM ERROR" in previous_error:
        return

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


def validate_coverage_report(report_file_path: str):
    if os.path.exists(report_file_path):
        return Status.SUCCESS, "None", "Report generated", ""

    return (
        Status.FAILED,
        "Coverage Report Missing",
        "N/A",
        "Vivado ran successfully, but coverage report was not generated."
    )

# =====================================================
# ------- CHECKER NODE ------
# =====================================================
def checker_node(state: AgentState):
    print("\n[CHECKER]: Validate code...")

    paths = prepare_checker_paths()

    returncode, raw_output, exec_time = execute_vivado(
        paths["bat_file_path"],
        paths["working_dir"]
    )

    if has_vivado_error(returncode, raw_output):
        errors, error_summary = parse_vivado_failure(raw_output)
        status = Status.FAILED
        coverage_val = "N/A"
        if state.get("generated_code"):
            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                errors
            )

        print(f"Compilation FAILED (Time: {exec_time}s): \n {errors}")

    else:
        save_error_experience_if_fixed(state)

        status, error_summary, coverage_val, errors = validate_coverage_report(
            paths["report_file_path"]
        )

        if status == Status.SUCCESS:
            print(f"Compilation & Simulation SUCCESSFUL | Time exec: {exec_time} sec")
        else:
            print(f"Error: {errors}")

    save_checker_metrics(
        state,
        status,
        exec_time,
        coverage_val,
        error_summary,
        errors
    )

    print(f"[DEBUG CHECKER] Final coverage_val: {coverage_val}")

    return {
        "status": status,
        "compilation_error": errors,
        "fcov_report_path": paths["report_file_path"] if status == Status.SUCCESS else "",
        "simulation_log_path": paths["sim_log_path"] if status == Status.SUCCESS else "",
    }