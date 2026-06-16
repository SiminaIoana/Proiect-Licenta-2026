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
    technical_justification = extract_plan_section(plan, "TECHNICAL_JUSTIFICATION")
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
    if technical_justification:
        msg += "\n\n**Technical justification:**\n"
        msg += technical_justification
        
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
        analysis = (
            state.get("error_analysis", "")
            or state.get("root_cause_hole", "")
            or "No detailed error analysis was generated."
        )

        auto_fix_allowed = state.get("auto_fix_allowed", True)
        has_rollback = bool(state.get("rollback_files", {}))

        error_preview = errors[:3000]

        ui_message += "### Vivado/XSim Error Analysis\n\n"

        ui_message += "**Raw error:**\n"
        ui_message += f"```text\n{error_preview}\n```\n\n"

        ui_message += "**Analyzer explanation:**\n"
        ui_message += f"{analysis}\n\n"

        ui_message += "---\n\n"
        ui_message += "**Choose next action:**\n"

        if auto_fix_allowed:
            ui_message += "- **[1]** Generate a corrected code fix based on this error analysis.\n"
        else:
            ui_message += "- **[1]** Not recommended: this error is probably not safe for automatic code fixing.\n"

        if has_rollback:
            ui_message += "- **[2]** Rollback to the previous code version.\n"
        else:
            ui_message += "- **[2]** Rollback unavailable: no checkpoint exists for this run.\n"

        ui_message += "- **[q]** Quit and fix manually."

        return ui_message

    if phase == Phase.SELECT_HOLE:
        holes_list = state.get("holes_list", [])

        if not holes_list:
            ui_message += "### Analysis Complete\n\n"
            ui_message += "**No coverage holes detected.**\n\n"
            ui_message += "Press **[q]** to quit."
            return ui_message

        ui_message += "### Coverage Analysis Results\n\n"
        ui_message += f"The analyzer identified **{len(holes_list)}** coverage holes.\n\n"

        ui_message += "| ID | Source | Item | Missing |\n"
        ui_message += "| :---: | :--- | :--- | :--- |\n"

        for hole in holes_list:
            hole_id = hole.get("id", "?")

            cg = hole.get("covergroup_short", "unknown")
            idx = hole.get("instance_index", "")
            source = f"{cg}#{idx}" if idx else cg

            kind = hole.get("kind", "item")
            kind_label = "CP" if kind == "coverpoint" else "Cross" if kind == "cross" else kind

            name = hole.get("name", "unknown")

            expected = hole.get("expected", 0) or 0
            uncovered = hole.get("uncovered", 0) or 0
            bins = hole.get("bins") or []

            if bins and len(bins) <= 2:
                missing = ", ".join(bins)
            elif bins and len(bins) > 2:
                missing = f"{uncovered}/{expected} bins"
            else:
                missing = f"{uncovered}/{expected} bins"

            ui_message += (
                f"| **{hole_id}** | `{source}` | "
                f"{kind_label} `{name}` | {missing} |\n"
            )

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

            if state.get("dut_change_analysis_result", ""):
                ui_message += "### DUT Change Impact Analysis\n\n"
                ui_message += f"{state.get('dut_change_analysis_result', '')}\n\n"
                ui_message += "---\n\n"

            ui_message += "**Optional experimental feature:**\n"
            ui_message += (
                "You can describe a future DUT modification, and the system will suggest "
                "which UVM testbench components should be updated.\n\n"
            )

            ui_message += "**Example input:**\n"
            ui_message += (
                "`dut: FIFO depth changes to 16 and new almost_full/almost_empty signals are added`\n\n"
            )

            ui_message += "**What would you like to do next?**\n"
            ui_message += "- **[1]** Start DUT change impact analysis.\n"
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
