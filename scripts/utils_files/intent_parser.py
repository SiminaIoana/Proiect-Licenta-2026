import re
from utils_files.phases import Phase
from llama_index.core import Settings
from scripts.utils_files.file_ops import safe_format
from scripts.prompts.human_interaction_feedback import INTENT_PARSER_PROMPT


def llm_intent_classifier(user_input: str, phase: Phase) -> str:
    llm = Settings.llm
    prompt = safe_format(INTENT_PARSER_PROMPT,user_input=user_input, phase=str(phase))

    response = llm.complete(prompt)
    text = response.text.strip().lower()

    match = re.search(r"action\s*=\s*(approve|reject|rollback|retry|show_list|quit|unknown)", text)
    if match:
        return match.group(1)

    return "unknown"


def map_intent_to_choice(intent: str, phase: Phase) -> str:
    if intent == "quit":
        return "q"

    if phase == Phase.SELECT_HOLE:
        if intent == "show_list":
            return "show_list"
        return ""

    if phase == Phase.PLAN_REVIEW:
        if intent == "approve":
            return "1"
        if intent in ["reject", "retry"]:
            return "2"
        if intent in ["show_list"]:
            return "3"

    if phase == Phase.CODE_REVIEW:
        if intent == "approve":
            return "1"
        if intent in ["reject", "retry"]:
            return "2"

    if phase == Phase.RESULT_REVIEW:
        if intent == "show_list":
            return "1"
        if intent == "retry":
            return "2"
        if intent == "rollback":
            return "3"

    return ""

def normalize_user_input(user_input: str, phase: Phase) -> str:
    text = user_input.strip().lower()
    if not text:
        return ""

    # global exit commands
    if text == "q" or any(phrase in text for phrase in ["quit", "exit", "stop", "end session"]):
        return "q"

    show_holes_phrases = [
        "pick another hole",
        "choose another hole",
        "select another hole",
        "another hole",
        "different hole",
        "go back to holes",
        "back to holes",
        "holes list",
        "show holes",
        "show list",
        "see holes",
        "current holes",
        "updated holes",
        "list of holes"
    ]

    approve_phrases = [
        "approve",
        "accept",
        "continue",
        "yes",
        "ok",
        "go ahead",
        "do it",
        "proceed",
        "i like the plan",
        "i approve",
        "approve the plan"
    ]

    retry_phrases = [
        "reject",
        "regenerate",
        "retry",
        "try again",
        "new solution",
        "another approach",
        "different solution",
        "regenerate plan"
    ]

    rollback_phrases = [
        "rollback",
        "revert",
        "undo",
        "restore",
        "previous code"
    ]

    # SELECT_HOLE
    if phase == Phase.SELECT_HOLE:
        if text.isdigit():
            return text

        if any(phrase in text for phrase in show_holes_phrases) or any(word in text for word in ["list", "refresh", "reanalyze", "holes"]):
            return "show_list"

        return ""

    # PLAN_REVIEW
    if phase == Phase.PLAN_REVIEW:
        if any(phrase in text for phrase in show_holes_phrases) or text == "3":
            return "3"

        if any(phrase in text for phrase in approve_phrases) or text == "1":
            return "1"

        if any(phrase in text for phrase in retry_phrases) or text == "2":
            return "2"

    # RESULT_REVIEW
    if phase == Phase.RESULT_REVIEW:
        if any(phrase in text for phrase in show_holes_phrases) or text == "1":
            return "1"

        if any(phrase in text for phrase in retry_phrases) or text == "2":
            return "2"

        if any(phrase in text for phrase in rollback_phrases) or text == "3":
            return "3"

    # CODE_REVIEW
    if phase == Phase.CODE_REVIEW:
        if any(phrase in text for phrase in approve_phrases) or text == "1":
            return "1"

        if any(phrase in text for phrase in retry_phrases) or text == "2":
            return "2"

    intent = llm_intent_classifier(user_input, phase)
    mapped_choice = map_intent_to_choice(intent, phase)

    if mapped_choice:
        return mapped_choice

    return ""