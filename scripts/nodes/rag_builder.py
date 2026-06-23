import time
import tiktoken
from state import AgentState
from config import PROJECT_CONFIG
from llama_index.core import Settings
from utils_files.results_saving import get_index, save_agent_metrics
from prompts.rag_builder_prompt import DYNAMIC_RAG_QUERY, STATIC_RAG_QUERY
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler


token_counter = TokenCountingHandler(
    tokenizer=tiktoken.get_encoding("cl100k_base").encode
)

Settings.callback_manager = CallbackManager([token_counter])

def rag_node(state: AgentState):
     """
     Builds the RAG context..
     The node retrieves project-specific DUT/testbench information from dynamic documentation and general UVM/SystemVerilog rules from static documentation.
     """
     print("\n[RAG NODE]: Searching documentation...")
     start_time = time.time()
     token_counter.reset_counts()

     # Paths for documentation
     dynamic_path = PROJECT_CONFIG["dynamic_docs_path"]
     static_path = PROJECT_CONFIG["static_docs_path"]
     query_context = PROJECT_CONFIG["rag_search_query"]
    
     index_dynamic = get_index(dynamic_path, "../DOCS/storage_dynamic/", "Dynamic index")
     index_static = get_index(static_path, "../DOCS/storage_static/", "Static index")
    
     dynamic_query = DYNAMIC_RAG_QUERY.format(query_context=query_context)
     dynamic_response = index_dynamic.as_query_engine().query(dynamic_query)

     static_query = STATIC_RAG_QUERY
     static_response = index_static.as_query_engine().query(static_query)

     encoding = tiktoken.get_encoding("cl100k_base")

     # Prints for debug
     # print("[RAG DEBUG] dynamic_response chars =", len(str(dynamic_response)))
     # print("[RAG DEBUG] static_response chars =", len(str(static_response)))
     # print("[RAG DEBUG] dynamic_response tokens =", len(encoding.encode(str(dynamic_response))))
     # print("[RAG DEBUG] static_response tokens =", len(encoding.encode(str(static_response))))
     # print("[RAG DEBUG] dynamic_response preview:")
     # print(str(dynamic_response))
     # print("[RAG DEBUG] static_response preview:")
     # print(str(static_response))

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