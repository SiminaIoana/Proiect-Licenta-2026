from llama_index.core import Settings
from state import AgentState
from utils_files.results_saving import get_index
import tiktoken
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from config import PROJECT_CONFIG

token_counter = TokenCountingHandler(
    tokenizer=tiktoken.get_encoding("cl100k_base").encode
)

Settings.callback_manager = CallbackManager([token_counter])

# NODE 0 --> RAG-node
def rag_node(state: AgentState):
     
     print("\nNode 0 RAG NODE: Searching documentation...")

     token_counter.reset_counts()

     dynamic_path = PROJECT_CONFIG["dynamic_docs_path"]
     static_path = PROJECT_CONFIG["static_docs_path"]
     query_context = PROJECT_CONFIG["rag_search_query"]
    
     index_dynamic = get_index(dynamic_path, "../DOCS/storage_dynamic/", "Dynamic index")
     index_static = get_index(static_path, "../DOCS/storage_static/", "Static index")
    
     dynamic_query = f"""
     Analyze the design for: '{query_context}'. 
     Extract all ports, signals, bit-widths, and functional behavior.
     CRITICAL: Identify exact names of variables in the 'transaction' class 
     (e.g., we, re, data_in, full, empty) to be used for UVM coverpoints.
     """
     dynamic_response = index_dynamic.as_query_engine().query(dynamic_query)

     static_query = "Provide the syntax rules and a template for a UVM subscriber implementing functional coverage with a covergroup."
     static_response = index_static.as_query_engine().query(static_query)

     rag_tokens = token_counter.total_llm_token_count

     return {
        "uvm_rules": str(static_response), 
        "dut_specs": str(dynamic_response),
        "iteration_tokens": rag_tokens
     }
