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
    build_coverage_holes_list,
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
from utils_files.validator import validate_action_plan
from prompts.analyzer_prompt import (
    ANALYZER_SYSTEM_PROMPT,
    ANALYZER_ROOT_CAUSE_PROMPT,
    ANALYZER_PLAN_REFINEMENT_PROMPT,
    ANALYZER_DUT_CHANGE_IMPACT_PROMPT,
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
    
    if phase == Phase.DUT_CHANGE_ANALYSIS:
        return dut_change_impact_analysis(state)

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
    use_memory = PROJECT_CONFIG.get("use_memory", True)

    ltm_path = os.path.join("..", "results", "LTM_analyzer")
    past_experience = ""

    if use_memory:
        try:
            if os.path.exists(ltm_path) and any(os.path.isfile(os.path.join(ltm_path, f)) for f in os.listdir(ltm_path)):
                index_ltm = get_index(ltm_path, "../DOCS/storage_ltm_analyzer/", "Analyzer LTM")
                if index_ltm:
                    query_engine = index_ltm.as_query_engine(similarity_top_k=1)
                    memory_response = query_engine.query(
                    f"How did we fix a coverage hole like: {hole_description}"
                    )
                    past_experience = str(memory_response)
                    print(f"[ANALYZER INFO]: Retrieved past experience from LTM: {past_experience}")
            else:
                print(f"[ANALYZER INFO]: No past experiences found in {ltm_path}. Starting from scratch.")
                past_experience = "No relevant past experience found."
        except Exception as e:
            print(f"[ANALYZER WARNING]: Memory indexing skipped: {e}")
            past_experience = "No relevant past experience found."
    else:
        print("[ANALYZER INFO]: Memory disabled for this experimental run.")
        past_experience = ""

    memory_section = (
        f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}\n"
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


# ============================================================
# Error analysis
# ============================================================

def extract_relevant_error_lines(text: str, max_lines: int = 30) -> str:
    """
    Extracts the most relevant lines from Vivado/XSim/UVM logs.
    Keeps the function deterministic and simple for demo stability.
    """
    if not text:
        return ""

    markers = [
        "ERROR:",
        "FATAL:",
        "CRITICAL WARNING:",
        "UVM_ERROR",
        "UVM_FATAL",
        "syntax error",
        "Syntax error",
        "FAILED",
        "failed",
        "xvlog",
        "xelab",
        "xsim",
    ]

    lines = text.splitlines()
    selected = []

    for i, line in enumerate(lines):
        if any(marker in line for marker in markers):
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            selected.extend(lines[start:end])

    # remove duplicates, keep order
    clean = []
    seen = set()

    for line in selected:
        if line not in seen:
            clean.append(line)
            seen.add(line)

    if clean:
        return "\n".join(clean[:max_lines])

    non_empty = [line for line in lines if line.strip()]
    return "\n".join(non_empty[-max_lines:])


def classify_vivado_error(error_text: str) -> dict:
    """
    Classifies the error into a small number of categories.
    This is safer than asking the LLM to guess everything.
    """
    text = (error_text or "").lower()

    if "not recognized" in text or "settings64.bat" in text or "vivado path" in text:
        return {
            "category": "SYSTEM_PATH_ERROR",
            "auto_fix_allowed": False,
            "recommendation": (
                "This looks like an environment problem. Check the Vivado path, "
                "settings64.bat, and whether xvlog/xelab/xsim are available."
            ),
        }

    if "coverage report" in text or "xcrg" in text or "coverage report missing" in text:
        return {
            "category": "COVERAGE_REPORT_ERROR",
            "auto_fix_allowed": False,
            "recommendation": (
                "Vivado may have run, but the coverage report was not generated or "
                "could not be parsed. Check the xcrg command and coverage database path."
            ),
        }

    if "xvlog" in text or "syntax error" in text or "near" in text:
        return {
            "category": "COMPILE_SYNTAX_ERROR",
            "auto_fix_allowed": True,
            "recommendation": (
                "The injected SystemVerilog/UVM code likely contains a syntax error "
                "or an invalid declaration. The generated code should be corrected."
            ),
        }

    if "xelab" in text:
        return {
            "category": "ELABORATION_ERROR",
            "auto_fix_allowed": True,
            "recommendation": (
                "The code compiled, but elaboration failed. Check class names, "
                "factory registration, include order, top module, and UVM test names."
            ),
        }

    uvm_error_match = re.search(r"UVM_ERROR\s*:\s*(\d+)", error_text or "")
    uvm_fatal_match = re.search(r"UVM_FATAL\s*:\s*(\d+)", error_text or "")

    uvm_error_count = int(uvm_error_match.group(1)) if uvm_error_match else 0
    uvm_fatal_count = int(uvm_fatal_match.group(1)) if uvm_fatal_match else 0

    if (
        uvm_error_count > 0
        or uvm_fatal_count > 0
        or "mismatch" in text
    ):
        return {
            "category": "SIMULATION_RUNTIME_ERROR",
            "auto_fix_allowed": True,
            "recommendation": (
                "The simulation ran but reported a UVM/runtime failure. Check the "
                "generated sequence/test behavior and scoreboard expectations."
                ),
        }

    return {
        "category": "UNKNOWN_VIVADO_ERROR",
        "auto_fix_allowed": True,
        "recommendation": (
            "The error could not be classified safely. Review the relevant Vivado/XSim "
            "log lines and regenerate only a minimal fix."
        ),
    }


def guess_target_files_from_error(error_text: str, state: AgentState) -> str:
    """
    Guesses likely affected files using:
    - current target_file from previous plan;
    - // FILE markers from generated code;
    - file names mentioned in the error.
    """
    known_files = [
        "transaction.sv",
        "sequence.sv",
        "test.sv",
        "subscriber.sv",
        "monitor.sv",
        "driver.sv",
        "scoreboard.sv",
        "agent.sv",
        "environment.sv",
        "top.sv",
        "MakeSVfile.bat",
    ]

    text = (error_text or "").lower()
    generated_code = state.get("generated_code", "")
    current_target = state.get("target_file", "")

    candidates = []

    if current_target and "unknown" not in current_target.lower():
        candidates.extend([f.strip() for f in current_target.split(",") if f.strip()])

    for match in re.finditer(r"FILE:\s*([a-zA-Z0-9_.-]+)", generated_code):
        candidates.append(match.group(1).strip())

    for file_name in known_files:
        if file_name.lower() in text:
            candidates.append(file_name)

    candidates = list(dict.fromkeys(candidates))

    if candidates:
        return ", ".join(candidates)

    return "sequence.sv, test.sv, subscriber.sv, MakeSVfile.bat"

def extract_error_file_locations(error_text: str) -> list[dict]:
    """
    Extracts file and line references from Vivado/XSim errors.

    Example:
    ERROR: [VRFC 10-4982] syntax error near 'start_item' [..\\TB-FIFO/sequence.sv:35]
    """

    locations = []

    pattern = re.compile(
        r"\[([^\[\]]+\.(?:sv|v|svh|vh|bat)):(\d+)\]",
        re.IGNORECASE,
    )

    for match in pattern.finditer(error_text or ""):
        raw_path = match.group(1).replace("\\", "/")
        line_no = int(match.group(2))
        file_name = os.path.basename(raw_path)

        locations.append(
            {
                "raw_path": raw_path,
                "file_name": file_name,
                "line": line_no,
            }
        )

    # remove duplicates, keep order
    unique = []
    seen = set()

    for loc in locations:
        key = (loc["file_name"], loc["line"])
        if key not in seen:
            unique.append(loc)
            seen.add(key)

    return unique


def find_file_in_project(file_name: str) -> str:
    """
    Searches for a file in the configured RTL/TB/run-script directories.
    """

    bat_dir = os.path.dirname(PROJECT_CONFIG.get("bat_file_path", ""))

    search_dirs = [
        PROJECT_CONFIG.get("tb_dir", ""),
        PROJECT_CONFIG.get("rtl_dir", ""),
        bat_dir,
    ]

    for directory in search_dirs:
        if not directory or not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if file_name in files:
                return os.path.join(root, file_name)

    return ""


def read_source_context(file_path: str, line_no: int, radius: int = 4) -> str:
    """
    Reads a small source-code window around the error line.
    """

    if not file_path or not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return ""

    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)

    context_lines = []

    for idx in range(start, end + 1):
        marker = ">>" if idx == line_no else "  "
        code_line = lines[idx - 1].rstrip()
        context_lines.append(f"{marker} {idx:4d}: {code_line}")

    return "\n".join(context_lines)

