from state import AgentState
from llama_index.core import Settings
from utils_files.phases import Phase
from utils_files.status import Status
from utils_files.file_ops import extract_code

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
        ui_message += "- **[2]** Regenerate plan -> Try another solution for the SAME hole.\n"
        ui_message += "- **[3]** Pick another hole.\n"
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