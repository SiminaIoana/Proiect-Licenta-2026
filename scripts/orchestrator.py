import os
import datetime
import time
import csv
from langgraph.graph import StateGraph, END, START
from typing import Literal
from config import initialize_llm
from state import AgentState
from nodes.rag_builder import rag_node
from nodes.agents.analyzer import analyzer_node
from nodes.agents.generator import generator_node
from nodes.checking import checker_node
from nodes.human_interaction_node import human_interaction_node 
from config import PROJECT_CONFIG

# init LLM
initialize_llm()

# =====================================================
# ----------- ROUTING FROM START ----------------------
# =====================================================
def route_from_start(state: AgentState):
    if state.get("status") == "IDLE":
        return END
    if state.get("status") == "WAITING_FOR_HUMAN":
        return "human_interaction"
    return "rag_builder"

# =====================================================
# ----------- ROUTING FROM CHECKER -------------------
# =====================================================
def route_from_checker(state: AgentState):
    print("[ROUTING]: Routing to ANALYZER...")
    return "analyzer"

# =====================================================
# ----------- ROUTING FROM ANALYZER -------------------
# =====================================================
def route_from_analyzer(state: AgentState):
    print("\n[ROUTING]: Routing to HUMAN INTERACTION...")
    return "human_interaction"

# =====================================================
# ----------- ROUTING FROM HUMAN -------------------
# =====================================================
def route_from_human(state: AgentState):
    if state.get("status") == "WAITING_FOR_HUMAN":
        print("[ROUTING]: System is on PAUSE. Waiting for UI input...")
        return END

    cmd = state.get("user_command", "").strip().lower()
    
    if cmd in ["stop", "exit", "quit", ""]:
        return END
    elif cmd in ["fix_syntax", "approve_plan", "reject_code"]:
        return "generator"
    elif cmd in ["fix_hole", "show_list"]:
        return "analyzer"
    elif cmd == "approve_code":
        return "checker" 
        
    return END
# =====================================================
# ----------- BUILD LANGGRAPH SYSTEM ------------------
# =====================================================
workflow = StateGraph(AgentState)

workflow.add_node("rag_builder", rag_node)
workflow.add_node("analyzer", analyzer_node)
workflow.add_node("generator", generator_node)
workflow.add_node("checker", checker_node)
workflow.add_node("human_interaction", human_interaction_node)

# Flow definitions
workflow.add_conditional_edges(START, route_from_start) 
workflow.add_edge("rag_builder", "checker")
workflow.add_edge("generator", "human_interaction")

workflow.add_conditional_edges("checker", route_from_checker)
workflow.add_conditional_edges("analyzer", route_from_analyzer)
workflow.add_conditional_edges("human_interaction", route_from_human)

app_graph = workflow.compile()


# =====================================================
# ----------- TERMINAL EXECUTION -----------
# =====================================================

def build_and_run():
    initial_state = {
        "dut_specs": "",        
        "uvm_rules": "",
        "action_plan": "",
        "generated_code": "",
        "target_file": "",      
        "analyzer_mode": "",
        "iterations": 0,
        "compilation_error": "",
        "coverage_holes":"",
        "status" : "",
        "iteration_tokens": 0,
        "user_command":""
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