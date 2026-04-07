from llama_index.core import Settings
from state import AgentState
from utils import get_index, extract_code
import os
import tiktoken
from config import PROJECT_CONFIG


# ============================================================
# ------- FUNCTION FOR READING RTL FILES ------
# ============================================================
def read_rtl(rtl_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not rtl_dir or not os.path.exists(rtl_dir):
        return content

    for root, _, files in os.walk(rtl_dir):
        for file in files:
           
            if file.endswith(".v") or file.endswith(".sv"): 
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content += f"\n--- RTL FILE: {file} ---\n{f.read()}\n"
                except Exception as e:
                    pass
    return content


# ============================================================
# ------- FUNCTION FOR READING TESTBENCH FILES ------
# ============================================================
def read_env(tb_dir: str) -> str:
    '''Read source files (.sv, .v) '''
    content = ""
    if not tb_dir or not os.path.exists(tb_dir):
        return content

    for root, _, files in os.walk(tb_dir):
        for file in files:
            if file.endswith(".sv") or file.endswith(".v"):
                
                if "DEBUG" in file or "ai_proposed" in file or "unknown_file" in file:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content += f"\n--- TB FILE: {file} ---\n{f.read()}\n"
                except Exception as e:
                    pass
    return content


# ==================================
# ------- GENERATOR NODE ------
# ==================================
def generator_node(state: AgentState):
    print("\n" + "="*60)
    print("[GENERATOR]: FIX ERRORS AND HOLES...")
    print("="*60)

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")

    plan = state.get("action_plan", "")
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)
    specs = state.get("dut_specs", "")
    user_command = state.get("user_command", "")
    target_file = state.get("target_file", "unknown_file.sv")

    working_dir = os.path.dirname(PROJECT_CONFIG["bat_file_path"])
    rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
    env_code = read_env(PROJECT_CONFIG.get("tb_dir", ""))

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
        
        system_prompt = "You are an Expert SystemVerilog and UVM Developer."
        user_prompt = f"""The simulation/compilation FAILED due to syntax or logical errors in the previously generated code.
        
                    VIVADO COMPILATION ERRORS:
                    {error}
                    Search in memory to find something to help you to fix the problem:
                    {memory_section}
        
                    CURRENT ENVIRONMENT AND RTL code:
                    {env_code}
                    {rtl_code}
        
                    DUT SPECIFICATIONS:
                    {specs}
        
                    YOUR TASK:
                    Based on the errors, identify which file is broken and rewrite it.
                    Return the ENTIRE updated code for that specific file. 
                    Enclose the SystemVerilog code in standard markdown ```systemverilog ... ``` blocks.
                    The VERY FIRST LINE inside the markdown block MUST be a comment with the exact file name you are modifying, like this:
                    // FILE: name_of_the_file.sv
                    """
    
    # ------ FIX HOLES -----
    else:
        print(f"[GENERATOR]: Updating '{target_file}' based on Analyzer's Action Plan...")
        system_prompt = "You are an Expert SystemVerilog and UVM Developer."
        user_prompt = f"""The Analyzer has identified a coverage hole and created an action plan.
                    ANALYZER'S ACTION PLAN:
                    {plan}
        
                    CURRENT ENVIRONMENT AND RTL:
                    {env_code}
                    {rtl_code}
                    
                    DUT SPECIFICATIONS:
                    {specs}
        
                    YOUR TASK:
                    You must update or create the following file(s): {target_file}
        
                    Read the CURRENT ENVIRONMENT code provided above. Find the current implementation of the requested files (or create new ones if necessary), and rewrite them completely to incorporate the fixes from the Action Plan.
        
                    CRITICAL OUTPUT FORMAT:
                    For EACH file you modify or create, enclose the complete updated code in its own standard markdown block (e.g., ```systemverilog ... ``` or ```tcl ... ```).
                    The VERY FIRST LINE inside EACH markdown block MUST be a comment with the exact file name, exactly like this:
                    // FILE: <name_of_the_file.ext>
        
                    ABSOLUTELY NO PLACEHOLDERS! You are writing to a disk that overwrites the file. DO NOT use shortcuts like "// ... existing code ..." or "// ... rest of the file ...". 
                    You MUST output the ENTIRE file from the very first line to the very last line, integrating the new classes alongside all the old ones. If the file is 200 lines long, you must print all 200 lines.
                 """
    
    # combine user prompt with system prompt for Groq
    full_prompt = system_prompt + "\n\n" + user_prompt
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
    #print("[GENERATOR]: Code generated successfully! Passing to Checker...")

    return {
        "generated_code": response.text,
        "iteration_tokens": total_tokens,
        "iterations": iterations + 1,
        "analyzer_mode": "code_review",  
        "status": "WAITING_FOR_HUMAN"
    }