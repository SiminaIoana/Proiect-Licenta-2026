from langgraph.graph import StateGraph, END, START
from typing import Literal
from config import initialize_llm
from state import AgentState
from nodes import rag_node, analyzer_node, generator_node, checker_node

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

    # initial state
    initial_state = {
        "dut_specs": "Synchronous FIFO. Ports: write_enable (we), read_enable (re), full_signal, empty_signal, data_in (32-bit), data_out (32-bit). Reset is active low.",
        "action_plan": "",
        "generated_code": "",
        "compilation_error": "",
        "iterations": 0
    }

    print("\n=============START LANGRGRAPH SYSTEM===============\n")
    app.invoke(initial_state)

if __name__ == "__main__":
    build_and_run()