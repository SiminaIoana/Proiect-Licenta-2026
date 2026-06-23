import json
from state import AgentState
from utils_files.phases import Phase
from utils_files.status import Status
from llama_index.core import Settings
from utils_files.ui_messages import build_ui_message
from utils_files.memory import save_negative_experience
from utils_files.intent_parser import normalize_user_input
from utils_files.injection import create_rollback_checkpoint, inject_generated_code
from prompts.human_interaction_feedback import (
    HUMAN_INTERACTION_SYSTEM_PROMPT,
    HUMAN_REVIEW_ROUTER_PROMPT,
    HUMAN_CONTEXTUAL_ANSWER_PROMPT
)

def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def tokenize_user_text(text: str) -> list[str]:
    cleaned = normalize_text(text)

    for ch in [",", ".", "!", "?", ";", ":", "(", ")", "[", "]", "{", "}", "\"", "'"]:
        cleaned = cleaned.replace(ch, " ")
    return cleaned.split()


def has_word(text: str, words: list[str]) -> bool:
    tokens = tokenize_user_text(text)
    return any(word in tokens for word in words)


def contains_any(text: str, phrases: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in phrases)


def has_concept_pair(text: str, verbs: list[str], objects: list[str]) -> bool:
    """
    Detects intent by checking iif the input contains both an action verb and an object.
    """
    tokens = tokenize_user_text(text)

    has_verb = any(verb in tokens for verb in verbs)
    has_object = any(obj in tokens for obj in objects)

    return has_verb and has_object


def strip_feedback_prefix(text: str) -> str:
    """Strips the feedback prefix to detect the core feedback content."""
    raw = text.strip()
    prefixes = [
        "feedback:",
        "suggestion:",
        "comment:",
        "observation:",
        "idea:",
        "feedback",
        "suggestion",
        "comment",
        "observation",
        "idea",
    ]

    raw_lower = raw.lower()
    for prefix in prefixes:
        if raw_lower.startswith(prefix):
            return raw[len(prefix):].strip()

    return raw


def has_negative_or_correction_intent(text: str) -> bool:
    """
    Detects when the user is correcting or restricting.
    """
    return contains_any(
        text,
        [
            "do not",
            "don't",
            "dont",
            "avoid",
            "without",
            "not generate",
            "not write",
            "not change",
            "not modify",
            "but change",
            "but modify",
            "but make",
            "however",
            "instead",
        ]
    )


def is_feedback_like(text: str) -> bool:
    """
    Technical text that should be treated as feedback.
    This is used after clear commands are checked.
    """
    return contains_any(
        text,
        [
            "feedback",
            "suggestion",
            "comment",
            "observation",
            "idea",
            "maybe",
            "i think",
            "i believe",
            "you should",
            "should",
            "try to",
            "instead",
            "do not",
            "don't",
            "dont",
            "avoid",
            "keep",
            "change",
            "modify",
            "simpler",
            "simple",
            "complicated",
            "constraint",
            "stimulus",
            "sequence",
            "test",
            "coverage",
            "coverpoint",
            "cross",
            "bin",
            "range",
            "transaction",
            "driver",
            "monitor",
            "scoreboard",
            "makefile",
            "make sv",
            "vivado command",
            "fifo depth",
            "packets",
            "writes",
            "reads",
            "existing test",
            "existing sequence",
            "current test",
            "current sequence",
        ]
    )


def generate_feedback_acknowledgement(raw_text: str, phase: Phase) -> str:
    """
    Uses the LLM only to generate a short natural acknowledgement.
    It does not decide routing and does not generate a plan.
    """
    try:
        llm = Settings.llm
        prompt = HUMAN_INTERACTION_SYSTEM_PROMPT.format(raw_text=raw_text)
        response = llm.complete(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"[HUMAN WARNING] Feedback acknowledgement generation failed: {e}")
        return (
            "I understand your feedback. I will take it into account and revise the "
            "plan or code if it is technically valid."
        )


