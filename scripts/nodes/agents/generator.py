from llama_index.core import Settings
from state import AgentState
from utils import get_index, extract_code
import os
import tiktoken

# NODE 2 --> Generator
def generator_node(state: AgentState):
    plan = state.get("action_plan", "")
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)
    specs = state.get("dut_specs", "")
    llm = Settings.llm

    # long term memory 
    ltm_content = ""
    if error != "":
        print(f"\nNode 2 GENERATOR: Querying Semantic Memory (LTM) for a fix...")
        try:
            index_exp = get_index("../results/experience_data/", "../DOCS/storage_exp/", "LTM Index")
            
            if index_exp:
                query_engine = index_exp.as_query_engine(similarity_top_k=1)
                # ow the probmlem was solved
                memory_response = query_engine.query(f"Identify the fix for this Vivado error: {error}")
                ltm_content = str(memory_response)
            else:
                ltm_content = ""

        except Exception as e:

            print(f"Node 2: LTM is empty or not yet available. Proceeding with general knowledge.")
            ltm_content = ""

    system_prompt = """You are an Expert SystemVerilog and UVM Developer.
                YOUR ONLY TASK is to insert coverpoints into an EXACT existing template.
                Do NOT invent a new class structure. Do NOT modify the functions provided in the template.
                
                CRITICAL SYSTEMVERILOG SYNTAX RULES:
                1. Always name your coverpoints if defining bins (e.g., `cp_data: coverpoint trans.data_in { bins b1 = {0}; }`).
                2. NEVER declare the same variable as a coverpoint twice.
                3. NEVER use temporal sequences (like `##1` or `=>`) inside a covergroup. Covergroups do not support SVA temporal syntax.
                4. MEMORY LIMITATION: NEVER use an array of bins for a full 32-bit range like `bins my_bins[] = {[0:2**32-1]}`! This crashes the simulator. Instead, group values into a few safe interval bins WITHOUT brackets,
                   for example: `bins low = {[1:100]}; bins mid = {[101:500]}; bins high = {[501:32'hFFFF_FFFE]};` and add corner cases like `bins zero = {0}; bins max_val = {32'hFFFF_FFFF};`."""
    template ="""
`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

`include "include.sv"

class coverage_container extends uvm_subscriber#(transaction);
    `uvm_component_utils(coverage_container)

    transaction trans;

    covergroup fifo_cg();
        // >>> GENERATE YOUR COVERPOINTS AND CROSSES HERE BASED ON THE ACTION PLAN <<<
    endgroup

    function new(string name="coverage_container",uvm_component parent=null);
        super.new(name, parent); 
        fifo_cg = new();         
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
    endfunction

    function void write(transaction t);
        this.trans = t;
        fifo_cg.sample();
    endfunction

    function void check_phase(uvm_phase phase);
        $display("----------------------------------------------------------------");
        `uvm_info("MY_COVERAGE",$sformatf("%0f",fifo_cg.get_coverage()),UVM_NONE);
        $display("----------------------------------------------------------------");
    endfunction

endclass
`endif
"""
    # if errors appeared
    if error != "":
        print(f"\nGENERATOR: Fixing problems and rewrite the code: Iteration number: {iterations+1}")
        memory_section = f"\nRELEVANT PAST EXPERIENCE FOUND IN MEMORY:\n{ltm_content}\nReview this to avoid repeating the same syntax error!\n" if ltm_content else ""        
        user_prompt = f"""
                    The previous code failed with these errors:
                    {error} 
                    {memory_section}
                    REMEMBER the DUT Specifications:
                    {specs}
                    CRITICAL: Use ONLY variables defined in the specs (e.g. trans.we, trans.re, trans.data_in). Do NOT use generic names like trans.addr or trans.cmd!
                    
                    Fix the coverpoints and output the COMPLETE code using EXACTLY this template:
                    {template}
                    """
    else:
        print("\nNode 2 GENERATOR: Reading the action plan and writing SV code...")
        user_prompt = f"""
        Action Plan for Coverpoints:
        {plan}
        
        You MUST output the COMPLETE SystemVerilog code using EXACTLY this template. 
        Only replace the `// >>> GENERATE YOUR COVERPOINTS... <<<` comment with the actual coverpoints.
        Do NOT change any other lines.
        
        TEMPLATE TO FILL:
        {template}
        """
    # combine user prompt with system prompt for Groq
    full_prompt = system_prompt + "\n\n" + user_prompt
    response = llm.complete(full_prompt)

    # number of tokens used using standard encoding
    encoding = tiktoken.get_encoding("cl100k_base")

    # prompt tokens 
    prompt_tokens = len(encoding.encode(full_prompt))

    #responde tokens
    response_tokens = len(encoding.encode(response.text))
    current_tokens = state.get("iteration_tokens", 0)
    total_tokens = prompt_tokens + response_tokens + current_tokens
    return {"generated_code": response.text, "iterations": iterations+1, "iteration_token": total_tokens}