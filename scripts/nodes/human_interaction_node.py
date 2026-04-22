from state import AgentState
from utils_files.file_ops import extract_code,apply_smart_injection
from config import PROJECT_CONFIG
import os

# ==========================================
# ---------- HUMAN INTERACTION ----------
#===========================================
def human_interaction_node(state: AgentState):
    status = state.get("status", "")
    errors = state.get("compilation_error", "")
    analyzer_mode = state.get("analyzer_mode", "")
    
    # Reading input from the Streamlit UI
    user_choice = state.get("ui_input", "").strip().lower()

    # ----------------------------------------------------------------
    # PHASE 1: NO INPUT YET (Prepare the exact message for UI)
    # ----------------------------------------------------------------
    if not user_choice:
        ui_message = ""

        if (status == "FAILED" or analyzer_mode == "syntax_debug") and errors:
            ui_message += "### Vivado Compilation Failed\n\n"
            ui_message += "**The generated code has syntax errors:**\n"
            ui_message += f"```text\n{errors}\n```\n\n"
            ui_message += "**Please choose an action:**\n"
            ui_message += "- **[1]** Let the AI try to fix the syntax error automatically.\n"
            ui_message += "- **[q]** Quit and fix it manually."

        elif analyzer_mode == "root_cause":
            plan = state.get("action_plan", "")
            target = state.get("target_file", "")
            
            ui_message += "### Proposed Action Plan\n\n"
            ui_message += f"**Target file to modify:** `{target}`\n\n"
            ui_message += "---\n\n"
            ui_message += f"{plan}\n\n"
            ui_message += "---\n\n"
            ui_message += "**What is your decision?**\n"
            ui_message += "- **[1]** Approve plan -> Let AI write the code.\n"
            ui_message += "- **[2]** Reject plan -> Pick another hole from the list.\n"
            ui_message += "- **[q]** Quit session -> I will fix it manually."

        elif analyzer_mode == "compare_results":
            result_msg = state.get("root_cause_hole", "")
            ui_message += "### Validation Results\n\n"
            ui_message += f"{result_msg}\n\n"
            ui_message += "**What would you like to do next?**\n"
            ui_message += "- **[1]** Pick another coverage hole to fix.\n"
            ui_message += "- **[2]** Retry fixing the SAME hole (Let AI try another approach).\n"
            ui_message += "- **[q]** Quit session."

        elif analyzer_mode == "build_holes_list":
            holes_list = state.get("holes_list", [])
            if not holes_list:
                ui_message += "### Analysis Complete\n\n"
                ui_message += "**No coverage holes to fix!** We reached 100% or no data is available.\n\n"
                ui_message += "Press **[q]** to quit."
            else:
                num_holes = len(holes_list)
                ui_message += "### Coverage Analysis Results\n\n"
                ui_message += f"The analyzer identified **{num_holes}** coverage holes. Here is the detailed list:\n\n"
                
                # Building a markdown table for better visualization
                ui_message += "| ID | Variable / Description |\n"
                ui_message += "| :---: | :--- |\n"
                for hole in holes_list:
                    clean_desc = hole['description'].replace('\n', ' ').strip()
                    ui_message += f"| **{hole['id']}** | {clean_desc} |\n"
                
                ui_message += "\n**Next step:**\n"
                ui_message += "- Type the **ID** of the hole you want the AI to analyze and fix.\n"
                ui_message += "- Type **[q]** to quit and end the session."

       
        elif analyzer_mode == "code_review":
            generated_code = state.get("generated_code", "")
            extracted_files = extract_code(generated_code)
            
            ui_message += "### Code Review Required\n\n"
            ui_message += "The AI has generated the following code based on the action plan. Please review it carefully.\n\n"
            
            for filename, file_content in extracted_files.items():
                ui_message += f" **File:** `{filename}`\n"
                ui_message += f"```systemverilog\n{file_content}\n```\n\n"
                
            ui_message += "---\n\n"
            ui_message += "**What is your decision?**\n"
            ui_message += "- **[1]** Approve Code -> Save files and Run Vivado.\n"
            ui_message += "- **[2]** Reject Code -> Send back to AI to regenerate.\n"
            ui_message += "- **[q]** Quit session."

        return {
            "status": "WAITING_FOR_HUMAN",
            "ui_message": ui_message
        }

    # ----------------------------------------------------------------
    # PHASE 2: WE HAVE INPUT (User typed in UI)
    # ----------------------------------------------------------------
    return_dict = {"ui_input": "", "status": "PROCESSING"}

    if user_choice == 'q':
        return_dict["user_command"] = "quit"
        return return_dict

    if (status == "FAILED" or analyzer_mode == "syntax_debug") and errors:
        if user_choice == "1":
            return_dict["user_command"] = "fix_syntax"
            return_dict["status"] = "PROCESSING"
            return return_dict 

    elif analyzer_mode == "root_cause":
        if user_choice == '1': return_dict["user_command"] = "approve_plan"
        elif user_choice == '2': 
            return_dict["user_command"] = "show_list"
            return_dict["analyzer_mode"] = "build_holes_list"

    elif analyzer_mode == "compare_results":
        if user_choice == '1':
            return_dict["user_command"] = "show_list"
            return_dict["analyzer_mode"] = "build_holes_list"
        elif user_choice == '2':
            return_dict["user_command"] = "fix_hole"
            return_dict["analyzer_mode"] = "root_cause"

    elif analyzer_mode == "build_holes_list":
        if user_choice.isdigit():
            hole_id = int(user_choice)
            holes_list = state.get("holes_list", [])
            selected_hole = next((h for h in holes_list if h["id"] == hole_id), None)
            
            if selected_hole:
                return_dict.update({"current_hole": selected_hole, "analyzer_mode": "root_cause", "user_command": "fix_hole"})
            else:
                return_dict["status"] = "WAITING_FOR_HUMAN"
                return_dict["ui_message"] = "Invalid ID. Please select a valid number from the list."

    # --- Code review logic ---
    elif analyzer_mode == "code_review":
        if user_choice == '1':
            return_dict["user_command"] = "approve_code"
            
            generated_code = state.get("generated_code", "")
            
            extracted_files = extract_code(generated_code)
            
            tb_dir = PROJECT_CONFIG.get("tb_dir", "")
            rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")
            
            for filename, file_content in extracted_files.items():
                if not filename or "unknown_file" in filename: 
                    continue
                
                file_path_to_save = None
                
                for root, _, files in os.walk(tb_dir):
                    if filename in files:
                        file_path_to_save = os.path.join(root, filename)
                        break

                if not file_path_to_save:
                    for root, _, files in os.walk(rtl_dir):
                        if filename in files:
                            file_path_to_save = os.path.join(root, filename)
                            break
                            
                if file_path_to_save:
                    apply_smart_injection(file_path_to_save, file_content)
                else:
                    print(f"[ERROR] Target file {filename} not found on disk for injection.")
            
        elif user_choice == '2':
            return_dict["user_command"] = "reject_code"

    if "user_command" not in return_dict and return_dict.get("status") != "WAITING_FOR_HUMAN":
        return_dict["status"] = "WAITING_FOR_HUMAN"
        return human_interaction_node(state | {"ui_input": ""})

    return return_dict