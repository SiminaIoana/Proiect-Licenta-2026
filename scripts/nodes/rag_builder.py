from llama_index.core import Settings
from state import AgentState
from utils_files.results_saving import get_index
import tiktoken
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from config import PROJECT_CONFIG
import time
from utils_files.results_saving import save_agent_metrics

token_counter = TokenCountingHandler(
    tokenizer=tiktoken.get_encoding("cl100k_base").encode
)

Settings.callback_manager = CallbackManager([token_counter])

# NODE 0 --> RAG-node
def rag_node(state: AgentState):
     
     print("\nNode 0 RAG NODE: Searching documentation...")
     start_time = time.time()
     token_counter.reset_counts()

     dynamic_path = PROJECT_CONFIG["dynamic_docs_path"]
     static_path = PROJECT_CONFIG["static_docs_path"]
     query_context = PROJECT_CONFIG["rag_search_query"]
    
     index_dynamic = get_index(dynamic_path, "../DOCS/storage_dynamic/", "Dynamic index")
     index_static = get_index(static_path, "../DOCS/storage_static/", "Static index")
    
     dynamic_query = f"""
Analyze the verification project context for the selected coverage hole: '{query_context}'.

Extract the information that is useful for understanding and fixing this coverage hole:
- DUT/module interface: ports, directions, bit-widths, and signal meaning;
- relevant transaction class fields, using their exact names;
- relevant driver, monitor, subscriber, scoreboard, sequence, and test behavior;
- existing covergroups, coverpoints, bins, crosses, and sampling conditions;
- reset behavior and any protocol/state constraints that affect valid stimulus generation;
- existing sequences/tests that may already target or miss this scenario;
- run script information, including which tests are currently executed.

Focus on exact names from the project code. 
Do not assume signal names. If a detail is not present in the context, state that it was not found.
Return the answer in concise structured bullet points.
"""
     dynamic_response = index_dynamic.as_query_engine().query(dynamic_query)

     static_query = """
Provide concise UVM/SystemVerilog guidelines useful for analyzing and fixing functional coverage holes in a UVM testbench.

Include rules about:
- defining and sampling covergroups inside uvm_subscriber#(transaction);
- writing valid coverpoints, bins, iff conditions, and cross coverage;
- generating directed UVM sequences and tests for uncovered bins;
- keeping stimulus valid with respect to DUT state, reset, full/empty conditions, and protocol constraints;
- using exact transaction fields and avoiding undeclared signals;
- connecting new tests and sequences correctly through the UVM factory;
- updating Vivado/XSim run scripts to execute additional tests;
- common mistakes in generated SystemVerilog/UVM code, especially syntax errors, missing semicolons, invalid randomize-with blocks, missing factory registration, and wrong hierarchy paths;
- Vivado/XSim-compatible SystemVerilog syntax.

Return practical rules, not a general tutorial.
"""
     static_response = index_static.as_query_engine().query(static_query)
     print("[RAG DEBUG] dynamic_response chars =", len(str(dynamic_response)))
     print("[RAG DEBUG] static_response chars =", len(str(static_response)))

     encoding = tiktoken.get_encoding("cl100k_base")
     print("[RAG DEBUG] dynamic_response tokens =", len(encoding.encode(str(dynamic_response))))
     print("[RAG DEBUG] static_response tokens =", len(encoding.encode(str(static_response))))

     print("[RAG DEBUG] dynamic_response preview:")
     print(str(dynamic_response))

     print("[RAG DEBUG] static_response preview:")
     print(str(static_response))
     rag_tokens = token_counter.total_llm_token_count
     duration = round(time.time() - start_time, 2)

     save_agent_metrics(
    agent_name="rag",
    phase=str(state.get("phase", "")),
    hole_description="",
    prompt_tokens=0,
    response_tokens=0,
    total_tokens=rag_tokens,
    duration_seconds=duration,
    status="SUCCESS",
    notes="static_docs + dynamic_docs"
)

     return {
        "uvm_rules": str(static_response), 
        "dut_specs": str(dynamic_response),
        "iteration_tokens": rag_tokens
     }
