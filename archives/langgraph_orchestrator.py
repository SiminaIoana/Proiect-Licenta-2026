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

#create or load index
def get_index(data_dir: str, storage_dir: str, index_name: str):
    """
    Verify the directories, read documents and create the index. If the index exist, it will be loaded
    """
    try:
        print(f"Loading existing {index_name} from '{storage_dir}.'")
        storage_context=StorageContext.from_defaults(persist_dir=storage_dir)
        index=load_index_from_storage(storage_context)
        print(f"Successfully loaded {index_name}!")
        return index
    
    except(FileNotFoundError, ValueError):
        #storage_dir does not exists
        print(f"Storage not found. Creating {index_name} from '{storage_dir}'")

        try:
            #read documents
            documents = SimpleDirectoryReader(input_dir=data_dir).load_data()

            # transform documents in indexes
            index = VectorStoreIndex.from_documents(documents)

            #save the index
            index.storage_context.persist(persist_dir=storage_dir)
            print(f"{index_name} created and saved in '{storage_dir}'")
            return index
        
        except ValueError as e:
            #directory does not exists or is empty
            print(f"Error: The '{data_dir}' folder does not exists or is empty!")
            print(f"Detailed LlamIndex error : {e}")
            return None

        except Exception as e:
            #any other error catched
            print(f"An unexpected error occurred while created {index_name}: {e}")
            return None



# system memory
class AgentState(TypedDict):
    dut_specs: str
    action_plan: str
    generated_code: str
    compilation_error: str
    iterations: int

# NODE 0 --> RAG-node
def rag_node(state: AgentState):
     print("\n\n Node 0 RAG NODE: Searching documentation...")
     user_query = state.get("dut_specs", "General specification")
    
     index = get_index("../DOCS/rag_data_dynamic/", "../DOCS/storage_dynamic/", "Specs")
     query_engine = index.as_query_engine()

     # test 
     query = "List all ports, signals, bit-widths, and functional behavior for the FIFO design described in the docs."
     response = query_engine.query(query)
     return {"dut_specs": response.response}


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
    plan = state.get("action_plan", "")
    # getting errors if exists
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)

    # if errors appeared
    if error != "":
        print(f"\n\n Node 2 GENERATOR: Fixing problems and rewrite the code: Iteration number: {iterations+1}")
        user_prompt = f"The previous code had this error: {error}. Please fix it and output the full code again." 
    else:
        print("\n\n Node 2 GENERATOR: Reading the action plan and writing SV code...")
        user_prompt = f"""
                    Write the `fifo_coverage_container.sv` class based strictly on this Action Plan:
                    {plan}
                    """
        
    system_prompt = """You are an Expert SystemVerilog and UVM Developer. 
                    Your ONLY task is to write clean, compilable, and production-ready SystemVerilog code based on an Action Plan.
                    STRICT RULES:
                    1. Output ONLY the SystemVerilog code inside a ```systemverilog ... ``` code block.
                    2. DO NOT write any conversational text, explanations, or pleasantries before or after the code block.
                    3. Use proper UVM macros (`uvm_component_utils`).
                    4. Ensure the covergroups are instantiated in the constructor (new function) and sampled in the write() method.
                    5. Assume the transaction class is named `fifo_seq_item`.
                    """
    # combine user prompt with system prompt for Groq
    full_prompt = system_prompt + "\n\n" + user_prompt
    response = llm.complete(full_prompt)

    return {"generated_code": response.text, "iterations": iterations+1}


# node for verification
def checker_node(state: AgentState):
    print("\n\nNODE 3 Checker: Validate generated code...")
    code = state.get("generated_code", "")

    # verify write function
    if "write(fifo_seq_item t)" in code and "item." in code:
        error_msg = "Sintax Error: In the write() method, the argument is named 't', but you used 'item.<signal>'. Please use 't.<signal>'."
        return {"compilation_error": error_msg}
    
    # no specific errors
    return {"compilation_error": ""}


# node for decisions
def decision_step(state: AgentState) -> Literal["generator", "__end__"]:
    error = state.get("compilation_error", "")
    iteration = state.get("iterations",0)

    # errors generated 
    if error != "" and iteration < 3:
        print(f"\nError detected. Redirecting to Generator")
        return "generator"
    
    # code works
    print(f"----Code is verified and works properly!---")
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
    
    final_state = app.invoke(initial_state)

    print("\n=============GENERATE SYSTEM VERILOG CODE:===============\n")
    print(final_state["generated_code"])


if __name__ == "__main__":
    build_and_run()

