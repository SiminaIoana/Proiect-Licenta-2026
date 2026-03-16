from llama_index.core import Settings, StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader
from state import AgentState
from utils import get_index

# NODE 0 --> RAG-node
def rag_node(state: AgentState):
     print("\nNode 0 RAG NODE: Searching documentation...")
     user_query = state.get("dut_specs", "General specification")
    
     index_dynamic = get_index("../DOCS/rag_data_dynamic/", "../DOCS/storage_dynamic/", "Dynamic index")
     dynamic_query_engine = index_dynamic.as_query_engine()

     index_static = get_index("../DOCS/rag_data_static/", "../DOCS/storage_static/", "Static index")
     static_query_engine = index_static.as_query_engine()


     # test 
     dynamic_query = dynamic_query = """List all ports, signals, bit-widths, and functional behavior for the FIFO design described in the technical specification docs. 
                                    Additionally, analyze the provided SystemVerilog code, specifically the 'fifo_intf' interface and the 'transaction' class. Extract the exact names of the variables declared in the 'transaction' class (such as 'we', 're', 'data_in', 'full', 'empty') so they can be accurately used to create coverpoints in a UVM subscriber.
                                    """
     dynamic_response = dynamic_query_engine.query(dynamic_query)

     static_query = "Extract the rules and examples for implementing a class that extends uvm_subscriber. How should a covergroup and its coverpoints be defined and sampled inside this subscriber?"
     static_response = static_query_engine.query(static_query)
     return {
         "uvm_rules": static_response.response, 
         "dut_specs": dynamic_response.response
     }
