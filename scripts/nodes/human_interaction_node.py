from state import AgentState
from utils_files.ui_messages import build_ui_message
from utils_files.intent_parser import normalize_user_input
from utils_files.injection import create_rollback_checkpoint, inject_generated_code
from utils_files.memory import save_negative_experience
from utils_files.phases import Phase
from utils_files.status import Status
from llama_index.core import Settings


# ==========================================
# ---------- TEXT INTENT HELPERS ----------
# ==========================================

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
    Detects intent by checking if the user used both an action verb
    and a relevant object.

    Examples:
    - "generate the code please" -> generate + code
    - "show me the implementation" -> show + implementation
    - "run vivado" -> run + vivado
    """
    tokens = tokenize_user_text(text)

    has_verb = any(verb in tokens for verb in verbs)
    has_object = any(obj in tokens for obj in objects)

    return has_verb and has_object


def strip_feedback_prefix(text: str) -> str:
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
    Detects when the user is not approving, but correcting or restricting.
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

        prompt = f"""
You are an AI verification assistant.

The user provided feedback during a review step.

USER FEEDBACK:
{raw_text}

Write a short acknowledgement message, maximum 2 sentences.

Rules:
- Acknowledge what the user wants.
- Say that you will revise the plan/code accordingly if it is technically valid.
- Do not generate code.
- Do not generate a new action plan.
- Do not claim that the change is already done.
- Do not mention internal phases or implementation details.
"""

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

        prompt = f"""
You are a routing classifier for a human-in-the-loop AI verification assistant.

Current phase:
{phase}

Allowed commands:
{allowed_commands}

Default command if unsure:
{default_command}

User input:
{raw_text}

Current selected coverage hole:
{current_hole}

Current/previous plan:
{current_plan}

Last result or analysis:
{last_result}

Classify the user's intent.

Rules:
- Return ONLY valid JSON.
- Do not explain.
- The command must be one of the allowed commands.
- If the user gives technical feedback, criticism, suggestions, constraints, doubts, or observations, choose "refine_plan".
- If the user says the generated code should be changed because of strategy, files, protocol, coverage, sampling, latency, transactions, monitor, or testbench behavior, choose "refine_plan".
- In RESULT_REVIEW, "try again", "retry", "fix again", or any free technical feedback means "refine_plan".
- Choose "approve_plan" or "approve_code" only if the user clearly approves with no correction or restriction.
- Choose "regenerate_code" only for simple code regeneration without strategy change.
- If unsure, choose the default command.

JSON schema:
{{
  "user_command": "...",
  "user_feedback": "...",
  "confidence": 0.0
}}
"""

        response = llm.complete(prompt)
        text = response.text.strip()

        import json
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

# ==========================================
# ---------- HUMAN INTERACTION ----------
# ==========================================

def human_interaction_node(state: AgentState):
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

    # ------------------------------------------------------------
    # NO INPUT YET -> build UI message
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # GLOBAL QUIT
    # ------------------------------------------------------------
    if has_word(raw_text, ["q", "quit", "exit", "stop"]):
        result["user_command"] = "quit"
        result["user_feedback"] = ""
        return result

    # ------------------------------------------------------------
    # ERROR / FAILED PLAN REVIEW
    # ------------------------------------------------------------
    if phase == Phase.PLAN_REVIEW and status == Status.FAILED and errors:
        auto_fix_allowed = state.get("auto_fix_allowed", True)
        has_rollback = bool(state.get("rollback_files", {}))

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

        result["ui_message"] = (
            "I could not understand the selected action.\n\n"
            "Please type:\n"
            "[1] Generate corrected code based on the error analysis\n"
            "[2] Rollback to previous code version\n"
            "[q] Quit"
        )
        return result

    # ------------------------------------------------------------
    # SELECT_HOLE
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # PLAN_REVIEW
    # ------------------------------------------------------------
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

        # Only after all commands were checked:
        # free text becomes technical feedback for the analyzer.
        feedback = strip_feedback_prefix(raw_text)
        result["user_feedback"] = feedback
        result["user_command"] = "refine_plan"

        # Natural acknowledgement for the user.
        result["ui_message"] = generate_feedback_acknowledgement(raw_text, phase)

        print(f"[DEBUG HUMAN PLAN_REVIEW] SAVING FEEDBACK='{result['user_feedback']}'")
        return result

    # ------------------------------------------------------------
    # CODE_REVIEW
    # ------------------------------------------------------------
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
            ]
        )

        if approve_request:
            result["user_command"] = "approve_code"
            result["user_feedback"] = ""
            result["previous_coverage"] = state.get("coverage_value", 0.0)

            rollback_files = create_rollback_checkpoint(state)
            result["rollback_files"] = rollback_files

            inject_generated_code(state)
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

        result["ui_message"] = (
            "I could not clearly understand your code review decision.\n\n"
            "Please type:\n"
            "[1] Approve code → inject and run Vivado\n"
            "[2] Regenerate code with feedback\n"
            "[q] Quit"
        )
        return result

    # ------------------------------------------------------------
    # RESULT_REVIEW
    # ------------------------------------------------------------
    if phase == Phase.RESULT_REVIEW:
        # Full coverage optional branch: DUT change impact analysis.
        coverage_value = state.get("coverage_value", 0.0)
        holes_list = state.get("holes_list", [])

        try:
            coverage_float = float(coverage_value)
        except Exception:
            coverage_float = 0.0

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

                # If the user typed only "1", ask them to provide specs.
                # But because we avoid extra UI phases, we give an instruction message.
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

        # Clear deterministic commands first.
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