def route_review_input_with_llm(raw_text: str, phase: Phase, state: AgentState) -> dict:
    """
    Uses the LLM only for routing ambiguous review input.
    The LLM must choose one allowed command for the current phase.
    If unsure, it must choose refine_plan.
    """
    try:
        llm = Settings.llm
        current_hole = state.get("current_hole", {}).get("description", "")
        last_result = state.get("root_cause_hole", "")
        current_plan = state.get("action_plan", "")

        if phase == Phase.PLAN_REVIEW:
            allowed_commands = [
                "approve_plan",
                "refine_plan",
                "show_list",
                "quit",
            ]
            default_command = "refine_plan"

        elif phase == Phase.CODE_REVIEW:
            allowed_commands = [
                "approve_code",
                "regenerate_code",
                "refine_plan",
                "quit",
            ]
            default_command = "refine_plan"

        elif phase == Phase.RESULT_REVIEW:
            allowed_commands = [
                "show_list",
                "refine_plan",
                "rollback",
                "quit",
            ]
            default_command = "refine_plan"

        else:
            return {
                "user_command": "",
                "user_feedback": "",
                "confidence": 0.0,
            }

        prompt = HUMAN_REVIEW_ROUTER_PROMPT.format(
            phase=phase,
            allowed_commands=allowed_commands,
            default_command=default_command,
            raw_text=raw_text,
            current_hole=current_hole,
            current_plan=current_plan,
            last_result=last_result,
        )

        response = llm.complete(prompt)
        text = response.text.strip()
        parsed = json.loads(text)
        command = parsed.get("user_command", default_command)
        feedback = parsed.get("user_feedback", raw_text)
        confidence = float(parsed.get("confidence", 0.0))

        if command not in allowed_commands:
            command = default_command
            feedback = raw_text
            confidence = 0.0

        return {
            "user_command": command,
            "user_feedback": feedback,
            "confidence": confidence,
        }

    except Exception as e:
        print(f"[HUMAN WARNING] LLM routing failed: {e}")

        return {
            "user_command": "refine_plan",
            "user_feedback": raw_text,
            "confidence": 0.0,
        }


def is_success_fixed_hole_result(state: AgentState) -> bool:
    result_text = state.get("root_cause_hole", "")
    return "SUCCESS_FIXED_HOLE" in result_text


