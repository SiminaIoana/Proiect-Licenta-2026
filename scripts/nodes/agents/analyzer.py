import os
import re
import time
import tiktoken

from llama_index.core import Settings

from state import AgentState
from config import PROJECT_CONFIG

from utils_files.phases import Phase
from utils_files.status import Status
from utils_files.prompt_utils import safe_format
from utils_files.coverage import (
    extract_coverage_holes,
    extract_coverage_percent,
    filter_log_for_hole,
)
from utils_files.file_ops import (
    read_rtl,
    read_env,
    read_simulation_log,
    read_run_script,
)
from utils_files.results_saving import get_index, save_agent_metrics
from scripts.utils_files.memory import save_analyzer_experience

from prompts.analyzer_prompt import (
    ANALYZER_SYSTEM_PROMPT,
    ANALYZER_ROOT_CAUSE_PROMPT,
    ANALYZER_PLAN_REFINEMENT_PROMPT,
)


# ============================================================
# Analyzer entry point
# ============================================================

def analyzer_node(state: AgentState):
    phase = state.get("phase", Phase.INIT)
    print(f"\n[ANALYZER]: Current phase -> [{phase}]")

    if phase == Phase.BUILD_HOLES_LIST:
        return build_holes_list(state)

    if phase == Phase.ROOT_CAUSE_ANALYSIS:
        return root_cause_analysis(state)

    if phase == Phase.PLAN_REFINEMENT:
        return refine_action_plan(state)

    if phase == Phase.ERROR_ANALYSIS:
        return error_analysis(state)

    if phase == Phase.COMPARE_RESULTS:
        return compare_results(state)

    print(f"[ANALYZER ERROR] Unknown phase: {phase}")
    return {"status": Status.FAILED}


# ============================================================
# General helpers
# ============================================================

def normalize_target_files(target_files: str) -> str:
    """
    Normalize target files produced by the LLM.

    This project uses MakeSVfile.bat, not run.sh. This function prevents
    nonexistent run-script names from reaching the generator.
    """
    if not target_files:
        return target_files

    normalized = []

    for raw_file in target_files.split(","):
        file_name = (
            raw_file.strip()
            .replace("`", "")
            .replace('"', "")
            .replace("'", "")
        )

        if not file_name:
            continue

        lower = file_name.lower()

        if lower in {
            "run.sh",
            "run_script.sh",
            "run.bat",
            "makefile",
            "makefile.bat",
        }:
            file_name = "MakeSVfile.bat"

        normalized.append(file_name)

    return ", ".join(dict.fromkeys(normalized))


def extract_target_files_from_plan(plan_text: str, fallback: str = "") -> str:
    match = re.search(
        r"TARGET_FILES?:\s*([a-zA-Z0-9_.,\s`'\"-]+)",
        plan_text or "",
        re.IGNORECASE,
    )

    if not match:
        return normalize_target_files(fallback)

    target_files = (
        match.group(1)
        .replace("`", "")
        .replace('"', "")
        .replace("'", "")
        .strip()
    )

    return normalize_target_files(target_files)


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "N/A":
            return default
        return float(value)
    except Exception:
        return default


# ============================================================
# Build holes list
# ============================================================

def build_holes_list(state: AgentState):
    fcov_path = state.get("fcov_report_path", "")
    print(f"[DEBUG] fcov_report_path = '{fcov_path}'")

    current_coverage = extract_coverage_percent(fcov_path)
    print(f"[ANALYZER]: Current coverage score = {current_coverage}%")

    raw_holes = extract_coverage_holes(fcov_path)
    status = Status.SUCCESS
    holes_list = []

    if raw_holes.startswith("ERROR:"):
        print(f"[ANALYZER ERROR]: {raw_holes}")
        status = Status.FAILED

    elif "No obvious coverage holes" in raw_holes or raw_holes.strip() == "":
        print("[ANALYZER]: No holes found.")
        holes_list = []

    else:
        holes_lines = [
            line.strip()
            for line in raw_holes.split("\n")
            if line.strip().startswith("-")
        ]

        holes_list = [
            {"id": idx + 1, "description": line}
            for idx, line in enumerate(holes_lines)
        ]

        print(f"[ANALYZER]: Found {len(holes_list)} holes.")

    return {
        "coverage_holes": raw_holes,
        "holes_list": holes_list,
        "coverage_value": current_coverage,
        "status": status,
    }


# ============================================================
# Root cause analysis
# ============================================================

