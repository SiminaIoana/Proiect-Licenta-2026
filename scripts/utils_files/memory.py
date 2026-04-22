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

    memory_entry = (
        f"COVERAGE_HOLE_DESCRIPTION:\n{hole_description}\n\n"
        f"ANALYZER_PROPOSED_PLAN:\n{action_plan}\n\n"
        f"VERIFIED_STIMULUS_CODE:\n{success_code}\n"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(memory_entry)
    
    print(f"[ANALYZER LTM]: Good experience saved in:{file_path}")


def save_negative_experience(hole_description, rejected_code, user_feedback):
    exp_dir = os.path.join("..", "results", "LTM_rejected")
    os.makedirs(exp_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(exp_dir, f"rejected_{timestamp}.txt")

    entry = (
        f"HOLE_DESCRIPTION: {hole_description}\n"
        f"REJECTED_CODE_PATTERN:\n{rejected_code}\n"
        f"USER_REASON_FOR_REJECTION: {user_feedback}\n"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(entry)