def human_interaction_node(state: AgentState):
    """
    Interprets user input and helps guide it to workflow commands.
    The node handles hole selection, plan review, code review, result review,rollback and quit decisions. 
    """
    phase = state.get("phase", Phase.INIT)
    status = state.get("status", Status.PROCESSING)
    errors = state.get("compilation_error", "")
    raw_input = state.get("ui_input", "")

    raw_text = raw_input.strip()
    raw_lower = normalize_text(raw_text)
    user_choice = normalize_user_input(raw_input, phase)

    print(f"[DEBUG HUMAN] phase={phase}")
    print(f"[DEBUG HUMAN] raw_input='{raw_input}'")
    print(f"[DEBUG HUMAN] normalized='{user_choice}'")

    # If no input just return the current UI message.
    if not raw_text:
        ui_message = build_ui_message(state, phase, status, errors)
        return {
            "ui_message": ui_message
        }

    result = {
        "ui_input": "",
        "user_command": "",
        "user_feedback": state.get("user_feedback", "")
    }

    # Quit command is available in all phases
    if has_word(raw_text, ["q", "quit", "exit", "stop"]):
        result["user_command"] = "quit"
        result["user_feedback"] = ""
        return result

    if phase in [
        Phase.PLAN_REVIEW,
        Phase.CODE_REVIEW,
        Phase.RESULT_REVIEW,
        Phase.SELECT_HOLE,
    ]:
        if is_explanation_only_question(raw_text):
            result["ui_message"] = generate_contextual_answer(raw_text, phase, state)
            result["user_command"] = ""
            result["user_feedback"] = ""
            return result

        if is_question_like(raw_text) and not is_change_request_like(raw_text):
            result["ui_message"] = generate_contextual_answer(raw_text, phase, state)
            result["user_command"] = ""
            result["user_feedback"] = ""
            return result
        
    # Error review after the plan failed
    if phase == Phase.PLAN_REVIEW and status == Status.FAILED and errors:
        auto_fix_allowed = state.get("auto_fix_allowed", True)
        has_rollback = bool(state.get("rollback_files", {}))

        # Minimal correction based on error analysis
        fix_request = (
            raw_lower == "1"
            or has_word(raw_text, ["fix", "repair", "correct", "generate"])
            or contains_any(
                raw_text,
                [
                    "fix syntax",
                    "fix error",
                    "generate fix",
                    "correct code",
                    "try to fix",
                    "repair code",
                    "error analysis",
                    "generate corrected code",
                    "minimal correction",
                    "minimal corrected version",
                    "generator can create",
                    "let the generator",
                    "create correction",
                ]
            )
        )
        # Restore to previous code using ROLLBACK checkpoint
        rollback_request = (
            raw_lower == "2" 
            or has_word(raw_text, ["rollback", "restore", "revert", "undo"]) 
            or contains_any(
            raw_text,
            [
                "previous version",
                "restore previous",
                "rollback code",
                "revert code",
            ]
        )
    )

        if fix_request:
            if not auto_fix_allowed:
                result["ui_message"] = (
                    "This error was classified as unsafe for automatic code fixing. "
                    "Rollback or manual correction is recommended."
                )
                return result

            result["user_command"] = "fix_syntax"
            result["user_feedback"] = ""
            return result

        if rollback_request:
            if not has_rollback:
                result["ui_message"] = (
                    "Rollback is not available because no checkpoint was found for this run."
                )
                return result

            result["user_command"] = "rollback"
            result["user_feedback"] = ""

            if state.get("generated_code"):
                save_negative_experience(
                    state.get("current_hole", {}).get("description", ""),
                    state.get("generated_code", ""),
                    errors or "User requested rollback after Vivado error."
                )

            return result

        # If the input is not clear enough to be a fix explain that
        result["ui_message"] = (
            "I could not understand the selected action.\n\n"
            "Please type:\n"
            "[1] Generate corrected code based on the error analysis\n"
            "[2] Rollback to previous code version\n"
            "[q] Quit"
        )
        return result

    # Selection de ID for the hole to analyze in the current phase
    if phase == Phase.SELECT_HOLE:
        show_list_request = (
            user_choice == "show_list"
            or has_word(raw_text, ["list"])
            or contains_any(raw_text, ["show list", "holes list", "updated list"])
        )

        if show_list_request:
            result["user_command"] = "show_list"
            result["user_feedback"] = ""
            return result

        if raw_text.isdigit():
            hole_id = int(raw_text)
            holes_list = state.get("holes_list", [])

            selected_hole = next(
                (h for h in holes_list if h["id"] == hole_id),
                None
            )

            if selected_hole:
                result["current_hole"] = selected_hole
                result["user_command"] = "fix_hole"
                result["user_feedback"] = ""
            else:
                result["ui_message"] = (
                    "Invalid ID. Please select a valid coverage hole number."
                )

            return result

        result["ui_message"] = (
            "I could not understand which hole you want to analyze.\n\n"
            "Please type a valid hole ID, **show list**, or **q**."
        )
        return result

    # Approve tge plan or ask for revision sending a feedkback
    if phase == Phase.PLAN_REVIEW:
        negative_intent = has_negative_or_correction_intent(raw_text)
        approve_verbs = [
            "approve",
            "accept",
            "continue",
            "proceed",
            "generate",
            "write",
            "create",
            "produce",
            "show",
            "see",
            "display",
        ]

        code_objects = [
            "code",
            "implementation",
            "solution",
            "fix",
            "changes",
        ]

        approve_request = (
            not negative_intent
            and (
                user_choice == "1"
                or has_word(raw_text, ["approve", "accept", "yes", "y", "ok", "okay", "continue", "proceed"])
                or contains_any(raw_text, ["i approve", "approve plan", "go ahead", "do it", "looks good"])
                or has_concept_pair(raw_text, approve_verbs, code_objects)
            )
        )

        show_list_request = (
            user_choice == "3"
            or has_word(raw_text, ["list", "back"])
            or contains_any(
                raw_text,
                [
                    "show list",
                    "holes list",
                    "updated list",
                    "pick another",
                    "another hole",
                    "show me the list",
                ]
            )
        )

        retry_request = (
            raw_lower == "2"
            or has_word(raw_text, ["retry", "reanalyze", "reanalyse"])
            or contains_any(
                raw_text,
                [
                    "retry same hole",
                    "retry analysis",
                    "regenerate plan",
                    "try again",
                ]
            )
        )

        if approve_request:
            result["user_command"] = "approve_plan"
            result["user_feedback"] = ""
            return result

        if show_list_request:
            result["user_command"] = "show_list"
            result["user_feedback"] = ""
            return result

        if retry_request:
            result["user_command"] = "retry_same_hole"
            result["user_feedback"] = state.get("user_feedback", "")
            return result

        # Only after all commands were checked free text becomes technical feedback for the analyzer.
        feedback = strip_feedback_prefix(raw_text)
        result["user_feedback"] = feedback
        result["user_command"] = "refine_plan"

        # Natural acknowledgement for the user
        result["ui_message"] = generate_feedback_acknowledgement(raw_text, phase)
        print(f"[DEBUG HUMAN PLAN_REVIEW] SAVING FEEDBACK='{result['user_feedback']}'")
        return result

    # Approve the code or ask for changes with feedback
    if phase == Phase.CODE_REVIEW:
        negative_intent = has_negative_or_correction_intent(raw_text)
        feedback_like = is_feedback_like(raw_text)

        approve_verbs = [
            "approve",
            "accept",
            "continue",
            "proceed",
            "inject",
            "run",
            "apply",
            "execute",
            "test",
            "try",
            "validate",
        ]

        run_objects = [
            "code",
            "vivado",
            "simulation",
            "sim",
            "solution",
            "fix",
            "implementation",
        ]

        # Explicit approval
        approve_request = (
            not negative_intent
            and not feedback_like
            and (
                user_choice == "1"
                or has_word(raw_text, ["approve", "accept", "yes", "y", "ok", "okay", "continue", "proceed"])
                or contains_any(raw_text, ["i approve", "approve code", "go ahead", "do it", "looks good"])
                or has_concept_pair(raw_text, approve_verbs, run_objects)
            )
        )

        # Explicit rejection
        reject_request = (
            raw_lower == "2"
            or has_word(raw_text, ["reject", "regenerate", "retry"])
            or contains_any(
                raw_text,
                [
                    "try again",
                    "change the code",
                    "modify the code",
                    "regenerate code",
                    "generate again",
                ]
            )
        )

        # Words used for reanalysis and refineement
        explicit_reanalysis_request = (
            has_word(raw_text, ["reanalyze", "reanalyse"])
            or contains_any(
                raw_text,
                [
                    "root cause",
                    "redo analysis",
                    "rerun analysis",
                    "run analysis again",
                    "restart analysis",
                    "start over analysis",
                    "full analysis",
                    "analyze again",
                    "analyse again",
                ]
            )
        )

        simple_regenerate = raw_lower in [
            "2",
            "reject",
            "regenerate",
            "retry",
            "try again",
            "regenerate code",
            "generate again",
        ]

        plan_level_feedback = contains_any(
            raw_text,
            [
                "target file",
                "wrong file",
                "file is wrong",
                "there is no",
                "does not exist",
                "only",
                "do not create",
                "don't create",
                "dont create",
                "do not modify",
                "don't modify",
                "dont modify",
                "no new sequence",
                "no new test",
                "strategy",
                "chosen strategy",
                "code_action",
                "target_files",
                "coverpoint",
                "cover point",
                "bins",
                "bin ",
                "ranges",
                "coverage model",
                "subscriber",
                "sequence.sv",
                "test.sv",
                "makefile",
                "make sv",
                "run script",
                "replace_class",
                "replace_coverpoint",
                "replace marker",
                "scope",
                "plan",
                "revise plan",
                "revise the plan",
                "change plan",
                "change the plan",
                "too complicated",
                "is too complicated",
                "too complex",
                "make it simple",
                "make it simpler",
                "simpler plan",
                "unsafe",
                "not safe",
                "not accepted",
                "not sampled",
                "does not account",
                "doesn't account",
                "wrong strategy",
                "change strategy",
                "not enough",
                "not sufficient",
                "already exists",
                "sequence already exists",
                "test already exists",
                "run command is missing",
                "missing run command",
                "not executed",
                "not running the test",
               
            ]
        )

        code_level_feedback = contains_any(
            raw_text,
            [
                "duplicate",
                "duplicated",
                "xcrg",
                "coverage report command",
                "do not duplicate",
                "don't duplicate",
                "dont duplicate",
                "append only",
                "only append",
                "syntax",
                "compile",
                "compilation",
                "missing macro",
                "class name",
                "test name mismatch",
                ]
            )
        
        if approve_request:
            result["previous_coverage"] = state.get("coverage_value", 0.0)

            try:
                rollback_files = create_rollback_checkpoint(state)
                result["rollback_files"] = rollback_files

                inject_generated_code(state)

                result["user_command"] = "approve_code"
                result["status"] = Status.SUCCESS
                result["ui_message"] = (
                    "Code was approved and injected successfully. "
                    "The simulation will be run again to validate the change."
                )

                return result

            except Exception as e:
                error_message = f"Injection failed before simulation: {e}"

                print(f"[HUMAN ERROR]: {error_message}")

                # Restore files immediately if injection partially modified something.
                rollback_files = result.get("rollback_files", {})
                for file_path, old_content in rollback_files.items():
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(old_content)
                    except Exception as restore_error:
                        print(
                            f"[ROLLBACK WARNING]: Could not restore {file_path}: "
                            f"{restore_error}"
                        )

                save_negative_experience(
                    state.get("current_hole", {}).get("description", ""),
                    state.get("generated_code", ""),
                error_message
                )

                result["user_command"] = ""
                result["status"] = Status.FAILED
                result["compilation_error"] = error_message
                result["rollback_files"] = {}
                result["ui_message"] = (
                    "The generated code could not be injected into the project files, "
                    "so the previous files were restored. You can ask for code regeneration "
                    "or plan refinement before trying again."
                )

                return result

        if explicit_reanalysis_request:
            result["user_command"] = "retry_same_hole"
            result["user_feedback"] = state.get("user_feedback", "")
            result["ui_message"] = (
                "I understand. I will rerun the root-cause analysis for the same coverage hole."
            )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            return result
        if code_level_feedback:
            result["user_feedback"] = strip_feedback_prefix(raw_text)
            result["user_command"] = "regenerate_code"
            result["ui_message"] = (
                "I understand. I will regenerate the code using your feedback."
            )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            return result 
        
        if plan_level_feedback:
            result["user_feedback"] = strip_feedback_prefix(raw_text)
            result["user_command"] = "refine_plan"
            result["ui_message"] = (
                generate_feedback_acknowledgement(raw_text, phase)
                + " I will revise the current plan before regenerating the code."
            )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            return result
        
        if simple_regenerate:
            result["user_command"] = "regenerate_code"
            result["user_feedback"] = state.get("user_feedback", "")
            result["ui_message"] = (
                "I understand. I will regenerate the code using the current plan."
            )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            return result

        if reject_request or feedback_like or negative_intent:
            result["user_feedback"] = strip_feedback_prefix(raw_text)

            result["user_command"] = "refine_plan"
            result["ui_message"] = (
                    generate_feedback_acknowledgement(raw_text, phase)
                    + " I will refine the current plan before regenerating the code."
                )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            return result

        # Only ambigous or natural feedback reaches the LLM router, which must choose the command based on the content.
        routed = route_review_input_with_llm(raw_text, phase, state)

        result["user_command"] = routed["user_command"]

        if routed["user_command"] in ["refine_plan", "regenerate_code"]:
            result["user_feedback"] = routed.get("user_feedback") or raw_text

            if routed["user_command"] == "refine_plan":
                result["ui_message"] = (
                "I will use your feedback to refine the current plan before regenerating the code."
            )
            else:
                result["ui_message"] = (
                    "I will regenerate the code using your feedback."
                )

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

        else:
            result["user_feedback"] = ""

        return result

    # Decide if the user wants to approve the result, retry with the same plan, see the holes list again, or do a rollback to previous version.
    if phase == Phase.RESULT_REVIEW:
        coverage_value = state.get("coverage_value", 0.0)
        holes_list = state.get("holes_list", [])

        try:
            coverage_float = float(coverage_value)
        except Exception:
            coverage_float = 0.0

        # When full coverage is reached the user may optionally describe a DUT change.
        full_coverage_reached = coverage_float >= 100.0 and not holes_list
        dut_change_request = (
            raw_lower == "1"
            or raw_lower.startswith("dut:")
            or raw_lower.startswith("modify dut:")
            or raw_lower.startswith("change dut:")
            or contains_any(
                raw_text,
                [
                    "modify dut",
                    "change dut",
                    "new dut",
                    "dut change",
                    "updated dut",
                    "new specifications",
                    "new dut specs",
                    "add functionality",
                    "add new functionality",
                    "extend dut",
                ],
            )
        )

        if full_coverage_reached:
            if raw_lower == "q" or has_word(raw_text, ["quit", "exit", "stop"]):
                result["user_command"] = "quit"
                result["user_feedback"] = ""
                return result

            if dut_change_request:
                result["user_command"] = "dut_change_analysis"

                # If the user typed only numerical 1, ask them to provide specs.
                if raw_lower == "1":
                    result["ui_message"] = (
                        "Please describe the DUT modification using this format:\n\n"
                        "`dut: describe the new DUT functionality here`\n\n"
                        "Example:\n"
                        "`dut: FIFO depth changes to 16 and almost_full/almost_empty signals are added`"
                    )
                    result["user_command"] = ""
                    return result

                result["new_dut_specs"] = raw_text
                result["user_feedback"] = ""
                return result

            result["ui_message"] = (
                "Full coverage was reached.\n\n"
                "Please type:\n"
                "`dut: describe the new DUT functionality`\n\n"
                "or type **q** to quit."
            )
            return result

        # Clear deterministic commands first --> chose another hole is suggested
        success_fixed = is_success_fixed_hole_result(state)
        if success_fixed:
            if raw_lower == "1" or has_word(raw_text, ["list", "back", "another"]):
                result["user_command"] = "show_list"
                result["user_feedback"] = ""
                return result

            if raw_lower == "q" or has_word(raw_text, ["quit", "exit", "stop"]):
                result["user_command"] = "quit"
                result["user_feedback"] = ""
                return result

            result["ui_message"] = (
                "The selected coverage hole was already fixed.\n\n"
                "Please type:\n"
                "[1] Show updated holes list / choose another coverage hole\n"
                "[q] Quit"
            )
            return result
        
        if raw_lower == "1" or has_word(raw_text, ["list", "back"]):
            result["user_command"] = "show_list"
            result["user_feedback"] = ""
            return result

        if raw_lower == "3" or has_word(raw_text, ["rollback", "restore", "revert", "undo"]):
            result["user_command"] = "rollback"
            result["user_feedback"] = ""
            return result

        if raw_lower == "q" or has_word(raw_text, ["quit", "exit", "stop"]):
            result["user_command"] = "quit"
            result["user_feedback"] = ""
            return result

        # In result review, numeric 2 means refine the current plan.
        if raw_lower == "2":
            result["user_command"] = "refine_plan"
            result["user_feedback"] = state.get("user_feedback", "")
            return result

        # Ambiguous or natural input goes to LLM router.
        routed = route_review_input_with_llm(raw_text, phase, state)

        result["user_command"] = routed["user_command"]

        if routed["user_command"] == "refine_plan":
            result["user_feedback"] = routed.get("user_feedback") or raw_text
            result["ui_message"] = (
                "I will use your feedback to refine the current plan for the same coverage hole."
            )
        else:
            result["user_feedback"] = ""

        print(
            f"[DEBUG HUMAN RESULT_REVIEW LLM ROUTER] "
            f"command='{result['user_command']}', "
            f"feedback='{result['user_feedback']}', "
            f"confidence={routed.get('confidence')}"
        )

        return result
    

