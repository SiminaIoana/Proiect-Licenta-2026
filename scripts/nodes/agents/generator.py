from scripts.utils_files.status import Status
from llama_index.core import Settings
from state import AgentState

from utils_files.file_ops import read_specific_files
from utils_files.results_saving import get_index

import os
import tiktoken
from config import PROJECT_CONFIG

from prompts.generator_prompt import GENERATOR_SYSTEM_PROMPT, GENERATOR_FIX_HOLE_PROMPT, GENERATOR_FIX_SYNTAX_PROMPT


# ==================================
# ------- GENERATOR NODE ------
# ==================================
def generator_node(state: AgentState):
    print("\n" + "="*60)
    print("[GENERATOR]: FIX ERRORS AND HOLES...")
    print("="*60)

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")
    feedback = state.get("user_feedback", "")
    plan = state.get("action_plan", "")
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)
    specs = state.get("dut_specs", "")
    user_command = state.get("user_command", "")
    target_file = state.get("target_file", "unknown_file.sv")

    working_dir = os.path.dirname(PROJECT_CONFIG["bat_file_path"])
    directories_to_search = [PROJECT_CONFIG.get("tb_dir", ""), PROJECT_CONFIG.get("rtl_dir", "")]
    core_files = "transaction.sv, sequence.sv, test.sv"
    files_to_read = f"{target_file}, {core_files}"
    target_code = read_specific_files(files_to_read, directories_to_search)

    # ----------------------------------------------
    # --------- FIXING ERRORS ---------------
    #-----------------------------------------------
    if user_command == "fix_syntax" and error != "":
        print(f"\n[GENERATOR]: Querying Semantic Memory (LTM) for a fix...")
        # long term memory 
        ltm_content = ""
        try:
            index_exp = get_index("../results/experience_data/", "../DOCS/storage_exp/", "LTM Index")
            
            if index_exp:
                query_engine = index_exp.as_query_engine(similarity_top_k=1)
                # how the probmlem was solved
                memory_response = query_engine.query(f"Identify the fix for this Vivado error: {error}")
                ltm_content = str(memory_response)

        except Exception as e:
            pass
        
        memory_section = f"\nRELEVANT PAST EXPERIENCE FOUND IN MEMORY:\n{ltm_content}\nReview this to avoid repeating the same error!\n" if ltm_content else ""
        
        user_prompt = GENERATOR_FIX_SYNTAX_PROMPT.format(
            error=error,
            memory_section=memory_section,
            target_code=target_code,
            specs=specs
        )
    
    # ------ FIX HOLES -----
    else:
        print(f"[GENERATOR]: Updating '{target_file}' based on Analyzer's Action Plan...")
        user_prompt = GENERATOR_FIX_HOLE_PROMPT.format(
            plan=plan,
            target_code=target_code,
            specs=specs
        )
    # combine user prompt with system prompt for Groq
    full_prompt = GENERATOR_SYSTEM_PROMPT + "\n\n" + user_prompt
    context_path = os.path.join(working_dir, "AI_CONTEXT.txt")
    with open(context_path, "w", encoding="utf-8") as f:
        f.write(full_prompt)

    print(f"[DEBUG] ALL THE CONTEXT FOR AI WAS SAVED IN: {context_path}")

    response = llm.complete(full_prompt)
    debug_path = os.path.join(working_dir, "DEBUG.sv")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"[DEBUG] CODE WASGENERATED IN {debug_path}")

    # prompt tokens 
    prompt_tokens = len(encoding.encode(full_prompt))
    #responde tokens
    response_tokens = len(encoding.encode(response.text))
    current_tokens = state.get("iteration_tokens", 0)
    total_tokens = prompt_tokens + response_tokens + current_tokens

    return {
     "generated_code": response.text,
    "iteration_tokens": total_tokens,
    "iterations": iterations + 1,
    "status":   Status.SUCCESS
}