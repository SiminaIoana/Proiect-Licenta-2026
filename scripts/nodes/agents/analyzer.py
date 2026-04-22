import os
from llama_index.core import Settings
from scripts.utils_files.memory import save_analyzer_experience
from scripts.utils_files.results_saving import get_index
from state import AgentState
import tiktoken
from config import PROJECT_CONFIG
import re
from utils_files.coverage import extract_coverage_holes, extract_coverage_percent, filter_log_for_hole
from utils_files.file_ops import read_rtl, read_env, read_simulation_log, read_run_script
from prompts.analyzer_prompt import ANALYZER_SYSTEM_PROMPT, ANALYZER_ROOT_CAUSE_PROMPT

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
        print(f"[DEBUG] fcov_report_path = '{fcov_path}'")
        print(f"[DEBUG] File exists = {os.path.exists(fcov_path)}")
    
        # ---- PARSE FCOV REPORT ----
        current_coverage = extract_coverage_percent(fcov_path)
        print(f"[ANALYZER]: Current coverage score = {current_coverage}%")

        raw_holes = extract_coverage_holes(fcov_path)
        
        print("\n--- DEBUG RAW HOLES ---")
        print(raw_holes)
        print("-----------------------\n")

        if raw_holes.startswith("ERROR:"):
            print(f"[ANALYZER ERROR]: {raw_holes}")
            return {
            "coverage_holes": raw_holes,
            "holes_list": [],
            "coverage_value": current_coverage,
            "status": "FAILED"
        }

        
        if "No obvious coverage holes" in raw_holes or raw_holes.strip() == "":
            print("[ANALYZER]: Target reached! No holes found.")
            return {
                "coverage_holes": raw_holes,
                "holes_list": [],
                "coverage_value": current_coverage,
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
                "coverage_value": current_coverage,
                "status": "ANALYSIS_COMPLETE"
            }
    #====================================
    # ---- ROOT CAUSE ----
    #====================================
    elif mode == "root_cause":
        current_hole = state.get("current_hole",{})
        hole_description = current_hole.get('description', 'Unknown Hole')
        current_coverage = state.get("coverage_value", 0.0)
        print(f"[ANALYZER]: Investigating root cause for -> {hole_description}")

        rtl_code = read_rtl(PROJECT_CONFIG.get("rtl_dir", ""))
        env_code = read_env(PROJECT_CONFIG.get("tb_dir", ""))
        sim_log = read_simulation_log(state.get("simulation_log_path", ""))

        specs = state.get("dut_specs", "")
        run_script = read_run_script(PROJECT_CONFIG.get("run_script_path", ""))

        sim_log_filtered = filter_log_for_hole(sim_log, hole_description)
        # ---- SAVING EXPERIENCE -----
        ltm_path = os.path.join("..", "results", "LTM_analyzer")
        past_experience=""
        try:
            if os.path.exists(ltm_path) and any(os.path.isfile(os.path.join(ltm_path, f)) for f in os.listdir(ltm_path)):
                index_ltm = get_index(ltm_path, "../DOCS/storage_ltm_analyzer/", "Analyzer LTM")
                if index_ltm:
                    query_engine = index_ltm.as_query_engine(similarity_top_k=1)
                    memory_response = query_engine.query(f"How did we fix a coverage hole like: {hole_description}")
                    past_experience = str(memory_response)
            else:
                print(f"[ANALYZER INFO]: No past experiences found in {ltm_path}. Starting from scratch.")
                past_experience = "No relevant past experience found."
        except Exception as e:
            print(f"[ANALYZER WARNING]: Memory indexing skipped: {e}")
            past_experience = "No relevant past experience found."
        
        # Secțiunea de memorie care va fi injectată în prompt
        memory_section = f"\nPAST SUCCESSFUL EXPERIENCE:\n{past_experience}" if past_experience else ""
        
        # Formatăm prompt-ul (Asigură-te că ANALYZER_ROOT_CAUSE_PROMPT din prompts.py are placeholder-ul {past_experience})
        prompt = ANALYZER_ROOT_CAUSE_PROMPT.format(
            current_coverage=current_coverage,
            hole_description=hole_description,
            sim_log_filtered=sim_log_filtered,
            rtl_code=rtl_code,
            env_code=env_code,
            run_script=run_script,
            specs=specs,
            past_experience=memory_section # Injectăm memoria aici
        )

        # Combinăm System Prompt cu User Prompt
        full_prompt = ANALYZER_SYSTEM_PROMPT + "\n\n" + prompt

        # Trimiterea cererii către LLM
        response = llm.complete(full_prompt)

        # prompt tokens (Atenție să folosești full_prompt aici)
        prompt_tokens = len(encoding.encode(full_prompt))
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

        new_coverage = extract_coverage_percent(fcov_path)
        old_coverage = state.get("coverage_value", 0.0)
        target_hole = state.get("current_hole", {}).get("description", "")

        if new_coverage > old_coverage:
            trend = f"📈 Coverage improved: {old_coverage}% → {new_coverage}%"
        elif new_coverage < old_coverage:
            trend = f"📉 Coverage DECREASED: {old_coverage}% → {new_coverage}% (rollback recommended!)"
        else:
            trend = f"➡️ Coverage unchanged: {new_coverage}%"
            
        if target_hole and target_hole not in new_holes_str:
            hole_result = f"✅ SUCCESS! The hole was fixed and covered."
            action_plan = state.get("action_plan", "")
            success_code = state.get("generated_code", "")
            
            save_analyzer_experience(target_hole, action_plan, success_code)
        else:
            hole_result = f"❌ FAILED. The hole is STILL UNCOVERED."

        analysis_result = f"{trend}\n{hole_result}"
        holes_lines = [line.strip() for line in new_holes_str.split("\n") if line.strip().startswith("-")]
        updated_list = [{"id": idx + 1, "description": line} for idx, line in enumerate(holes_lines)]

        return {
            "coverage_holes": new_holes_str,
            "holes_list": updated_list,
            "root_cause_hole": analysis_result,
            "coverage_value": new_coverage, 
            "status": "ANALYSIS_COMPLETE",
            "analyzer_mode": "compare_results" 
        }
    
    else:
        print(f"Unknown Mode '{mode}'")
        return {
            "status":"FAILED"
        }