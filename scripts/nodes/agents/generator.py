from llama_index.core import Settings
from state import AgentState
from utils import get_index, read_specific_files
import os
import tiktoken
from config import PROJECT_CONFIG



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
        
        system_prompt = "You are an Expert SystemVerilog and UVM Developer."
        user_prompt = f"""The simulation/compilation FAILED due to syntax or logical errors in the previously generated code.
        
                    VIVADO COMPILATION ERRORS:
                    {error}
                    Search in memory to find something to help you to fix the problem:
                    {memory_section}
        
                    CURRENT ENVIRONMENT AND RTL code that needs to be fixed:
                    {target_code}
        
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
                    {target_code}
                  
                    DUT SPECIFICATIONS:
                    {specs}
        
                    YOUR TASK:
                    Based on the Action Plan, generate ONLY the NEW code that needs to be appended to the target files (e.g., the new sequence class and the new test class).
                    
                    CRITICAL INSTRUCTIONS:
                    1. DO NOT rewrite or output the existing classes or existing code from the provided files.
                    2. ONLY output the new classes that need to be added.
                    3. For the new test class, ensure you properly instantiate the sequence and start it using the correct hierarchy from the current environment (e.g., seq.start(environment_h.agent_h.sequencer_h);).
                    4. Enclose the code for each file in its own standard markdown block (```systemverilog ... ```).
                    5. The VERY FIRST LINE inside EACH markdown block MUST be a comment with the exact file name you are targeting:
                       // FILE: <name_of_the_file.ext>
                    
                    CRITICAL OUTPUT FORMAT FOR MODIFICATIONS:
                    If you need to MODIFY an existing line (like changing the test name in top.sv), you MUST use this exact format:
                    <<<< SEARCH
                    (exact old code here)
                        ==== REPLACE
                    (new modified code here)
                    >>>>

                    If you are just ADDING a completely new class, just output the class code normally.
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

    return {
        "generated_code": response.text,
        "iteration_tokens": total_tokens,
        "iterations": iterations + 1,
        "analyzer_mode": "code_review",  
        "status": "WAITING_FOR_HUMAN"
    }