def root_cause_analysis(state: AgentState):
    start_time = time.time()

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")

    current_hole = state.get("current_hole", {})
    hole_description = current_hole.get("description", "Unknown Hole")
    current_coverage = state.get("coverage_value", 0.0)

    print(f"[ANALYZER]: Investigating root cause for -> {hole_description}")

    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
    env_code = read_env(tb_dir)
    run_script = read_run_script(PROJECT_CONFIG.get("bat_file_path", ""))
    sim_log = read_simulation_log(state.get("simulation_log_path", ""))

    specs = state.get("dut_specs", "")
    uvm_rules = state.get("uvm_rules", "")
    user_feedback = state.get("user_feedback", "")

    print(f"[DEBUG ANALYZER] user_feedback='{user_feedback}'")

    if user_feedback:
        print(f"[ANALYZER]: Incorporating user feedback into analysis: {user_feedback}")

    sim_log_filtered = filter_log_for_hole(sim_log, hole_description)

    # ---- SAVING EXPERIENCE -----
    ltm_path = os.path.join("..", "results", "LTM_analyzer")
    past_experience = ""

    try:
        if os.path.exists(ltm_path) and any(os.path.isfile(os.path.join(ltm_path, f)) for f in os.listdir(ltm_path)):
            index_ltm = get_index(ltm_path, "../DOCS/storage_ltm_analyzer/", "Analyzer LTM")
            if index_ltm:
                query_engine = index_ltm.as_query_engine(similarity_top_k=1)
                memory_response = query_engine.query(f"How did we fix a coverage hole like: {hole_description}")
                past_experience = str(memory_response)
                print(f"[ANALYZER INFO]: Retrieved past experience from LTM: {past_experience}")
        else:
            print(f"[ANALYZER INFO]: No past experiences found in {ltm_path}. Starting from scratch.")
            past_experience = "No relevant past experience found."
    except Exception as e:
        print(f"[ANALYZER WARNING]: Memory indexing skipped: {e}")
        past_experience = "No relevant past experience found."

    memory_section = (
        f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}"
        if past_experience
        else ""
    )

    prompt = safe_format(
        ANALYZER_ROOT_CAUSE_PROMPT,
        current_coverage=current_coverage,
        hole_description=hole_description,
        sim_log_filtered=sim_log_filtered,
        rtl_code=rtl_code,
        env_code=env_code,
        run_script=run_script,
        specs=specs,
        uvm_rules=uvm_rules,
        past_experience=memory_section,
        user_feedback=user_feedback,
    )

    full_prompt = ANALYZER_SYSTEM_PROMPT + "\n\n" + prompt

    response = llm.complete(full_prompt)
    response_text = response.text.strip()

    prompt_tokens = len(encoding.encode(full_prompt))
    response_tokens = len(encoding.encode(response_text))
    total_tokens = state.get("iteration_tokens", 0) + prompt_tokens + response_tokens

    target_file = extract_target_files_from_plan(response_text, "unknown_file.sv")

    duration = round(time.time() - start_time, 2)

    save_agent_metrics(
        agent_name="analyzer",
        phase=str(state.get("phase", "")),
        hole_description=hole_description,
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        total_tokens=prompt_tokens + response_tokens,
        duration_seconds=duration,
        status=Status.SUCCESS.value,
        notes=f"target_file={target_file}",
    )

    print(f"[DEBUG] Extracted TARGET_FILES: {target_file}")

    return {
        "root_cause_hole": "LLM Analysis Generated",
        "action_plan": response_text,
        "target_file": target_file,
        "iteration_tokens": total_tokens,
        "status": Status.SUCCESS,
    }

# ============================================================
# Plan refinement
# ============================================================

def refine_action_plan(state: AgentState):
    print("\n[ANALYZER]: Refining current plan using user feedback...")

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")

    current_hole = state.get("current_hole", {})
    hole_description = current_hole.get("description", "")

    current_plan = state.get("action_plan", "")
    user_feedback = state.get("user_feedback", "")
    uvm_rules = state.get("uvm_rules", "")

    prompt = safe_format(
        ANALYZER_PLAN_REFINEMENT_PROMPT,
        hole_description=hole_description,
        current_plan=current_plan,
        user_feedback=user_feedback,
        uvm_rules=uvm_rules,
    )

    full_prompt = ANALYZER_SYSTEM_PROMPT + "\n\n" + prompt

    response = llm.complete(full_prompt)
    response_text = response.text.strip()

    prompt_tokens = len(encoding.encode(full_prompt))
    response_tokens = len(encoding.encode(response_text))

    target_file = extract_target_files_from_plan(
        response_text,
        state.get("target_file", ""),
    )

    return {
        "root_cause_hole": response_text,
        "action_plan": response_text,
        "target_file": target_file,
        "iteration_tokens": state.get("iteration_tokens", 0) + prompt_tokens + response_tokens,
        "status": Status.SUCCESS,
    }


