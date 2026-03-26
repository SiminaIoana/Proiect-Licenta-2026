from llama_index.core import Settings
from state import AgentState
import tiktoken
# NODE 1 --> Analyzer
def analyzer_node(state: AgentState):
    print("\nNode 1 ANALYZER: Reading specification..")
    specs = state.get("dut_specs", "")
    rules = state.get("uvm_rules", "")
    error = state.get("compilation_error","")
    holes = state.get("coverage_holes", "")
    llm = Settings.llm

    if error:
        return {"action_plan": "DEBUG_MODE: Fix the compilation error reported by Vivado before adding new coverage features."}
    
    if holes and holes.strip() != "":
        print("\n Node 1 ANALYZER: Anlyzing coverage holes...")
        prompt=f"""You are an Expert UVM Verification Engineer. 
            We have a UVM coverage container class for a FIFO, but the functional coverage is below the target.
            
            Here are the exact coverage holes extracted from the Vivado simulator:
            {holes}
            
            Based on the DUT Specifications:
            {specs}
            
            Update your previous Action Plan. Provide STRICT INSTRUCTIONS for the Generation Agent on how to modify the covergroups, coverpoints, or crosses to hit these specific missing bins. 
            Tell the Generator exactly what logic or bins need to be added to cover these scenarios (e.g., combinations of full/empty, read/write).
            Do NOT write the SystemVerilog code yourself. Output ONLY the updated Action Plan clearly formatted.
            """
    else:
        prompt = f"""You are an Expert UVM Verification Architect. 
            Based on the following DUT Specifications, create a RIGOROUS and EXHAUSTIVE Action Plan for a UVM coverage container class (`uvm_subscriber`). 

            Your goal is to ensure the functional coverage definition is extremely detailed and catches corner cases.

            STRICT INSTRUCTIONS FOR THE PLAN:
            1. Variables: Use the EXACT variable names extracted from the provided SystemVerilog code. Do NOT use generic names.
            2. Data Coverpoints: For the data input, you MUST explicitly demand specific bins for corner cases. Example: all zeros, all ones, alternating bits (32'hAAAA_AAAA, 32'h5555_5555), and ranges.
            3. Control Crosses: You MUST explicitly demand complex cross coverage for critical FIFO states to catch protocol violations. 
            4. Structure: Output a detailed, itemized Action Plan that the Generator can easily translate into SV syntax.

            DUT Specifications & Extracted Code Variables:
            {specs}

            UVM Rules:
            {rules}

            Output the Action Plan clearly formatted."""
    
    response = llm.complete(prompt)
    # number of tokens used using standard encoding
    encoding = tiktoken.get_encoding("cl100k_base")

    # prompt tokens 
    prompt_tokens = len(encoding.encode(prompt))

    #responde tokens
    response_tokens = len(encoding.encode(response.text))

    current_tokens = state.get("iteration_tokens", 0)
    total_tokens = prompt_tokens + response_tokens + current_tokens
    return {
        "action_plan": response.text,
        "iteration_token": total_tokens
    }