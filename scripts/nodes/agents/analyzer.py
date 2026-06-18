import os
import re
import time
import tiktoken
from state import AgentState
from config import PROJECT_CONFIG
from utils_files.phases import Phase
from utils_files.status import Status
from llama_index.core import Settings
from utils_files.file_ops import safe_format
from utils_files.validator import validate_action_plan
from scripts.utils_files.memory import save_analyzer_experience
from utils_files.results_saving import get_index, save_agent_metrics
from utils_files.coverage import (
    build_coverage_holes_list,
    build_detailed_result_message,
    extract_coverage_holes,
    extract_coverage_percent,
    classify_fix_result,
    filter_log_for_hole,
    safe_float,
)
from utils_files.file_ops import (
    read_rtl,
    read_env,
    read_run_script,
    read_simulation_log,
    build_source_error_context,
)
from prompts.analyzer_prompt import (
    ANALYZER_SYSTEM_PROMPT,
    ANALYZER_ROOT_CAUSE_PROMPT,
    ANALYZER_PLAN_REFINEMENT_PROMPT,
    ANALYZER_DUT_CHANGE_IMPACT_PROMPT,
)
from utils_files.vivado_utils import (
    build_error_fix_plan,
    classify_vivado_error,
    guess_target_files_from_error,
    extract_relevant_error_lines,
)

"""
Analyzer node for the coverage-closure workflow.

This module extracts coverage holes, analyzes selected holes, refines action
plans, analyzes Vivado/XSim errors and compares coverage results after a fix.
"""
# Analyzer entry point
def analyzer_node(state: AgentState):
    """
    Routes Analyzer execution based on the current workflow phase.
    """
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
    
    if phase == Phase.DUT_CHANGE_ANALYSIS:
        return dut_change_impact_analysis(state)

    print(f"[ANALYZER ERROR] Unknown phase: {phase}")
    return {"status": Status.FAILED}


