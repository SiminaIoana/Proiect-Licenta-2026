from llama_index.core import Settings
from state import AgentState

# NODE 1 --> Analyzer
def analyzer_node(state: AgentState):
    print("\nNode 1 ANALYZER: Reading specification..")
    specs = state.get("dut_specs", "")
    rules = state.get("uvm_rules", "")
    llm = Settings.llm
    prompt = f"""You are an Expert Verification Engineer. 
            Based on the following DUT Specifications (which include the exact variable names from the 'transaction' class), create a detailed Action Plan for a UVM coverage container class (`uvm_subscriber`). 

            STRICT INSTRUCTIONS:
            1. Clearly define the Covergroups, Coverpoints, Bins, and Cross Coverage required.
            2. Use the EXACT variable names extracted from the provided SystemVerilog code (e.g., 'we', 're', 'data_in', 'full', 'empty'). Do NOT use generic names like 'data' or 'addr'.
            3. Follow the provided UVM Rules for correct syntax and structure.
            DUT Specifications & Extracted Code Variables:
            {specs}

            UVM Rules:
            {rules}

            Output the Action Plan clearly formatted."""
    
    response = llm.complete(prompt)

    return {"action_plan": response.text}
