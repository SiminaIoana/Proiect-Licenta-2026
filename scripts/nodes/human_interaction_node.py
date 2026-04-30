from state import AgentState
from utils_files.ui_messages import build_ui_message
from utils_files.intent_parser import normalize_user_input
from utils_files.injection import create_rollback_checkpoint, inject_generated_code
from utils_files.memory import save_negative_experience
from utils_files.phases import Phase
from utils_files.status import Status


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
        "user_command": "",
        "user_feedback": state.get("user_feedback", "")
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
                result["user_feedback"] = ""
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
            result["user_command"] = "retry_same_hole"
        elif user_choice == "3":
            result["user_command"] = "show_list"
        else:
            result["user_feedback"] = raw_input
            result["user_command"] = "retry_same_hole"
            result["ui_message"] = ("I have saved the observation as technical feedback and will re-run the analysis for the same hole.")
        return result

    if phase == Phase.RESULT_REVIEW:
        if user_choice == "1":
            result["user_command"] = "show_list"
        elif user_choice == "2":
            result["user_command"] = "retry_same_hole"
        elif user_choice == "3":
            result["user_command"] = "rollback"
        else:
            result["user_feedback"] = raw_input
            result["user_command"] = "retry_same_hole"
            result["ui_message"] = ("I have saved the observation as technical feedback and will re-run the analysis for the same hole.")
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
            if raw_input.strip().lower() not in ["2", "reject", "regenerate"]:
                result["user_feedback"] = raw_input

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_input
        )
        else:
            result["ui_message"] = (
            "I could not understand your decision.\n\n"
            "Please type **approve**, **regenerate**, or **q**."
            )
        return result

    return {
    "ui_input": "",
    "user_command": "",
    "user_feedback": state.get("user_feedback", ""),
    "ui_message": (
        "I could not understand your request.\n\n"
        "Please use one of the suggested options or provide a clearer instruction."
    )}