def normalize_target_files(target_files: str) -> str:
    """
    Normalizes target files produced by the LLM.

    This project uses MakeSVfile.bat.This function prevents
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


def build_holes_list(state: AgentState):
    """
    Extracts the current coverage score and uncovered items from the XCRG report.
    """
    fcov_path = state.get("fcov_report_path", "")
    current_coverage = extract_coverage_percent(fcov_path)
    print(f"[DEBUG] fcov_report_path = '{fcov_path}'")
    print(f"[ANALYZER]: Current coverage score = {current_coverage}%")

    # Build the raw text version and the structured list used by the UI
    raw_holes = extract_coverage_holes(fcov_path)
    holes_list = build_coverage_holes_list(fcov_path)

    status = Status.SUCCESS

    if raw_holes.startswith("ERROR:"):
        print(f"[ANALYZER ERROR]: {raw_holes}")
        status = Status.FAILED
        holes_list = []

    elif not holes_list:
        print("[ANALYZER]: No holes found.")

    else:
        print(f"[ANALYZER]: Found {len(holes_list)} holes.")

    return {
        "coverage_holes": raw_holes,
        "holes_list": holes_list,
        "coverage_value": current_coverage,
        "status": status,
    }


def root_cause_analysis(state: AgentState):
    """
    Analyzes the selected coverage hole and generates an action plan.
    The prompt combines the selected hole, simulation log, RTL/testbench code, RAG context, UVM rules, user feedback and optional past experience.
    """
    start_time = time.time()
    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")

    current_hole = state.get("current_hole", {})
    hole_description = current_hole.get("description", "Unknown Hole")
    current_coverage = state.get("coverage_value", 0.0)

    print(f"[ANALYZER]: Investigating root cause for -> {hole_description}")

    # Read the project context needed by the Analyzer prompt.
    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
    env_code = read_env(tb_dir)
    run_script = read_run_script(PROJECT_CONFIG.get("bat_file_path", ""))
    sim_log = read_simulation_log(state.get("simulation_log_path", ""))

    specs = state.get("dut_specs", "")
    uvm_rules = state.get("uvm_rules", "")
    #print(f"dut_specs length={len(state.get('dut_specs', ''))}")
    #print(f"uvm_rules length={len(state.get('uvm_rules', ''))}")
    user_feedback = state.get("user_feedback", "")

    print(f"[DEBUG ANALYZER] user_feedback='{user_feedback}'")

    if user_feedback:
        print(f"[ANALYZER]: Incorporating user feedback into analysis: {user_feedback}")
    # Keep only log information that is relevant for the selected coverage hole.
    sim_log_filtered = filter_log_for_hole(sim_log, hole_description)

    # ---- SAVING EXPERIENCE -----
    use_memory = PROJECT_CONFIG.get("use_memory", True)
    ltm_path = os.path.join("..", "results", "LTM_analyzer")
    past_experience = ""

    if use_memory:
        try:
            if os.path.exists(ltm_path) and any(os.path.isfile(os.path.join(ltm_path, f)) for f in os.listdir(ltm_path)):
                index_ltm = get_index(ltm_path, "../DOCS/storage_ltm_analyzer/", "Analyzer LTM")
                if index_ltm:
                    query_engine = index_ltm.as_query_engine(similarity_top_k=2)
                    memory_response = query_engine.query(f"How did we fix a coverage hole like: {hole_description}")
                    past_experience = str(memory_response)
                    print(f"[ANALYZER INFO]: Retrieved past experience from LTM: {past_experience}")
            else:
                print(f"[ANALYZER INFO]: No past experiences found in {ltm_path}. Starting from scratch.")
                past_experience = "No relevant past experience found."
        except Exception as e:
            print(f"[ANALYZER WARNING]: Memory indexing skipped: {e}")
            past_experience = "No relevant past experience found."
    else:
        print("[ANALYZER INFO]: Memory disabled for this run.")
        past_experience = ""

    memory_section = (
        f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}\n"
        if past_experience
        else ""
    )

    rag_context_tokens = len(encoding.encode(specs)) + len(encoding.encode(uvm_rules))
    # print("[ANALYZER DEBUG] rag_context_tokens in analyzer prompt =", rag_context_tokens)
    
    # Build the final prompt
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
    # Validate the language model plan before sending it.
    validation = validate_action_plan(response_text, state)
    response_text = validation.plan_text
    target_file = validation.target_files

    if validation.warnings:
        print("[PLAN VALIDATOR] Corrections/warnings:")
        for warning in validation.warnings:
            print(f" - {warning}")

    prompt_tokens = len(encoding.encode(full_prompt))
    response_tokens = len(encoding.encode(response_text))
    total_tokens = state.get("iteration_tokens", 0) + prompt_tokens + response_tokens
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


def refine_action_plan(state: AgentState):
    """
    Refines the current action plan using user feedback.
    """
    print("\n[ANALYZER]: Refining current plan using user feedback...")

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")
    current_hole = state.get("current_hole", {})
    hole_description = current_hole.get("description", "")
    current_plan = state.get("action_plan", "")
    user_feedback = state.get("user_feedback", "")
    uvm_rules = state.get("uvm_rules", "")

    # Build the plan
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
    # The refined plan is validated using the same validator.
    validation = validate_action_plan(response_text, state)
    response_text = validation.plan_text
    target_file = validation.target_files

    if validation.warnings:
        print("[PLAN VALIDATOR] Warnings after refinement:")
        for warning in validation.warnings:
            print(f" - {warning}")

    prompt_tokens = len(encoding.encode(full_prompt))
    response_tokens = len(encoding.encode(response_text))

    return {
        "root_cause_hole": response_text,
        "action_plan": response_text,
        "target_file": target_file,
        "iteration_tokens": state.get("iteration_tokens", 0) + prompt_tokens + response_tokens,
        "status": Status.SUCCESS,
    }


def error_analysis(state: AgentState):
    """
    Analyzes a Vivado/XSim failure and builds a correction plan.
    """
    print("[ANALYZER]: Error detected. Analyzing Vivado/XSim failure.")

    raw_error = state.get("compilation_error", "")
    sim_log = read_simulation_log(state.get("simulation_log_path", ""))
    # Combine Checker error output with the simulation log.
    combined_error_text = raw_error + "\n\n" + sim_log
    evidence = extract_relevant_error_lines(combined_error_text)

    # Helps the user inspect the exact lines reported by Vivado.
    source_context, source_target_files = build_source_error_context(combined_error_text)
    classification = classify_vivado_error(combined_error_text)
    category = classification["category"]
    recommendation = classification["recommendation"]
    auto_fix_allowed = classification["auto_fix_allowed"]
    target_files = source_target_files or guess_target_files_from_error(raw_error, state)

    analysis_message = (
        f"**Error category:** `{category}`\n\n"
        f"**What probably went wrong:**\n"
        f"{recommendation}\n\n"
        f"**Likely affected files:** `{target_files}`\n\n"
        f"**Relevant evidence from Vivado/XSim logs:**\n"
        f"```text\n{evidence[:2000] or raw_error[:2000] or 'No detailed error lines were captured.'}\n```\n\n"
    )

    if source_context:
        analysis_message += (
        "**Source context around the reported error line:**\n"
        f"```systemverilog\n{source_context[:3000]}\n```\n\n"
        )

    if auto_fix_allowed:
        analysis_message += (
            "**Recommended action:** let the Generator create a minimal corrected version "
            "of the last generated code, then review it before injection."
        )
    else:
        analysis_message += (
            "**Recommended action:** fix this manually or rollback. This error is probably "
            "not safely fixable by generated SystemVerilog code."
        )

    action_plan = build_error_fix_plan(
        category=category,
        target_files=target_files,
        recommendation=recommendation,
        evidence=(evidence + "\n\nSOURCE CONTEXT:\n" + source_context) if source_context else (evidence or raw_error),
    )

    return {
        "root_cause_hole": analysis_message,
        "error_analysis": analysis_message,
        "error_category": category,
        "auto_fix_allowed": auto_fix_allowed,
        "action_plan": action_plan,
        "target_file": target_files,
        "status": Status.FAILED,
    }


def parse_action_plan_field(action_plan: str, field_name: str) -> str:
    """
    Extracts one named field from the generated action plan.
    """
    pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(action_plan or "")
    return match.group(1).strip() if match else ""


def compare_results(state: AgentState):
    """
    Compares the new coverage report with the previous state.
    Options: Fixed, partially improved, not fixed, regression or unconfirmed
    """
    print("[ANALYZER]: Comparing new FCOV report with previous state...")

    # Parses the updated coverage report after the generated fix
    fcov_path = state.get("fcov_report_path", "")
    new_holes_str = extract_coverage_holes(fcov_path)
    updated_list = build_coverage_holes_list(fcov_path)

    new_coverage = safe_float(extract_coverage_percent(fcov_path))
    old_coverage = safe_float(state.get("previous_coverage", state.get("coverage_value", 0.0)))

    target_hole_obj = state.get("current_hole", {})
    target_hole_description = target_hole_obj.get("description", "")
    action_plan = state.get("action_plan", "")

    strategy = parse_action_plan_field(action_plan, "CHOSEN STRATEGY")
    code_action = parse_action_plan_field(action_plan, "CODE_ACTION")

    target_files = normalize_target_files(parse_action_plan_field(action_plan, "TARGET_FILES") or state.get("target_file", ""))

    previous_holes_list = state.get("holes_list", [])
    holes_parse_failed = new_holes_str.startswith("ERROR:")

    category, details = classify_fix_result(
        old_coverage=old_coverage,
        new_coverage=new_coverage,
        selected_hole=target_hole_obj,
        previous_holes_list=previous_holes_list,
        updated_holes_list=updated_list,
        holes_parse_failed=holes_parse_failed,
        strategy=strategy,
    )

    if category == "SUCCESS_FIXED_HOLE":
        success_code = state.get("generated_code", "")
        save_analyzer_experience(target_hole_description, action_plan, success_code)

    analysis_result = build_detailed_result_message(
        category=category,
        old_coverage=old_coverage,
        new_coverage=new_coverage,
        selected_hole=target_hole_description,
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


def dut_change_impact_analysis(state: AgentState):
    """
    Analysis-only feature. -- EXPERIMENTAL ONLY --

    This function explains what parts of the UVM testbench may need to be updated after a DUT modification.
    """
    print("[ANALYZER]: Running DUT change impact analysis...")

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")
    start_time = time.time()

    new_dut_specs = state.get("new_dut_specs", "")
    old_dut_specs = state.get("dut_specs", "")
    uvm_rules = state.get("uvm_rules", "")

    rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
    env_code = read_env(PROJECT_CONFIG.get("tb_dir", ""))
    run_script = read_run_script(PROJECT_CONFIG.get("bat_file_path", ""))

    prompt = safe_format(
        ANALYZER_DUT_CHANGE_IMPACT_PROMPT,
        old_dut_specs=old_dut_specs,
        new_dut_specs=new_dut_specs,
        rtl_code=rtl_code,
        env_code=env_code,
        run_script=run_script,
        uvm_rules=uvm_rules,
    )

    full_prompt = ANALYZER_SYSTEM_PROMPT + "\n\n" + prompt

    response = llm.complete(full_prompt)
    response_text = response.text.strip()

    prompt_tokens = len(encoding.encode(full_prompt))
    response_tokens = len(encoding.encode(response_text))
    duration = round(time.time() - start_time, 2)

    save_agent_metrics(
        agent_name="analyzer",
        phase=str(state.get("phase", "")),
        hole_description="DUT change impact analysis",
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        total_tokens=prompt_tokens + response_tokens,
        duration_seconds=duration,
        status=Status.SUCCESS.value,
        notes="analysis_only=true",
    )

    return {
        "dut_change_analysis_result": response_text,
        "root_cause_hole": response_text,
        "status": Status.SUCCESS,
    }