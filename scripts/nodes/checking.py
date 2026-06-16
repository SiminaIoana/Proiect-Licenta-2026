import os
from state import AgentState
from utils_files.status import Status
from utils_files.coverage import validate_coverage_report
from utils_files.results_saving import save_checker_metrics
from utils_files.memory import save_negative_experience, save_error_experience_if_fixed
from utils_files.vivado_utils import (
    has_vivado_error,
    execute_vivado, 
    prepare_checker_paths, 
    clean_old_simulation_logs, 
    build_combined_simulation_log, read_text_file_safe,
    parse_vivado_failure
)


def checker_node(state: AgentState):
    """
    Runs the Vivado/XSim validation step.

    The node executes the configured simulation script, collects logs,
    detects blocking errors and validates the generated coverage report.
    """
    print("\n[CHECKER]: Validate code...")

    paths = prepare_checker_paths()

    # Remove old simulation logs
    clean_old_simulation_logs(paths["working_dir"])

    returncode, raw_output, exec_time = execute_vivado(
        paths["bat_file_path"],
        paths["working_dir"]
    )

    combined_log_path = build_combined_simulation_log(
    paths["working_dir"],
    raw_output
    )

    combined_log_text = read_text_file_safe(combined_log_path)
    full_error_text = raw_output + "\n" + combined_log_text
    # Stop the flow if Vivado/XSim reports errors
    if has_vivado_error(returncode, raw_output, combined_log_text):
        errors, error_summary = parse_vivado_failure(full_error_text)
        status = Status.FAILED
        coverage_val = "N/A"

        if state.get("generated_code"):
            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                errors
            )
        print(f"Compilation FAILED (Time: {exec_time}s):\n{errors}")

    else:
        # If the error is fixed by the code and the run is successful, save the experience
        save_error_experience_if_fixed(state)

        status, error_summary, coverage_val, errors = validate_coverage_report(paths["report_file_path"])

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
    print(f"[DEBUG CHECKER] Combined simulation log: {combined_log_path}")

    return {
        "status": status,
        "compilation_error": errors,
        "fcov_report_path": paths["report_file_path"] if status == Status.SUCCESS else "",
        "simulation_log_path": combined_log_path if os.path.exists(combined_log_path) else "",
    }