def build_source_error_context(error_text: str) -> tuple[str, str]:
    """
    Builds source-code context for the files and lines mentioned in Vivado errors.
    Returns:
    - markdown/code text for UI
    - comma-separated target files
    """

    locations = extract_error_file_locations(error_text)

    if not locations:
        return "", ""

    sections = []
    target_files = []

    for loc in locations:
        file_name = loc["file_name"]
        line_no = loc["line"]

        # ignorăm top.sv dacă apare doar ca "ignored due to previous errors"
        if file_name == "top.sv" and "ignored due to previous errors" in error_text.lower():
            continue

        file_path = find_file_in_project(file_name)
        source_context = read_source_context(file_path, line_no)

        target_files.append(file_name)

        if source_context:
            sections.append(
                f"File: {file_name}, line {line_no}\n"
                f"{source_context}"
            )
        else:
            sections.append(
                f"File: {file_name}, line {line_no}\n"
                "Source context could not be read from disk."
            )

    target_files = list(dict.fromkeys(target_files))
    return "\n\n".join(sections), ", ".join(target_files)


def build_error_fix_plan(
    category: str,
    target_files: str,
    recommendation: str,
    evidence: str,
) -> str:
    return (
        "SHORT_RESPONSE:\n"
        "Vivado/XSim reported an error after the last run. The system should not "
        "continue coverage comparison until this error is fixed.\n\n"

        "ROOT_CAUSE_SUMMARY:\n"
        f"Error category: {category}.\n"
        f"{recommendation}\n\n"

        "CHOSEN STRATEGY: TESTBENCH_WIRING_FIX\n"
        "CODE_ACTION: MODIFY\n"
        f"TARGET_FILES: {target_files}\n\n"

        "PLANNED_CHANGE:\n"
        "Generate the smallest correction needed to make the modified verification "
        "environment compile and run again. The fix must target only the files related "
        "to the last generated code or run script change.\n\n"

        "EVIDENCE:\n"
        f"{evidence[:2000]}"
    )


