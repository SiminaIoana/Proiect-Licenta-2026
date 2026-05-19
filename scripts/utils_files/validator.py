import os
import re
from dataclasses import dataclass
from config import PROJECT_CONFIG


ALLOWED_STRATEGIES = {
    "RUN_SCRIPT_FIX",
    "NEW_SEQUENCE",
    "NEW_TEST",
    "MODIFY_EXISTING_SEQUENCE",
    "MODIFY_EXISTING_TEST",
    "MODIFY_CONSTRAINT",
    "MODIFY_COVERPOINT",
    "MODIFY_BINS",
    "MODIFY_CROSS",
    "ADD_DIRECTED_VALUES_TO_EXISTING_SEQUENCE",
    "TESTBENCH_WIRING_FIX",
    "RTL_BUG",
    "NO_CHANGE_EXPLAIN",
}

ALLOWED_CODE_ACTIONS = {
    "APPEND",
    "MODIFY",
    "NO_CODE_CHANGE",
}

SUPPORTED_MODIFY_MARKERS = {
    "REPLACE_CLASS",
    "REPLACE_COVERPOINT",
    "REPLACE_COVERGROUP",
}


@dataclass
class PlanValidationResult:
    plan_text: str
    target_files: str
    warnings: list[str]


def parse_plan_field(plan_text: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(plan_text or "")
    return match.group(1).strip() if match else ""


def replace_or_add_field(plan_text: str, field_name: str, value: str) -> str:
    pattern = re.compile(
        rf"(^\s*{re.escape(field_name)}\s*:\s*)(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    if pattern.search(plan_text or ""):
        return pattern.sub(rf"\g<1>{value}", plan_text, count=1)

    return (plan_text or "").rstrip() + f"\n\n{field_name}: {value}\n"


def get_project_search_dirs() -> list[str]:
    dirs = []

    tb_dir = PROJECT_CONFIG.get("tb_dir", "")
    rtl_dir = PROJECT_CONFIG.get("rtl_dir", "")
    bat_file_path = PROJECT_CONFIG.get("bat_file_path", "")

    if tb_dir and os.path.isdir(tb_dir):
        dirs.append(tb_dir)

    if rtl_dir and os.path.isdir(rtl_dir):
        dirs.append(rtl_dir)

    if bat_file_path:
        bat_dir = os.path.dirname(bat_file_path)
        if bat_dir and os.path.isdir(bat_dir):
            dirs.append(bat_dir)

    return list(dict.fromkeys(dirs))


def get_existing_project_files() -> dict[str, str]:
    existing_files = {}

    for search_dir in get_project_search_dirs():
        for root, _, files in os.walk(search_dir):
            for file_name in files:
                existing_files[file_name.lower()] = os.path.join(root, file_name)

    bat_file_path = PROJECT_CONFIG.get("bat_file_path", "")
    if bat_file_path:
        existing_files[os.path.basename(bat_file_path).lower()] = bat_file_path

    return existing_files


def get_run_script_name() -> str:
    bat_file_path = PROJECT_CONFIG.get("bat_file_path", "")
    if not bat_file_path:
        return ""
    return os.path.basename(bat_file_path)


def clean_file_name(raw_file: str) -> str:
    return (
        raw_file.strip()
        .replace("`", "")
        .replace('"', "")
        .replace("'", "")
    )

def contains_any(text: str, phrases: list[str]) -> bool:
    lower = (text or "").lower()
    return any(phrase.lower() in lower for phrase in phrases)

def find_file_by_keywords(existing_files: dict[str, str], keywords: list[str]) -> str:
    candidates = []

    for lower_name, path in existing_files.items():
        if not lower_name.endswith((".sv", ".svh", ".v", ".bat", ".tcl")):
            continue

        if any(keyword in lower_name for keyword in keywords):
            candidates.append(os.path.basename(path))

    if not candidates:
        return ""

    return sorted(candidates, key=len)[0]


def infer_role_from_file_name(file_name: str) -> str:
    lower = file_name.lower()

    if lower in {"run.sh", "run_script.sh", "run.bat", "makefile", "makefile.bat"}:
        return "run_script"

    if "seq" in lower or "sequence" in lower:
        return "sequence"

    if "test" in lower:
        return "test"

    if "subscriber" in lower or "coverage" in lower or "cover" in lower:
        return "coverage"

    if "transaction" in lower or "item" in lower:
        return "transaction"

    if "driver" in lower:
        return "driver"

    if "monitor" in lower:
        return "monitor"

    if "scoreboard" in lower:
        return "scoreboard"

    if "dut" in lower or "rtl" in lower or "design" in lower:
        return "rtl"

    return ""


def normalize_one_target_file(raw_file: str, existing_files: dict[str, str]) -> tuple[str, str]:
    file_name = clean_file_name(raw_file)

    if not file_name:
        return "", ""

    lower = file_name.lower()

    if lower in existing_files:
        return os.path.basename(existing_files[lower]), ""

    role = infer_role_from_file_name(file_name)

    if role == "run_script":
        run_script = get_run_script_name()
        if run_script:
            return run_script, f"Mapped run script alias '{file_name}' to configured run script '{run_script}'."

    if role == "sequence":
        mapped = find_file_by_keywords(existing_files, ["sequence", "seq"])
        if mapped:
            return mapped, f"Mapped nonexistent sequence file '{file_name}' to existing sequence file '{mapped}'."

    if role == "test":
        mapped = find_file_by_keywords(existing_files, ["test"])
        if mapped:
            return mapped, f"Mapped nonexistent test file '{file_name}' to existing test file '{mapped}'."

    if role == "coverage":
        mapped = find_file_by_keywords(existing_files, ["subscriber", "coverage", "cover"])
        if mapped:
            return mapped, f"Mapped nonexistent coverage file '{file_name}' to existing coverage file '{mapped}'."

    return file_name, f"Target file '{file_name}' was not found in configured project directories."


def normalize_target_files(target_files: str, existing_files: dict[str, str]) -> tuple[str, list[str]]:
    normalized = []
    warnings = []

    for raw_file in (target_files or "").split(","):
        file_name, warning = normalize_one_target_file(raw_file, existing_files)

        if file_name:
            normalized.append(file_name)

        if warning:
            warnings.append(warning)

    normalized = list(dict.fromkeys(normalized))
    return ", ".join(normalized), warnings


def normalize_strategy(strategy_text: str) -> tuple[str, str]:
    raw = (strategy_text or "").strip()
    upper = raw.upper()

    matches = [strategy for strategy in ALLOWED_STRATEGIES if strategy in upper]

    if not matches:
        return raw, ""

    if len(matches) == 1:
        return matches[0], ""

    matches = sorted(matches, key=lambda item: upper.find(item))
    chosen = matches[0]

    return chosen, f"Multiple strategies detected. Kept only '{chosen}'."


def normalize_code_action(code_action_text: str) -> tuple[str, str]:
    raw = (code_action_text or "").strip()
    upper = raw.upper()

    matches = [action for action in ALLOWED_CODE_ACTIONS if action in upper]

    if not matches:
        return raw, ""

    if len(matches) == 1:
        return matches[0], ""

    matches = sorted(matches, key=lambda item: upper.find(item))
    chosen = matches[0]

    return chosen, f"Multiple code actions detected. Kept only '{chosen}'."


def has_supported_modify_marker(plan_text: str) -> bool:
    upper = (plan_text or "").upper()
    return any(marker in upper for marker in SUPPORTED_MODIFY_MARKERS)


def append_validator_notes(plan_text: str, notes: list[str]) -> str:
    if not notes:
        return plan_text

    return (
        (plan_text or "").rstrip()
        + "\n\nVALIDATOR_NOTES:\n"
        + "\n".join(f"- {note}" for note in notes)
        + "\n"
    )


def validate_action_plan(plan_text: str, state: dict) -> PlanValidationResult:
    corrected_plan = plan_text or ""
    warnings = []
    notes = []

    existing_files = get_existing_project_files()

    # ------------------------------------------------------------
    # 1. Parse initial plan fields
    # ------------------------------------------------------------
    strategy_raw = parse_plan_field(corrected_plan, "CHOSEN STRATEGY")
    code_action_raw = parse_plan_field(corrected_plan, "CODE_ACTION")
    target_files_raw = parse_plan_field(corrected_plan, "TARGET_FILES")

    # ------------------------------------------------------------
    # 2. Normalize strategy first
    # ------------------------------------------------------------
    strategy, strategy_warning = normalize_strategy(strategy_raw)

    if strategy and strategy != strategy_raw:
        corrected_plan = replace_or_add_field(
            corrected_plan,
            "CHOSEN STRATEGY",
            strategy,
        )

    if strategy_warning:
        warnings.append(strategy_warning)
        notes.append(strategy_warning)

    # ------------------------------------------------------------
    # 3. Special deterministic correction:
    #    If sequence/test already exist and only run command is missing,
    #    do NOT create duplicate sequence/test.
    # ------------------------------------------------------------
    root_cause_type = parse_plan_field(corrected_plan, "ROOT_CAUSE_TYPE").upper()
    run_script = get_run_script_name()

    sequence_exists_but_test_missing = (
    contains_any(
        corrected_plan,
        [
            "sequence exists",
            "sequence already exists",
            "existing sequence",
            "sequence is available",
            "sequence was found",
        ],
    )
    and contains_any(
        corrected_plan,
        [
            "test is missing",
            "test does not exist",
            "no test exists",
            "missing test",
            "missing test class",
            "no test class",
            "no uvm test",
            "no test starts",
            "not started by any test",
            "sequence is not started",
            "sequence is never started",
        ],
    )
)
    missing_execution_evidence = contains_any(
        corrected_plan,
        [
            "test exists",
            "test already exists",
            "sequence exists",
            "sequence already exists",
            "execution command is missing",
            "run command is missing",
            "not executed by the run script",
            "no run command",
            "missing from the run script",
            "was never added to the run script",
            "was never executed",
            "not executed",
            "coverage was never collected",
        ],
    )

    if sequence_exists_but_test_missing and run_script:
        test_file = find_file_by_keywords(existing_files, ["test"])

        required_files = [
        file_name
        for file_name in [test_file, run_script]
        if file_name
    ]

        corrected_plan = replace_or_add_field(
        corrected_plan,
        "CHOSEN STRATEGY",
        "NEW_TEST",
    )

        corrected_plan = replace_or_add_field(
        corrected_plan,
        "CODE_ACTION",
        "APPEND",
    )

        corrected_plan = replace_or_add_field(
        corrected_plan,
        "TARGET_FILES",
        ", ".join(dict.fromkeys(required_files)),
    )

        strategy = "NEW_TEST"
        code_action_raw = "APPEND"
        target_files_raw = ", ".join(dict.fromkeys(required_files))

        note = (
        "A suitable sequence already exists, but no UVM test starts it. "
        "The safe fix is to append a new test class in the existing test file "
        "and add the new test execution command to the configured run script. "
        "Do not create a duplicate sequence and do not use RUN_SCRIPT_FIX only."
    )

        warnings.append(note)
        notes.append(note)
    if (
        root_cause_type == "MISSING_TEST_EXECUTION"
        and strategy in {"NEW_SEQUENCE", "NEW_TEST"}
        and missing_execution_evidence
        and not sequence_exists_but_test_missing
        and run_script
    ):
        corrected_plan = replace_or_add_field(
            corrected_plan,
            "CHOSEN STRATEGY",
            "RUN_SCRIPT_FIX",
        )

        corrected_plan = replace_or_add_field(
            corrected_plan,
            "CODE_ACTION",
            "APPEND",
        )

        corrected_plan = replace_or_add_field(
            corrected_plan,
            "TARGET_FILES",
            run_script,
        )

        # Very important:
        # update local variables too, otherwise the code below still sees
        # the old strategy such as NEW_SEQUENCE.
        strategy = "RUN_SCRIPT_FIX"
        code_action_raw = "APPEND"
        target_files_raw = run_script

        note = (
            "Root cause is MISSING_TEST_EXECUTION and the plan states that the "
            "sequence/test already exists. The safe fix is to append only the "
            "missing run command to the configured run script, not to create "
            "duplicate sequence/test classes."
        )

        warnings.append(note)
        notes.append(note)

    # ------------------------------------------------------------
    # 4. Normalize code action after possible strategy correction
    # ------------------------------------------------------------
    code_action, action_warning = normalize_code_action(code_action_raw)

    if code_action and code_action != code_action_raw:
        corrected_plan = replace_or_add_field(
            corrected_plan,
            "CODE_ACTION",
            code_action,
        )

    if action_warning:
        warnings.append(action_warning)
        notes.append(action_warning)

    if code_action == "MODIFY" and strategy == "NEW_SEQUENCE":
        if contains_any(
            corrected_plan,
        [
            "modify the existing",
            "modify existing",
            "existing directed sequence",
            "existing sequence",
            "current sequence",
            "sequence already exists",
            "already exists",
            "rather than adding",
            "rather than creating",
            "do not create",
            "not append",
            "instead of appending",
        ],
        ):
            corrected_plan = replace_or_add_field(
            corrected_plan,
            "CHOSEN STRATEGY",
            "MODIFY_EXISTING_SEQUENCE",
            )

            strategy = "MODIFY_EXISTING_SEQUENCE"

            note = (
            "CODE_ACTION is MODIFY and the plan refers to an existing sequence. "
            "Changed strategy from NEW_SEQUENCE to MODIFY_EXISTING_SEQUENCE."
            )

            warnings.append(note)
            notes.append(note)

    # ------------------------------------------------------------
    # 5. Normalize target files after possible strategy correction
    # ------------------------------------------------------------
    target_files, file_warnings = normalize_target_files(
        target_files_raw,
        existing_files,
    )

    if target_files and target_files != target_files_raw:
        corrected_plan = replace_or_add_field(
            corrected_plan,
            "TARGET_FILES",
            target_files,
        )

    warnings.extend(file_warnings)
    notes.extend(file_warnings)

    # ------------------------------------------------------------
    # 6. Strategy-specific deterministic guidance
    # ------------------------------------------------------------
    if strategy == "NEW_SEQUENCE":
        sequence_file = find_file_by_keywords(existing_files, ["sequence", "seq"])
        test_file = find_file_by_keywords(existing_files, ["test"])
        run_script = get_run_script_name()

        required_files = [
            file_name
            for file_name in [sequence_file, test_file, run_script]
            if file_name
        ]

        required_files_text = ", ".join(dict.fromkeys(required_files))

        if required_files_text:
            corrected_plan = replace_or_add_field(
                corrected_plan,
                "TARGET_FILES",
                required_files_text,
            )

        notes.append(
            "For NEW_SEQUENCE, append a new sequence class to the existing "
            "sequence file. Do not invent a separate seq_*.sv file unless that "
            "file already exists."
        )

        if test_file:
            notes.append(
                "For NEW_SEQUENCE, also append or update a test in the existing "
                "test file so the new sequence can be started."
            )

        if run_script:
            notes.append(
                "For NEW_SEQUENCE, add the new test execution command to the "
                "configured run script."
            )

    elif strategy == "NEW_TEST":
        test_file = find_file_by_keywords(existing_files, ["test"])
        run_script = get_run_script_name()

        required_files = [
            file_name
            for file_name in [test_file, run_script]
            if file_name
        ]

        required_files_text = ", ".join(dict.fromkeys(required_files))

        if required_files_text:
            corrected_plan = replace_or_add_field(
                corrected_plan,
                "TARGET_FILES",
                required_files_text,
            )

        notes.append(
            "For NEW_TEST, append the new test class to the existing test file. "
            "Do not invent a separate test_*.sv file unless that file already exists."
        )

        if run_script:
            notes.append(
                "For NEW_TEST, add the new test execution command to the "
                "configured run script."
            )

    elif strategy == "RUN_SCRIPT_FIX":
        run_script = get_run_script_name()

        if run_script:
            corrected_plan = replace_or_add_field(
                corrected_plan,
                "TARGET_FILES",
                run_script,
            )

        notes.append(
    "For RUN_SCRIPT_FIX, only append or update the configured run script. "
    "Do not generate new SystemVerilog sequence or test classes unless "
    "the plan explicitly proves that the existing ones are insufficient."
    )

        notes.append(
    "When adding a run command for an existing UVM test, derive the coverage "
    "database name and log file name from the UVM_TESTNAME. Example: for "
    "UVM_TESTNAME=test_data_bins, use -cov_db_name cov_test_data_bins and "
    "redirect output to xsim_test_data_bins.log. Do not use generic names "
    "such as cov_test2 or xsim_test2.log if a test-specific name can be used."
    )

    # ------------------------------------------------------------
    # 7. Check MODIFY compatibility with injector
    # ------------------------------------------------------------
    if code_action == "MODIFY" and not has_supported_modify_marker(corrected_plan):
        note = (
            "CODE_ACTION is MODIFY, but the plan does not mention an "
            "injector-supported marker. Use REPLACE_CLASS, REPLACE_COVERPOINT, "
            "or REPLACE_COVERGROUP."
        )

        warnings.append(note)
        notes.append(note)

    # ------------------------------------------------------------
    # 8. Append validator notes to the plan
    # ------------------------------------------------------------
    corrected_plan = append_validator_notes(corrected_plan, notes)

    # ------------------------------------------------------------
    # 9. Final target files returned to Analyzer/Generator
    # ------------------------------------------------------------
    final_target_files = parse_plan_field(corrected_plan, "TARGET_FILES")
    final_target_files, _ = normalize_target_files(
        final_target_files,
        existing_files,
    )

    return PlanValidationResult(
        plan_text=corrected_plan,
        target_files=final_target_files,
        warnings=warnings,
    )