def is_question_like(text: str) -> bool:
    """
    Detects when the user is asking for an explanation or clarification.
    """
    return contains_any(
        text,
        [
            "?",
            "why",
            "how",
            "what",
            "what does",
            "what means",
            "explain",
            "clarify",
            "meaning",
            "i don't understand",
            "i do not understand",
            "can you explain",
            "could you explain",
            "tell me why",
            "tell me how",
            "can you tell me",
            "can you check",
            "is it",
            "is this",
            "is the code",
            "is this code",
            "are there",
            "does it",
            "do you see",
            "syntax",
            "syntactic",
            "syntactically",
            "bug",
            "bugs",
        ]
    )

def is_change_request_like(text: str) -> bool:
    """
    Detects when the user is not only asking, but also requesting a change.
    """
    return contains_any(
        text,
        [
            "change",
            "modify",
            "revise",
            "regenerate",
            "try to",
            "use instead",
            "instead",
            "do not",
            "don't",
            "dont",
            "avoid",
            "add",
            "remove",
            "fix",
            "not good",
            "wrong",
            "this is incorrect",
            "this is not correct",
            "you should",
            "i think you should",
            "should not",
            "must",
            "must not",
            "needs to",
            "need to",
            "it should",
            "it must",
            "better to",
            "would be better",
            "make it",
            "generate a new",
        ]
    )