# ============================================================
# Error analysis
# ============================================================

def error_analysis(state: AgentState):
    print("[ANALYZER]: Error detected. Preparing data for human review/generator fix.")
    return {
        "status": Status.FAILED,
    }


# ============================================================
# Result comparison helpers
# ============================================================

def normalize_hole_description(description: str) -> str:
    text = (description or "").lower()
    text = re.sub(r"^-\s*", "", text)
    text = re.sub(r"['`\"]", "", text)
    text = re.sub(r"[^a-z0-9_\[\]\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_coverage_object(description: str) -> str:
    quoted = re.search(r"'([^']+)'", description or "")
    if quoted:
        return quoted.group(1).strip().lower()

    normalized = normalize_hole_description(description)
    object_match = re.search(
        r"\b(?:coverpoint|cross)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        normalized,
    )

    if object_match:
        return object_match.group(1).strip().lower()

    return ""


def parse_action_plan_field(action_plan: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(action_plan or "")
    return match.group(1).strip() if match else ""


def is_coverage_model_strategy(strategy: str) -> bool:
    strategy_upper = (strategy or "").upper()
    return any(
        marker in strategy_upper
        for marker in ["MODIFY_BINS", "MODIFY_COVERPOINT", "MODIFY_CROSS"]
    )


def is_same_logical_hole(selected_hole: str, updated_hole: str) -> bool:
    selected_norm = normalize_hole_description(selected_hole)
    updated_norm = normalize_hole_description(updated_hole)

    if not selected_norm or not updated_norm:
        return False

    if selected_norm == updated_norm:
        return True

    if selected_norm in updated_norm or updated_norm in selected_norm:
        return True

    selected_object = extract_coverage_object(selected_hole)
    updated_object = extract_coverage_object(updated_hole)

    if selected_object and selected_object == updated_object:
        return True

    return False


def find_matching_hole_in_updated_list(selected_hole: str, updated_holes_list: list):
    for hole in updated_holes_list:
        updated_description = hole.get("description", "")
        if is_same_logical_hole(selected_hole, updated_description):
            return hole

    return None


def classify_fix_result(
    old_coverage: float,
    new_coverage: float,
    selected_hole: str,
    previous_holes_list: list,
    updated_holes_list: list,
    holes_parse_failed: bool,
    strategy: str,
) -> tuple[str, dict]:
    matching_hole = find_matching_hole_in_updated_list(selected_hole, updated_holes_list)
    selected_still_present = matching_hole is not None

    details = {
        "matching_hole": matching_hole,
        "selected_still_present": selected_still_present,
    }

    if holes_parse_failed:
        return "UNCONFIRMED", details

    previous_count = len(previous_holes_list or [])
    updated_count = len(updated_holes_list or [])

    if new_coverage < old_coverage:
        return "REGRESSION", details

    if updated_count > previous_count and selected_still_present and new_coverage <= old_coverage:
        return "REGRESSION", details

    if selected_hole and not selected_still_present:
        return "SUCCESS_FIXED_HOLE", details

    if selected_still_present and is_coverage_model_strategy(strategy):
        return "DIAGNOSTIC_IMPROVEMENT_ONLY", details

    if selected_still_present and new_coverage > old_coverage:
        return "PARTIAL_IMPROVEMENT", details

    if selected_still_present:
        return "NOT_FIXED", details

    return "UNCONFIRMED", details


def build_detailed_result_message(
    category: str,
    old_coverage: float,
    new_coverage: float,
    selected_hole: str,
    classification_details: dict,
    strategy: str,
    code_action: str,
    target_files: str,
    updated_holes_list: list,) -> str:
    
    matching_hole = classification_details.get("matching_hole")
    selected_still_present = classification_details.get("selected_still_present")

    if selected_still_present is True:
        presence_text = "Yes"
    elif selected_still_present is False:
        presence_text = "No"
    else:
        presence_text = "Unconfirmed"

    if matching_hole:
        remaining_text = matching_hole.get("description", "")
    elif updated_holes_list:
        remaining_text = updated_holes_list[0].get("description", "")
    else:
        remaining_text = "No matching updated hole was found."

    if category == "SUCCESS_FIXED_HOLE":
        outcome = (
            "The selected coverage hole is no longer present in the updated holes list. "
            "The fix is confirmed for this hole."
        )
        recommendation = (
            "Show the updated holes list and continue with the next remaining coverage hole."
        )

    elif category == "PARTIAL_IMPROVEMENT":
        outcome = (
            "Total coverage improved, but the selected coverage hole is still present."
        )
        recommendation = (
            "Retry the same hole with a stronger or different strategy."
        )

    elif category == "DIAGNOSTIC_IMPROVEMENT_ONLY":
        outcome = (
            "The coverage model appears more readable or actionable, but the selected "
            "logical scenario is still uncovered."
        )
        recommendation = (
            "Create or modify a sequence/test to target the now-explicit uncovered bins."
        )

    elif category == "NOT_FIXED":
        outcome = "The fix did not resolve the selected coverage hole."
        recommendation = "Retry the same hole or choose a different strategy."

    elif category == "REGRESSION":
        outcome = "Coverage regressed or the updated holes list became worse after the fix."
        recommendation = "Rollback to the previous code version."

    else:
        outcome = (
            "Coverage changed, but selected hole closure could not be confirmed from "
            "the updated holes list."
        )
        recommendation = (
            "Review the generated coverage report, then retry or rollback if the result is unsafe."
        )

    changed_parts = []
    if strategy:
        changed_parts.append(f"- Strategy: {strategy}")
    if code_action:
        changed_parts.append(f"- Code action: {code_action}")
    if target_files:
        changed_parts.append(f"- Target files: {target_files}")

    if not changed_parts:
        changed_parts.append("- Strategy/code action/target files were not available in the action plan.")

    return (
        f"**Result category:** {category}\n\n"
        f"**Coverage:** {old_coverage}% -> {new_coverage}%\n\n"
        f"**Selected hole before fix:**\n"
        f"{selected_hole or 'Unknown selected hole'}\n\n"
        f"**Selected hole still present:** {presence_text}\n\n"
        f"**Outcome:** {outcome}\n\n"
        f"**What changed:**\n"
        + "\n".join(changed_parts)
        + "\n\n"
        f"**Updated uncovered item to inspect:**\n"
        f"{remaining_text}\n\n"
        f"**Recommended next step:** {recommendation}"
    )


# ============================================================
# Compare results
# ============================================================

def compare_results(state: AgentState):
    print("[ANALYZER]: Comparing new FCOV report with previous state...")

    fcov_path = state.get("fcov_report_path", "")
    new_holes_str = extract_coverage_holes(fcov_path)

    new_coverage = safe_float(extract_coverage_percent(fcov_path))
    old_coverage = safe_float(
        state.get("previous_coverage", state.get("coverage_value", 0.0))
    )

    target_hole = state.get("current_hole", {}).get("description", "")
    action_plan = state.get("action_plan", "")

    strategy = parse_action_plan_field(action_plan, "CHOSEN STRATEGY")
    code_action = parse_action_plan_field(action_plan, "CODE_ACTION")

    target_files = normalize_target_files(
        parse_action_plan_field(action_plan, "TARGET_FILES") or state.get("target_file", "")
    )

    previous_holes_list = state.get("holes_list", [])

    holes_parse_failed = new_holes_str.startswith("ERROR:")

    holes_lines = [
        line.strip()
        for line in new_holes_str.split("\n")
        if line.strip().startswith("-")
    ]

    updated_list = [
        {"id": idx + 1, "description": line}
        for idx, line in enumerate(holes_lines)
    ]

    category, details = classify_fix_result(
        old_coverage=old_coverage,
        new_coverage=new_coverage,
        selected_hole=target_hole,
        previous_holes_list=previous_holes_list,
        updated_holes_list=updated_list,
        holes_parse_failed=holes_parse_failed,
        strategy=strategy,
    )

    if category == "SUCCESS_FIXED_HOLE":
        success_code = state.get("generated_code", "")
        save_analyzer_experience(target_hole, action_plan, success_code)

    analysis_result = build_detailed_result_message(
        category=category,
        old_coverage=old_coverage,
        new_coverage=new_coverage,
        selected_hole=target_hole,
        classification_details=details,
        strategy=strategy,
        code_action=code_action,
        target_files=target_files,
        updated_holes_list=updated_list,
    )

    return {
        "coverage_holes": new_holes_str,
        "holes_list": updated_list,
        "root_cause_hole": analysis_result,
        "coverage_value": new_coverage,
        "previous_coverage": new_coverage,
        "status": Status.SUCCESS,
    }
