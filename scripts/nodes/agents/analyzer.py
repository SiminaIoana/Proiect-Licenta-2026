from llama_index.core import Settings
from state import AgentState
import tiktoken
from config import PROJECT_CONFIG
import re
from utils import extract_coverage_holes,extract_code, read_rtl,read_env,read_simulation_log,read_run_script,query_analyzer_memory

# ==================================
# ------- ANALYZER NODE ------
# ==================================
def analyzer_node(state: AgentState):

    mode = state.get("analyzer_mode","")
    print(f"\n[ANALYZER]: Executing mode -> [{mode}]")

    llm = Settings.llm
    encoding = tiktoken.get_encoding("cl100k_base")
    
    #====================================
    # ---- BUILDING HOLES LIST ----
    #====================================
    if mode == "build_holes_list":
        fcov_path = state.get("fcov_report_path", "")
    
        # ---- PARSE FCOV REPORT ----
        raw_holes = extract_coverage_holes(fcov_path)
        '''
        print("\n--- DEBUG RAW HOLES ---")
        print(raw_holes)
        print("-----------------------\n")
        '''
        if "No obvious coverage holes" in raw_holes or raw_holes.strip() == "":
            print("[ANALYZER]: Target reached! No holes found.")
            return {
                "coverage_holes": raw_holes,
                "holes_list": [],
                "status": "ANALYSIS_COMPLETE" 
            }
        else:
            # --- EXTRACT LIST OF HOLES ---
            holes_lines = [line.strip() for line in raw_holes.split("\n") if line.strip().startswith("-")]
            structured_list = []
            for idx, line in enumerate(holes_lines):
                structured_list.append({
                    "id": idx + 1,
                    "description": line
                })
            
            print(f"[ANALYZER]: Found {len(structured_list)} holes.")
            
            return {
                "coverage_holes": raw_holes, 
                "holes_list": structured_list,
                "status": "ANALYSIS_COMPLETE"
            }
    #====================================
    # ---- ROOT CAUSE ----
    #====================================
    elif mode == "root_cause":
        current_hole = state.get("current_hole",{})
        hole_description = current_hole.get('description', 'Unknown Hole')

        print(f"[ANALYZER]: Investigating root cause for -> {hole_description}")

        rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
        env_code = read_env(PROJECT_CONFIG.get("tb_dir", ""))
        sim_log = read_simulation_log(state.get("simulation_log_path", ""))

        specs = state.get("dut_specs", "")
        run_script = read_run_script(PROJECT_CONFIG.get("run_script_path", ""))
        # ---- SAVING EXPERIENCE -----
        #past_experience = query_analyzer_memory(hole_description)
        #memory_section = f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}" if past_experience else ""
        prompt = f"""You are an Expert UVM Verification Architect.
                    We have a specific coverage hole in our FCOV report. Your job is to act as a detective and find out WHY it is happening and HOW to fix it.
        
                    --- TARGET COVERAGE HOLE ---
                    {hole_description}
        
                    --- SIMULATION LOG (xsim.log summary) ---
                    {sim_log}
        
                    --- RTL DESIGN & UVM TESTBENCH FILES ---
                    {rtl_code}
                    {env_code}

                    --- RUN SCRIPT (Execution context) ---
                    {run_script}
                    --- DUT SPECIFICATIONS ---
                    {specs}
        
                    INSTRUCTIONS FOR UVM DIAGNOSTIC:
                    Perform a holistic check of the provided environment. Apply these universal UVM debugging rules:
                    1. Run-Time Check: Look at the RUN SCRIPT. Does this test actually instantiate and start the sequence needed to cover the hole?
                    2. Topology Check: Is the monitor's analysis port correctly connected to the coverage collector/subscriber?
                    3. Stimulus Generation: If the hole requires new stimulus, DO NOT just hardcode narrow constraints into existing base/general sequences. Instead, suggest creating a NEW directed sequence class. 
                    CRITICAL RULE: Always APPEND new sequence classes or test classes into the ALREADY EXISTING files (e.g., sequence.sv, test.sv). DO NOT create brand new .sv files for them!
        
                     CRITICAL OUTPUT RULES:
                    - Your response MUST be in NATURAL LANGUAGE ONLY.
                    - YOU ARE STRICTLY FORBIDDEN from outputting ANY ```systemverilog```, ```verilog```, or code blocks.
                    - You are the ARCHITECT. You only write the plan. The Generator will write the code.
        
                    CRITICAL OUTPUT FORMAT:
                    You MUST output your response exactly in the following structure:
                    ROOT CAUSE ANALYSIS: <Explain why the hole exists based on the logs and code>
                    ACTION PLAN: <Explain step-by-step what exact logic the Generator must add/modify>
                    TARGET_FILES: <filename1.sv>, <filename2.sv>
                """
        
        response = llm.complete(prompt)
        # prompt tokens 
        prompt_tokens = len(encoding.encode(prompt))

        #responde tokens
        response_tokens = len(encoding.encode(response.text))

        current_tokens = state.get("iteration_tokens", 0)
        total_tokens = prompt_tokens + response_tokens + current_tokens

        target_file_match = re.search(r'TARGET_FILES?:\s*([a-zA-Z0-9_.,\s`\'"]+)', response.text, re.IGNORECASE)
        
        if target_file_match:
            target_file = target_file_match.group(1).replace('`', '').replace('"', '').replace("'", "").strip()
        else:
            target_file = "unknown_file.sv"
            
        print(f"[DEBUG] Extracted TARGET_FILES: {target_file}")

        return {
            "root_cause_hole": "LLM Analysis Generated", 
            "action_plan": response.text, 
            "target_file": target_file,
            "iteration_tokens": total_tokens,
            "status": "ANALYSIS_COMPLETE"
        }

    #====================================
    # ---- SYNTAX DEBUG ----
    #====================================
    elif mode == "syntax_debug":
        print("[ANALYZER]: Syntax error detected. Preparing data for human review/generator fix.")
        return {
            "status": "FAILED",  
            "analyzer_mode": "syntax_debug"
        }
    
    #====================================
    # ---- COMPARE RESULTS ----
    #====================================
    elif mode == "compare_results":
        print("[ANALYZER]: Comparing new FCOV report with previous state...")

        fcov_path = state.get("fcov_report_path", "")
        new_holes_str = extract_coverage_holes(fcov_path)

        target_hole = state.get("current_hole", {}).get("description", "")

        analysis_result = ""
        if target_hole and target_hole not in new_holes_str:
            analysis_result = f" SUCCESS! The hole '{target_hole}' was successfully fixed and covered."
        else:
            analysis_result = f" FAILED. The code compiled, but '{target_hole}' is STILL UNCOVERED."
            
            
        holes_lines = [line.strip() for line in new_holes_str.split("\n") if line.strip().startswith("-")]
        updated_list = [{"id": idx + 1, "description": line} for idx, line in enumerate(holes_lines)]

        return {
            "coverage_holes": new_holes_str,
            "holes_list": updated_list,
            "root_cause_hole": analysis_result, 
            "status": "ANALYSIS_COMPLETE",
            "analyzer_mode": "compare_results" # Forțăm păstrarea acestui mod
        }
    
    else:
        print(f"Unknown Mode '{mode}'")
        return {
            "status":"FAILED"
        }