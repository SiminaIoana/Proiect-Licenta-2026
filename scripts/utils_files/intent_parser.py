
import re
from llama_index.core import Settings
from config import PROJECT_CONFIG
from utils_files.phases import Phase


def llm_intent_classifier(user_input: str, phase: Phase) -> str:
    llm = Settings.llm
    prompt = f"""
            You are an intent classifier for a UVM coverage assistant.

            Your task is to classify the user's message into exactly ONE action.

            Current system phase: {phase}

            Allowed actions:
            - approve
            - reject
            - rollback
            - retry
            - show_list
            - quit
            - unknown
        Rules:
        1. If the user wants to continue, accept, approve, or proceed, return approve.
        2. If the user wants to reject, regenerate, or get another solution, return reject.
        3. If the user wants to restore previous code, undo changes, or revert, return rollback.
        4. If the user wants to try fixing the same hole again, return retry.
        5. If the user wants to see holes, choose another hole, or go back to the list, return show_list.
        6. If the user wants to stop, exit, quit, or end the session, return quit.
        7. If the message is unclear, return unknown.

        Very important:
        Return ONLY in this exact format:
        action=<one_action>

        Do not explain anything.
        Do not return multiple actions.

        User message:
        \"\"\"{user_input}\"\"\"
    """

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

    # SELECT_HOLE: numbers are hole IDs
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