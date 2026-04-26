from state import AgentState
from utils_files.file_ops import extract_code,apply_smart_injection
from config import PROJECT_CONFIG
import os
from utils_files.phases import Phase
from utils_files.status import Status


def inject_generated_code(state: AgentState):
    generated_code = state.get("generated_code", "")
    extracted_files = extract_code(generated_code)

    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")
    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))

    for filename, file_content in extracted_files.items():
        if not filename or "unknown_file" in filename:
            continue

        file_path_to_save = find_file_in_dirs(filename, [tb_dir, rtl_dir, bat_dir])

        if file_path_to_save:
            apply_smart_injection(file_path_to_save, file_content)
        else:
            print(f"[ERROR] Target file {filename} not found on disk for injection.")


def find_file_in_dirs(filename: str, dirs: list):
    for directory in dirs:
        if not directory or not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if filename in files:
                return os.path.join(root, filename)

    return None


def build_ui_message(state: AgentState, phase: Phase, status: Status, errors: str) -> str:
    ui_message = ""

    if phase == Phase.PLAN_REVIEW and status == Status.FAILED and errors:
        ui_message += "### Vivado Compilation Failed\n\n"
        ui_message += "**The generated code has syntax errors:**\n"
        ui_message += f"```text\n{errors}\n```\n\n"
        ui_message += "**Please choose an action:**\n"
        ui_message += "- **[1]** Let the AI try to fix the syntax error automatically.\n"
        ui_message += "- **[q]** Quit and fix it manually."
        return ui_message

    if phase == Phase.SELECT_HOLE:
        holes_list = state.get("holes_list", [])

        if not holes_list:
            ui_message += "### Analysis Complete\n\n"
            ui_message += "**No coverage holes detected.**\n\n"
            ui_message += "Press **[q]** to quit."
            return ui_message

        ui_message += "### Coverage Analysis Results\n\n"
        ui_message += f"The analyzer identified **{len(holes_list)}** coverage holes:\n\n"
        ui_message += "| ID | Description |\n"
        ui_message += "| :---: | :--- |\n"

        for hole in holes_list:
            clean_desc = hole["description"].replace("\n", " ").strip()
            ui_message += f"| **{hole['id']}** | {clean_desc} |\n"

        ui_message += "\n**Next step:**\n"
        ui_message += "- Type the **ID** of the hole you want to analyze.\n"
        ui_message += "- Type **[q]** to quit."
        return ui_message

    if phase == Phase.PLAN_REVIEW:
        plan = state.get("action_plan", "")
        target = state.get("target_file", "")

        ui_message += "### Proposed Action Plan\n\n"
        ui_message += f"**Target file:** `{target}`\n\n"
        ui_message += "---\n\n"
        ui_message += f"{plan}\n\n"
        ui_message += "---\n\n"
        ui_message += "**What is your decision?**\n"
        ui_message += "- **[1]** Approve plan -> Let AI write code.\n"
        ui_message += "- **[2]** Reject plan -> Pick another hole.\n"
        ui_message += "- **[q]** Quit."
        return ui_message
    
    if phase == Phase.RESULT_REVIEW:
        result_msg = state.get("root_cause_hole", "")
        coverage = state.get("coverage_value", 0.0)
        holes_list = state.get("holes_list", [])
        errors = state.get("compilation_error", "")
        ui_message += "### Validation Results\n\n"
        
        if errors:
            ui_message += "### Vivado error after generated code\n\n"
            ui_message += f"```text\n{errors}\n```\n\n"
            ui_message += "**The injected code caused an error.**\n\n"
        else:
            ui_message += f"{result_msg}\n\n"

        if coverage >= 100.0 and not holes_list:
            ui_message += "🎯 **Target reached. Full coverage achieved.**\n\n"
            ui_message += "- **[q]** Finish session."
        else:
            ui_message += "**What would you like to do next?**\n"
            ui_message += "- **[1]** Pick another coverage hole.\n"
            ui_message += "- **[2]** Retry fixing the same hole.\n"
            ui_message += "- **[3]** Rollback to previous code version.\n"
            ui_message += "- **[q]** Quit."

        return ui_message

    if phase == Phase.CODE_REVIEW:
        generated_code = state.get("generated_code", "")
        extracted_files = extract_code(generated_code)

        ui_message += "### Code Review Required\n\n"
        ui_message += "The AI generated the following code:\n\n"

        for filename, file_content in extracted_files.items():
            ui_message += f"**File:** `{filename}`\n"
            ui_message += f"```systemverilog\n{file_content}\n```\n\n"

        ui_message += "---\n\n"
        ui_message += "**What is your decision?**\n"
        ui_message += "- **[1]** Approve code -> Save files and run Vivado.\n"
        ui_message += "- **[2]** Reject code -> Regenerate.\n"
        ui_message += "- **[q]** Quit."
        return ui_message


    return "Waiting for next action..."

def create_rollback_checkpoint(state: AgentState):
    generated_code = state.get("generated_code", "")
    extracted_files = extract_code(generated_code)
    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))
    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")

    rollback_files = {}

    for filename in extracted_files.keys():
        if not filename or "unknown_file" in filename:
            continue

        file_path = find_file_in_dirs(filename, [tb_dir, rtl_dir, bat_dir])

        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                rollback_files[file_path] = f.read()

    return rollback_files


