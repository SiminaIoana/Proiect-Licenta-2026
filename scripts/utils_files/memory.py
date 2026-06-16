import os
import datetime
from state import AgentState
from utils_files.file_ops import extract_code


def save_analyzer_experience(hole_description: str, action_plan: str, success_code: str) -> str:
    """
    Saves a successful coverage closure experience for future Analyzer runs.
    The saved entry contains the selected coverage hole, the proposed action
    plan, the modified files and the verified generated code.
    """
    exp_dir = os.path.join("..", "results", "LTM_analyzer")
    os.makedirs(exp_dir, exist_ok=True)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(exp_dir, f"coverage_fix_{timestamp}.txt")

    files_modified = []
    # Extract modified file names from the success_code
    for line in success_code.splitlines():
        if "FILE:" in line:
            filename = line.split("FILE:", 1)[1].strip()
            files_modified.append(filename)

    files_modified = list(dict.fromkeys(files_modified))
    files_text = "\n".join(f"- {f}" for f in files_modified) if files_modified else "N/A"
    
    memory_entry = (
        f"COVERAGE_HOLE_DESCRIPTION:\n{hole_description}\n\n"
        f"ANALYZER_PROPOSED_PLAN:\n{action_plan}\n\n"
        f"FILES_MODIFIED:\n{files_text}\n\n"
        f"VERIFIED_STIMULUS_CODE:\n{success_code}\n"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(memory_entry)
    
    print(f"[ANALYZER LTM]: Good experience saved in:{file_path}")


def save_negative_experience(hole_description, rejected_code, reason):
    """
    Saves rejected or failed generated code as negative experience.
    This helps the Generator avoid repeating code patterns that previously
    failed compilation, simulation or user review.
    """
    exp_dir = os.path.join("..", "results", "LTM_rejected")
    os.makedirs(exp_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(exp_dir, f"rejected_{timestamp}.txt")

    entry = (
        f"COVERAGE_HOLE_DESCRIPTION:\n{hole_description}\n\n"
        f"REJECTED_OR_FAILED_CODE:\n{rejected_code}\n\n"
        f"REJECTION_OR_ERROR_REASON:\n{reason}\n"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(entry)

    print(f"[NEGATIVE LTM]: Rejected experience saved in: {file_path}")

    
def save_error_experience_if_fixed(state: AgentState):
    """
    Saves generated code as a positive experience.
    This is called after a successful Checker run.
    """
    previous_error = state.get("compilation_error", "")
    code = state.get("generated_code", "")
    clean_code = extract_code(code) if code else ""

    # Looking just for system error and previuos error
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

