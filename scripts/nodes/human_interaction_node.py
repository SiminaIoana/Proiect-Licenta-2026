from state import AgentState
from utils_files.ui_messages import build_ui_message
from utils_files.intent_parser import normalize_user_input
from utils_files.injection import create_rollback_checkpoint, inject_generated_code
from utils_files.memory import save_negative_experience
from utils_files.phases import Phase
from utils_files.status import Status


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

    Example:
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
    ]

    raw_lower = raw.lower()

    for prefix in prefixes:
        if raw_lower.startswith(prefix):
            return raw[len(prefix):].strip()

    return raw


def has_negative_or_correction_intent(text: str) -> bool:
    """
    Detects when the user is not approving, but correcting or restricting.
    Example:
    - "do not generate complicated code"
    - "ok but change the sequence"
    - "don't modify constraints"
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
            "feedback:",
            "suggestion:",
            "comment:",
            "observation:",
            "idea:",
            "maybe",
            "i think",
            "i believe",
            "you should",
            "should",
            "try to",
            "try",
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
        ]
    )


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
    # Works for:
    # q, Q, quit, exit, stop, "q and restart", "please quit"
    # ------------------------------------------------------------
    if has_word(raw_text, ["q", "quit", "exit", "stop"]):
        result["user_command"] = "quit"
        result["user_feedback"] = ""
        return result

    # ------------------------------------------------------------
    # ERROR / FAILED PLAN REVIEW
    # For now: no automatic error repair. Prefer rollback.
    # ------------------------------------------------------------
    if phase == Phase.PLAN_REVIEW and status == Status.FAILED and errors:
        rollback_request = (
            has_word(raw_text, ["1", "rollback", "restore"])
            or contains_any(raw_text, ["previous version", "restore previous"])
        )

        if rollback_request:
            result["user_command"] = "rollback"
            result["user_feedback"] = ""
            if state.get("generated_code"):
                save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                errors or "User requested rollback after Vivado error."
            )
        else:
            result["ui_message"] = (
                "The generated code caused a Vivado error.\n\n"
                "Recommended action: rollback to the previous code version.\n\n"
                "Please type:\n"
                "[1] Rollback to previous code version\n"
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
        result["user_command"] = "retry_same_hole"
        result["ui_message"] = (
            "I have saved the observation as technical feedback and will re-run "
            "the analysis for the same hole."
        )

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

        if approve_request:
            result["user_command"] = "approve_code"
            result["user_feedback"] = ""
            result["previous_coverage"] = state.get("coverage_value", 0.0)

            rollback_files = create_rollback_checkpoint(state)
            result["rollback_files"] = rollback_files

            inject_generated_code(state)
            return result

        if reject_request or feedback_like or negative_intent:
            result["user_command"] = "reject_code"

            simple_reject = raw_lower in [
                "2",
                "reject",
                "regenerate",
                "retry",
                "try again",
            ]

            if simple_reject:
                result["user_feedback"] = state.get("user_feedback", "")
            else:
                result["user_feedback"] = strip_feedback_prefix(raw_text)

            save_negative_experience(
                state.get("current_hole", {}).get("description", ""),
                state.get("generated_code", ""),
                raw_text
            )

            result["ui_message"] = (
                "I saved your feedback and will regenerate/reanalyze the solution."
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
    #
    # In this phase:
    # - show list -> updated holes list
    # - retry -> same hole
    # - rollback -> previous code version
    # - ambiguous text -> ask clarification, do NOT auto-retry
    # ------------------------------------------------------------
    if phase == Phase.RESULT_REVIEW:
        show_list_request = (
            user_choice == "show_list"
            or raw_lower == "1"
            or has_word(raw_text, ["list"])
            or contains_any(
                raw_text,
                [
                    "show list",
                    "updated list",
                    "show updated list",
                    "show updated holes list",
                    "show me updated holes list",
                    "holes list",
                    "updated holes",
                    "pick another",
                    "another hole",
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
                    "try again",
                    "retry analysis",
                ]
            )
        )

        rollback_request = (
            raw_lower == "3"
            or has_word(raw_text, ["rollback", "restore"])
            or contains_any(
                raw_text,
                [
                    "restore previous",
                    "previous version",
                    "restore previous version",
                ]
            )
        )

        if show_list_request:
            result["user_command"] = "show_list"
            result["user_feedback"] = ""
            return result

        if retry_request:
            result["user_command"] = "retry_same_hole"
            result["user_feedback"] = state.get("user_feedback", "")
            return result

        if rollback_request:
            result["user_command"] = "rollback"
            result["user_feedback"] = ""
            if state.get("generated_code"):
                save_negative_experience(
                    state.get("current_hole", {}).get("description", ""),
                    state.get("generated_code", ""),
                    "User requested rollback after validation result. Generated solution was considered unsafe, ineffective, or not worth keeping."
                )
            return result

        result["ui_message"] = (
            "I could not clearly understand your next action.\n\n"
            "Please type:\n"
            "[1] Show updated holes list / pick another coverage hole\n"
            "[2] Retry fixing the same hole\n"
            "[3] Rollback to previous code version\n"
            "[q] Quit"
        )
        return result

    # ------------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------------
    return {
        "ui_input": "",
        "user_command": "",
        "user_feedback": state.get("user_feedback", ""),
        "ui_message": (
            "I could not understand your request.\n\n"
            "Please use one of the suggested options or provide a clearer instruction."
        )
    }