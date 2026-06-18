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

     dynamic_response = ""
     static_response = ""
     rag_status = "SUCCESS"
     rag_notes = []

     try:
          dynamic_path = PROJECT_CONFIG.get("dynamic_docs_path", "")
          static_path = PROJECT_CONFIG.get("static_docs_path", "")
          query_context = PROJECT_CONFIG.get("rag_search_query", "")

          dynamic_query = DYNAMIC_RAG_QUERY.format(query_context=query_context)
          static_query = STATIC_RAG_QUERY

          index_dynamic = get_index(
               dynamic_path,
               "./DOCS/storage_dynamic/",
               "Dynamic index"
          )

          index_static = get_index(
               static_path,
               "./DOCS/storage_static/",
               "Static index"
          )

          if index_dynamic is not None:
               try:
                    dynamic_response = index_dynamic.as_query_engine().query(dynamic_query)
               except Exception as e:
                    rag_status = "WARNING"
                    rag_notes.append(f"Dynamic RAG query failed: {e}")
                    print(f"[RAG WARNING]: Dynamic RAG query failed: {e}")
          else:
               rag_status = "WARNING"
               rag_notes.append("Dynamic index was not available.")
               print("[RAG WARNING]: Dynamic index was not available.")

          if index_static is not None:
               try:
                    static_response = index_static.as_query_engine().query(static_query)
               except Exception as e:
                    rag_status = "WARNING"
                    rag_notes.append(f"Static RAG query failed: {e}")
                    print(f"[RAG WARNING]: Static RAG query failed: {e}")
          else:
               rag_status = "WARNING"
               rag_notes.append("Static index was not available.")
               print("[RAG WARNING]: Static index was not available.")

     except Exception as e:
          rag_status = "FAILED"
          rag_notes.append(f"RAG Builder failed: {e}")
          print(f"[RAG ERROR]: RAG Builder failed: {e}")

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
          status=rag_status,
          notes="; ".join(rag_notes) if rag_notes else "static_docs + dynamic_docs"
     )

     return {
          "uvm_rules": str(static_response) if static_response else "",
          "dut_specs": str(dynamic_response) if dynamic_response else "",
          "iteration_tokens": state.get("iteration_tokens", 0) + rag_tokens,
          "rag_status": rag_status,
          "rag_notes": rag_notes,
     }