def get_contextual_follow_up(phase: Phase) -> str:
    if phase == Phase.PLAN_REVIEW:
        return "Would you like me to apply the proposed plan, or do you have another question?"

    if phase == Phase.CODE_REVIEW:
        return "Would you like me to apply and run this code, or should I revise it first?"

    if phase == Phase.RESULT_REVIEW:
        return "Would you like to continue with another coverage hole, refine the current plan, or rollback?"

    if phase == Phase.SELECT_HOLE:
        return "Which coverage hole would you like to analyze next?"

    return "Would you like to continue, or do you have another question?"


def generate_contextual_answer(raw_text: str, phase: Phase, state: AgentState) -> str:
    """
    Generates a natural answer to a user question without changing the workflow.
    """
    try:
        llm = Settings.llm

        prompt = HUMAN_CONTEXTUAL_ANSWER_PROMPT.format(
            phase=phase,
            current_hole=state.get("current_hole", {}).get("description", ""),
            holes_list=state.get("holes_list", []),
            action_plan=state.get("action_plan", "")[:4000],
            last_result=state.get("root_cause_hole", "")[:4000],
            generated_code=state.get("generated_code", "")[:3000],
            raw_text=raw_text,
            follow_up=get_contextual_follow_up(phase),
        )

        response = llm.complete(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"[HUMAN WARNING] Contextual answer generation failed: {e}")
        return (
            "I can explain this based on the current coverage context, but I could not "
            "generate a detailed answer right now. "
            + get_contextual_follow_up(phase)
        )
    


def is_explanation_only_question(text: str) -> bool:
    """
    Detects questions that ask for explanation/comparison only.
    These should not trigger plan refinement.
    """
    if not is_question_like(text):
        return False

    # If the user explicitly asks to change/refine/regenerate something,
    # this is not explanation-only.
    explicit_change_request = contains_any(
        text,
        [
            "change the plan",
            "modify the plan",
            "revise the plan",
            "update the plan",
            "regenerate the plan",
            "change it",
            "modify it",
            "revise it",
            "update it",
            "add an idle",
            "add a cycle",
            "add one idle",
            "remove",
            "do not use",
            "don't use",
            "use instead",
            "please change",
            "please modify",
            "can you change",
            "can you modify",
            "and change",
            "and modify",
            "but change",
            "but modify",
        ]
    )

    if explicit_change_request:
        return False

    explanation_patterns = [
        "why",
        "why do you think",
        "why did you choose",
        "why is",
        "why are",
        "what is the reason",
        "can you tell me why",
        "explain why",
        "better than",
        "rather than",
        "instead of",
        "compared to",
        "difference between",
    ]

    return contains_any(text, explanation_patterns)