def restore_rollback_files(state: AgentState):
    rollback_files = state.get("rollback_files", {})
    if not rollback_files:
        return {
        "ui_message": "Rollback failed: no checkpoint was found.",
        "rollback_files": {}
        }
    for file_path, old_content in rollback_files.items():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(old_content)

    return {
        "rollback_files": {},
        "ui_message": "Rollback completed. Previous code version was restored."
    }


def normalize_user_input(user_input: str, phase: Phase) -> str:
    text = user_input.strip().lower()

    # global exit commands
    if any(word in text for word in ["quit", "exit", "stop"]) or text == "q":
        return "q"

    # SELECT_HOLE: numbers mean hole IDs
    if phase == Phase.SELECT_HOLE:
        if text.isdigit():
            return text

        if any(word in text for word in ["list", "refresh", "reanalyze", "holes"]):
            return "show_list"

        return text

    # PLAN_REVIEW / CODE_REVIEW / RESULT_REVIEW
    if phase in [Phase.PLAN_REVIEW, Phase.CODE_REVIEW, Phase.RESULT_REVIEW]:

        if any(word in text for word in ["approve", "accept", "continue", "yes", "ok", "go ahead"]) or text == "1":
            return "1"

        if any(word in text for word in ["reject", "regenerate", "retry", "try again", "new solution", "no"]) or text == "2":
            return "2"

        if phase == Phase.RESULT_REVIEW:
            if any(word in text for word in ["rollback", "revert", "undo", "restore"]) or text == "3":
                return "3"

    return text
# ==========================================
# ---------- HUMAN INTERACTION ----------
#===========================================
def human_interaction_node(state: AgentState):
    phase = state.get("phase", Phase.INIT)
    status = state.get("status", Status.PROCESSING)
    errors = state.get("compilation_error", "")
    raw_input = state.get("ui_input", "")
    user_choice = normalize_user_input(raw_input, phase)

    # ------------------------------------------------------------
    # NO INPUT YET -> build UI message
    # ------------------------------------------------------------
    if not user_choice:
        ui_message = build_ui_message(state, phase, status, errors)

        return {
            "ui_message": ui_message
        }

    # ------------------------------------------------------------
    # USER INPUT RECEIVED
    # ------------------------------------------------------------
    result = {
        "ui_input": "",
        "user_command": ""
    }

    if user_choice == "q":
        result["user_command"] = "quit"
        return result

    # ERROR_ANALYSIS / PLAN_REVIEW with syntax error
    if phase == Phase.PLAN_REVIEW and status == Status.FAILED and errors:
        if user_choice == "1":
            result["user_command"] = "fix_syntax"
        return result

    # SELECT_HOLE
    if phase == Phase.SELECT_HOLE:
        if user_choice == "show_list":
            result["user_command"] = "show_list"
            return result
        if user_choice.isdigit():
            hole_id = int(user_choice)
            holes_list = state.get("holes_list", [])
            selected_hole = next((h for h in holes_list if h["id"] == hole_id), None)

            if selected_hole:
                result["current_hole"] = selected_hole
                result["user_command"] = "fix_hole"
            else:
                result["ui_message"] = "Invalid ID. Please select a valid hole number."
        else:
            result["ui_message"] = (
            "I could not understand which hole you want to analyze.\n\n"
            "Please type a valid hole ID, **show list**, or **q**."
        )
        return result

    # PLAN_REVIEW
    if phase == Phase.PLAN_REVIEW:
        if user_choice == "1":
            result["user_command"] = "approve_plan"
        elif user_choice == "2":
            result["user_command"] = "show_list"
        else:
            result["ui_message"] = (
            "I could not understand your decision.\n\n"
            "Please type **approve**, **reject**, or **q**."
            )
        return result

    if phase == Phase.RESULT_REVIEW:
        if user_choice == "1":
            result["user_command"] = "show_list"
        elif user_choice == "2":
            result["user_command"] = "retry_same_hole"
        elif user_choice == "3":
            result["user_command"] = "rollback"
        else:
            result["ui_message"] = (
            "I could not understand your request.\n\n"
            "Please type **pick another hole**, **retry**, **rollback**, or **q**."
        )
        return result
    
    # CODE_REVIEW
    if phase == Phase.CODE_REVIEW:
        if user_choice == "1":
            result["user_command"] = "approve_code"
            result["previous_coverage"] = state.get("coverage_value", 0.0)
            rollback_files = create_rollback_checkpoint(state)
            result["rollback_files"] = rollback_files
            inject_generated_code(state)

        elif user_choice == "2":
            result["user_command"] = "reject_code"
        
        else:
            result["ui_message"] = (
            "I could not understand your decision.\n\n"
            "Please type **approve**, **regenerate**, or **q**."
            )
        return result

    return {
    "ui_input": "",
    "user_command": "",
    "ui_message": (
        "I could not understand your request.\n\n"
        "Please use one of the suggested options or provide a clearer instruction."
    )}



