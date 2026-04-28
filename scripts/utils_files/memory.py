import os
import re
import csv
import datetime

# ============================================================
# ------- FUNCTION FOR QUERYING LTM MEMORY --------
# ============================================================
def save_analyzer_experience(hole_description: str, action_plan: str, success_code: str) -> str:

    exp_dir = os.path.join("..", "results", "LTM_analyzer")
    os.makedirs(exp_dir, exist_ok=True)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(exp_dir, f"coverage_fix_{timestamp}.txt")

    files_modified = []
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