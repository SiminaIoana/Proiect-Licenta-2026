from state import AgentState
from utils_files.phases import Phase
from utils_files.status import Status
from utils_files.file_ops import extract_code

import re


def extract_plan_field(plan: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(plan or "")
    return match.group(1).strip() if match else ""


def extract_plan_section(plan: str, section_name: str) -> str:
    pattern = re.compile(
        rf"^\s*{re.escape(section_name)}\s*:\s*(.*?)(?=^\s*[A-Z_ ]+\s*:|\Z)",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(plan or "")
    if not match:
        return ""

    text = match.group(1).strip()
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def build_short_plan_view(plan: str, target: str) -> str:
    short_response = extract_plan_section(plan, "SHORT_RESPONSE")
    root_cause = extract_plan_section(plan, "ROOT_CAUSE_SUMMARY")
    planned_change = extract_plan_section(plan, "PLANNED_CHANGE")

    strategy = extract_plan_field(plan, "CHOSEN STRATEGY")
    code_action = extract_plan_field(plan, "CODE_ACTION")
    target_files = extract_plan_field(plan, "TARGET_FILES") or target

    msg = ""

    if short_response:
        msg += f"**Summary:**\n{short_response}\n\n"

    if root_cause:
        msg += f"**Root cause:**\n{root_cause}\n\n"

    msg += "**Proposed fix:**\n"

    if strategy:
        msg += f"- **Strategy:** `{strategy}`\n"

    if code_action:
        msg += f"- **Code action:** `{code_action}`\n"

    if target_files:
        msg += f"- **Target files:** `{target_files}`\n"

    if planned_change:
        msg += f"\n**Planned change:**\n{planned_change}\n"

    if not msg.strip():
        msg = "A short plan summary could not be extracted. Please review the full action plan in the debug logs."

    return msg.strip()


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
        ui_message += build_short_plan_view(plan, target)
        ui_message += "\n\n---\n\n"
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

        success_fixed = "SUCCESS_FIXED_HOLE" in result_msg

        ui_message += "### Validation Results\n\n"

        if errors:
            ui_message += "### Vivado error after generated code\n\n"
            ui_message += f"```text\n{errors}\n```\n\n"
            ui_message += "**The injected code caused an error.**\n\n"
        else:
            ui_message += f"{result_msg}\n\n"

        if coverage >= 100.0 and not holes_list:
            ui_message += "**Target reached. Full coverage achieved.**\n\n"
            ui_message += "**What would you like to do next?**\n"
            ui_message += "- **[q]** Quit."
            return ui_message

        if success_fixed:
            ui_message += "**The selected coverage hole was fixed.**\n\n"
            ui_message += "**What would you like to do next?**\n"
            ui_message += "- **[1]** Show updated holes list / choose another coverage hole.\n"
            ui_message += "- **[q]** Quit."
            return ui_message

        ui_message += "**What would you like to do next?**\n"
        ui_message += "- **[1]** Show updated holes list / pick another coverage hole.\n"
        ui_message += "- **[2]** Refine the current plan for the same hole.\n"
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

            if filename.lower().endswith(".bat"):
                language = "bat"
            elif filename.lower().endswith((".sv", ".svh", ".v")):
                language = "systemverilog"
            else:
                language = "text"

            ui_message += f"```{language}\n{file_content}\n```\n\n"

        ui_message += "---\n\n"
        ui_message += "**What is your decision?**\n"
        ui_message += "- **[1]** Approve code -> Save files and run Vivado.\n"
        ui_message += "- **[2]** Reject code -> Regenerate.\n"
        ui_message += "- **[q]** Quit."
        return ui_message

    return "Waiting for next action..."
