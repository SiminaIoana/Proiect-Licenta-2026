import os
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from llama_index.llms.groq import Groq
from typing import Literal
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings, StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader

#load environment variables
load_dotenv()
# initialize LLM
llm = Groq(model="llama-3.3-70b-versatile")

# initialize the embedding
embed_model=HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

# global settings
from llama_index.core import Settings
Settings.llm=llm
Settings.embed_model=embed_model

# system memory
class AgentState(TypedDict):
    dut_specs: str
    action_plan: str
    generated_code: str
    compilation_error: str
    iterations: int

# NODE 1 --> Analyzer
def analyzer_node(state: AgentState):
    print("\n\n Node 1 ANALYZER: Reading specification..")
    specs = state.get("dut_specs", "")

    prompt = f"""You are an Expert Verification Engineer. 
Based on the following DUT specifications, create a detailed Action Plan for a UVM coverage container class (`uvm_subscriber`). 
Clearly define the Covergroups, Coverpoints, Bins, and Cross Coverage required.

DUT Specifications:
{specs}

Output the Action Plan clearly formatted."""
    
    response = llm.complete(prompt)

    return {"action_plan": response.text}

# NODE 2 --> Generator
def generator_node(state: AgentState):
    print("\n\n Node 1 GENERATOR: Reading the action plan and writing SV code...")
    plan = state.get("action_plan", "")

    system_prompt = """You are an Expert SystemVerilog and UVM Developer. 
Your ONLY task is to write clean, compilable, and production-ready SystemVerilog code based on an Action Plan.
STRICT RULES:
1. Output ONLY the SystemVerilog code inside a ```systemverilog ... ``` code block.
2. DO NOT write any conversational text, explanations, or pleasantries before or after the code block.
3. Use proper UVM macros (`uvm_component_utils`).
4. Ensure the covergroups are instantiated in the constructor (new function) and sampled in the write() method.
5. Assume the transaction class is named `fifo_seq_item`.
"""

    user_prompt = f"""
Write the `fifo_coverage_container.sv` class based strictly on this Action Plan:
{plan}
"""
    
    # combine user prompt with system prompt for Groq
    full_prompt = system_prompt + "\n\n" + user_prompt
    response = llm.complete(full_prompt)

    return {"generated_code": response.text}


def build_and_run():
    # initialize graph
    workflow = StateGraph(AgentState)

    # adding nodes for analyzer and generator
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("generator", generator_node)

    # define flow
    workflow.add_edge(START, "analyzer")
    workflow.add_edge("analyzer", "generator")
    workflow.add_edge("generator", END)

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
    
    final_state = app.invoke(initial_state)

    print("\n=============GENERATE SYSTEM VERILOG CODE:===============\n")
    print(final_state["generated_code"])


if __name__ == "__main__":
    build_and_run()