# ============================================================
# Error analysis
# ============================================================

def error_analysis(state: AgentState):
    print("[ANALYZER]: Error detected. Analyzing Vivado/XSim failure.")

    raw_error = state.get("compilation_error", "")
    sim_log = read_simulation_log(state.get("simulation_log_path", ""))

    combined_error_text = raw_error + "\n\n" + sim_log
    evidence = extract_relevant_error_lines(combined_error_text)

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


def find_matching_hole_in_updated_list(selected_hole, updated_holes_list: list):
    """
    First compares by stable key, then falls back to textual description.
    This avoids confusing holes with the same coverpoint/cross name but different instances.
    """

    if isinstance(selected_hole, dict):
        selected_key = selected_hole.get("key", "")
        selected_description = selected_hole.get("description", "")
    else:
        selected_key = ""
        selected_description = selected_hole or ""

    if selected_key:
        for hole in updated_holes_list:
            if hole.get("key", "") == selected_key:
                return hole

    for hole in updated_holes_list:
        updated_description = hole.get("description", "")
        if is_same_logical_hole(selected_description, updated_description):
            return hole

    return None


def classify_fix_result(
    old_coverage: float,
    new_coverage: float,
    selected_hole,
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
    updated_list = build_coverage_holes_list(fcov_path)

    new_coverage = safe_float(extract_coverage_percent(fcov_path))
    old_coverage = safe_float(
        state.get("previous_coverage", state.get("coverage_value", 0.0))
    )

    target_hole_obj = state.get("current_hole", {})
    target_hole_description = target_hole_obj.get("description", "")
    action_plan = state.get("action_plan", "")

    strategy = parse_action_plan_field(action_plan, "CHOSEN STRATEGY")
    code_action = parse_action_plan_field(action_plan, "CODE_ACTION")

    target_files = normalize_target_files(
        parse_action_plan_field(action_plan, "TARGET_FILES") or state.get("target_file", "")
    )

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



# ============================================================
# DUT change impact analysis
# ============================================================

def dut_change_impact_analysis(state: AgentState):
    """
    Analysis-only feature.

    This function does not generate code, does not inject code,
    and does not run Vivado. It only explains what parts of the
    UVM testbench may need to be updated after a DUT modification.
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