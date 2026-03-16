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
# inti LLM
initialize_llm()

# node for decisions
def decision_step(state: AgentState) -> Literal["generator", "__end__"]:
    error = state.get("compilation_error", "")
    iteration = state.get("iterations",0)

    # errors generated 
    if error != "" and iteration < 5 and "SYSTEM ERROR" not in error:
        print(f"\nError detected. Redirecting to Generator")
        return "generator"
    
    # code works
    return "__end__"


def build_and_run():
    # initialize graph
    workflow = StateGraph(AgentState)

    # adding rag_node
    workflow.add_node("rag_builder", rag_node)

    # adding nodes for analyzer and generator
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("generator", generator_node)

    #adding checker node
    workflow.add_node("checker", checker_node)

    # define flow
    workflow.add_edge(START, "rag_builder")
    workflow.add_edge("rag_builder", "analyzer")

    # flow without rag_builder for experimental results
    #workflow.add_edge(START, "analyzer")
    workflow.add_edge("analyzer", "generator")
    workflow.add_edge("generator", "checker")

    # conditional edge
    workflow.add_conditional_edges("checker", decision_step, {"generator":"generator", "__end__" : END })

    # compile
    app = workflow.compile()

    initial_state = {
        "dut_specs": "Synchronous FIFO. Ports: write_enable (we), read_enable (re), full_signal, empty_signal, data_in (32-bit), data_out (32-bit). Reset is active low.",
        "action_plan": "",
        "generated_code": "",
        "compilation_error": "",
        "iterations": 0
    }
    print("\n============= START LANGRGRAPH SYSTEM ===============\n")

    start_time = time.time()
    final_state = app.invoke(initial_state)
    end_time = time.time()

    total_time = end_time - start_time
    total_iterations = final_state.get("iterations", 0)

    # saved the metrics in file
    results = os.path.join("..", "results")
    os.makedirs(results, exist_ok=True)
    csv_path = os.path.join(results, "global_results.csv")

    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Total Execution Time (s)", "Total Iterations"])
        
        # date, time for saving metrics
        timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M")
        writer.writerow([timestamp, f"{total_time:.2f}", total_iterations])
    
        print("\n============= STOP LANGRGRAPH SYSTEM ===============\n")


if __name__ == "__main__":
    build_and_run()