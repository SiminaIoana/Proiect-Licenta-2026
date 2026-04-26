import os
import datetime
import time
import csv
from langgraph.graph import StateGraph, END, START
from typing import Literal
from config import initialize_llm
from scripts.utils_files.phases import Phase
from scripts.utils_files.status import Status
from state import AgentState
from nodes.rag_builder import rag_node
from nodes.agents.analyzer import analyzer_node
from nodes.agents.generator import generator_node
from nodes.checking import checker_node
from nodes.human_interaction_node import human_interaction_node, restore_rollback_files
from config import PROJECT_CONFIG
# init LLM
initialize_llm()

def phase_controller_node(state: AgentState):
    phase = state.get("phase", Phase.INIT)
    status = state.get("status", Status.PROCESSING)
    cmd = state.get("user_command", "").strip().lower()

    next_phase = phase

    if phase == Phase.INIT:
        next_phase = Phase.RUN_CHECKER

    elif phase == Phase.RUN_CHECKER:
        if status == Status.FAILED:
            next_phase = Phase.ERROR_ANALYSIS
        else:
            next_phase = Phase.BUILD_HOLES_LIST

    elif phase == Phase.BUILD_HOLES_LIST:
        holes = state.get("holes_list", [])
        if status == Status.FAILED:
            next_phase = Phase.ERROR_ANALYSIS
        elif not holes:
            next_phase = Phase.RESULT_REVIEW
        else:
            next_phase = Phase.SELECT_HOLE
    
    elif phase == Phase.SELECT_HOLE:
        if cmd == "fix_hole":
            next_phase = Phase.ROOT_CAUSE_ANALYSIS
        elif cmd in ["quit", "q"]:
            next_phase = Phase.DONE

    elif phase == Phase.ROOT_CAUSE_ANALYSIS:
        next_phase = Phase.PLAN_REVIEW

    elif phase == Phase.COMPARE_RESULTS:
        next_phase = Phase.RESULT_REVIEW
    
    elif phase == Phase.RESULT_REVIEW:
        coverage = state.get("coverage_value", 0.0)
        holes = state.get("holes_list", [])

        if cmd in ["quit", "q"]:
            next_phase = Phase.DONE
        elif cmd == "show_list":
            next_phase = Phase.SELECT_HOLE
        elif cmd == "retry_same_hole":
            next_phase = Phase.ROOT_CAUSE_ANALYSIS
        elif cmd == "rollback":
            next_phase = Phase.ROLLBACK

    elif phase == Phase.ERROR_ANALYSIS:
        next_phase = Phase.PLAN_REVIEW

    elif phase == Phase.PLAN_REVIEW:
        if cmd in ["approve_plan", "fix_syntax"]:
            next_phase = Phase.CODE_GENERATION
        elif cmd == "show_list":
            next_phase = Phase.BUILD_HOLES_LIST
        elif cmd in ["quit", "q"]:
            next_phase = Phase.DONE

    elif phase == Phase.CODE_GENERATION:
        next_phase = Phase.CODE_REVIEW
        
    elif phase == Phase.CODE_REVIEW:
        if cmd == "approve_code":
            next_phase = Phase.RUN_AFTER_FIX
        elif cmd == "reject_code":
            next_phase = Phase.ROOT_CAUSE_ANALYSIS
        elif cmd in ["quit", "q"]:
            next_phase = Phase.DONE

    elif phase == Phase.ROLLBACK:
        next_phase = Phase.RUN_CHECKER

    elif phase == Phase.RUN_AFTER_FIX:
        if status == Status.FAILED:
            next_phase = Phase.RESULT_REVIEW
        else:
            next_phase = Phase.COMPARE_RESULTS

    return {
        "phase": next_phase,
        "user_command": ""
    }

def route_from_phase_controller(state: AgentState):
    phase = state.get("phase", Phase.INIT)

    if phase in [Phase.RUN_CHECKER, Phase.RUN_AFTER_FIX]:
        return "checker"

    elif phase in [
        Phase.BUILD_HOLES_LIST,
        Phase.ROOT_CAUSE_ANALYSIS,
        Phase.COMPARE_RESULTS,
        Phase.ERROR_ANALYSIS
    ]:
        return "analyzer"

    elif phase in [
        Phase.SELECT_HOLE,
        Phase.PLAN_REVIEW,
        Phase.CODE_REVIEW,
        Phase.RESULT_REVIEW
    ]:
        return "human_interaction"

    elif phase == Phase.CODE_GENERATION:
        return "generator"
    
    elif phase == Phase.ROLLBACK:
        return "rollback"
    
    elif phase == Phase.DONE:
        return END

    return END

def route_from_start(state: AgentState):
    if not state.get("dut_specs") or not state.get("uvm_rules"):
        return "rag_builder"
    return "phase_controller"

def route_from_human(state: AgentState):
    cmd = state.get("user_command", "").strip().lower()

    if cmd == "":
        return END

    return "phase_controller"

# =====================================================
# ----------- BUILD LANGGRAPH SYSTEM ------------------
# =====================================================
workflow = StateGraph(AgentState)

workflow.add_node("phase_controller", phase_controller_node)
workflow.add_node("rag_builder", rag_node)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("generator", generator_node)
workflow.add_node("checker", checker_node)
workflow.add_node("human_interaction", human_interaction_node)
workflow.add_node("rollback", restore_rollback_files)
# START
workflow.add_conditional_edges(START, route_from_start)
workflow.add_edge("rag_builder", "phase_controller")
workflow.add_edge("rollback", "phase_controller")

# CONTROL FLOW
workflow.add_conditional_edges("phase_controller", route_from_phase_controller)

# BACK EDGES
workflow.add_edge("checker", "phase_controller")
workflow.add_edge("analyzer", "phase_controller")
workflow.add_edge("generator", "phase_controller")
workflow.add_conditional_edges("human_interaction", route_from_human)

app_graph = workflow.compile()
# =====================================================
# ----------- TERMINAL EXECUTION -----------
# =====================================================

def build_and_run():
    initial_state = {
        "holes_list": [],
        "current_hole": {},
        "root_cause_hole": "",
        "ui_message": "",
        "ui_input": "",
        "fcov_report_path": "",
        "simulation_log_path": "",
        "dut_specs": "",        
        "uvm_rules": "",
        "action_plan": "",
        "generated_code": "",
        "target_file": "",      
        "iterations": 0,
        "rollback_files": {},
        "compilation_error": "",
        "coverage_holes":"",
        "iteration_tokens": 0,
        "user_command":"",
        "coverage_value":0.0,
        "previous_coverage":0.0,
        "phase": Phase.INIT,
        "status": Status.PROCESSING,
    }
    print("\n============= START LANGRGRAPH SYSTEM ===============\n")
  
    start_time = time.time()
    final_state = app_graph.invoke(initial_state)
    end_time = time.time()

    total_time = end_time - start_time
    total_iterations = final_state.get("iterations", 0)

    results = os.path.join("..", "results")
    os.makedirs(results, exist_ok=True)
    csv_path = os.path.join(results, "global_results.csv")

    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Total Execution Time (s)", "Total Iterations"])
        
        timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M")
        writer.writerow([timestamp, f"{total_time:.2f}", total_iterations])
    
    print("\n============= STOP LANGRGRAPH SYSTEM ===============\n")

if __name__ == "__main__":
    build_and_run()
