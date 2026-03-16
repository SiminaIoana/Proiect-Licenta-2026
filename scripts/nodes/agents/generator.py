from llama_index.core import Settings
from state import AgentState

# NODE 2 --> Generator
def generator_node(state: AgentState):
    plan = state.get("action_plan", "")
    # getting errors if exists
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)
    llm = Settings.llm

    system_prompt = """You are an Expert SystemVerilog and UVM Developer.
                YOUR ONLY TASK is to insert coverpoints into an EXACT existing template.
                Do NOT invent a new class structure. Do NOT modify the functions provided in the template."""

    template = """
                `ifndef FIFO_COVERAGE_CONTAINER_UVM
                `define FIFO_COVERAGE_CONTAINER_UVM

                `include "include.sv"
                class coverage_container extends uvm_subscriber#(transaction);
                `uvm_component_utils(coverage_container)

                uvm_tlm_analysis_fifo#(transaction) mon2subs;
                transaction trans;
   
                function new(string name="coverage_container",uvm_component parent=null);
                    super.new(name,parent);
                    fifo_cg=new();
                endfunction

                function void build_phase(uvm_phase phase);
                    super.build_phase(phase);
                    mon2subs=new("mon2subs",this);
                endfunction

                covergroup fifo_cg();
                // >>> GENERATE YOUR COVERPOINTS AND CROSSES HERE BASED ON THE ACTION PLAN <<<
                // IMPORTANT: Always use `trans.variable_name` (e.g., `coverpoint trans.we;`)
                endgroup

                function void write(transaction t);
                    mon2subs.write(t); 
                endfunction

                task run_phase(uvm_phase phase);
                forever begin
                    mon2subs.get(trans);
                    fifo_cg.sample();
                    end
                endtask

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
        print(f"\nNode 2 GENERATOR: Fixing problems and rewrite the code: Iteration number: {iterations+1}")
        #user_prompt =f"Action plan: {plan} + \n\n + The previous code had this error: {error}. Please fix it and output the full code again." 
        user_prompt = f"""
                    The previous code failed with these errors:
                    {error} 
                    Fix the coverpoints and output the COMPLETE code using EXACTLY this template:
                    {template}
                    """
    else:
        print("\nNode 2 GENERATOR: Reading the action plan and writing SV code...")
        #user_prompt = f"""
         #           Write the `fifo_coverage_container.sv` class based strictly on this Action Plan:
          #          {plan}
           #         """
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

    return {"generated_code": response.text, "iterations": iterations+1}

