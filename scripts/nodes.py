import os
import re
import time
import csv
import datetime
import subprocess
from llama_index.core import Settings, StorageContext, load_index_from_storage, VectorStoreIndex, SimpleDirectoryReader
from state import AgentState
from utils import get_index
from config import VIVADO_BIN_PATH 

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

# NODE 2 --> Generator
def generator_node(state: AgentState):
    plan = state.get("action_plan", "")
    # getting errors if exists
    error = state.get("compilation_error", "")
    iterations = state.get("iterations", 0)
    llm = Settings.llm


    #system_prompt = """You are an Expert SystemVerilog and UVM Developer. 
    #                STRICT RULES:
    #                1. START with: `include "uvm_macros.svh"` and `import uvm_pkg::*;`
    #               2. CLASS: The coverage container MUST extend `uvm_subscriber #(transaction)`. Do NOT use `fifo_seq_item`.
     #               3. COVERAGE: You MUST implement the `covergroup` and all `coverpoints` defined in the Action Plan. Do not leave them as comments.
      #              4. EMBEDDED COVERGROUPS: In SystemVerilog, embedded covergroups cannot be used as variable types. Do NOT declare variables like `fifo_write cg_write;`. You must ONLY instantiate them by calling `covergroup_name = new();` directly inside the class `new()` function.
       #             5. SAMPLING: Call the `.sample()` method for each covergroup inside the `write(transaction t)` method.
        #            6. Output ONLY code inside ```systemverilog ... ```.
         #           7. THE TRANSACTION CLASS ALREADY EXISTS IN THE ENVIRONMENT. YOU MUST NOT DEFINE IT. 
          #          8. YOUR CODE MUST START DIRECTLY WITH `class coverage_container extends uvm_subscriber #(transaction);`. Any redefinition of `transaction` will cause a fatal system failure.
           #         9. UVM FACTORY: You MUST register the class with the UVM factory by adding `uvm_component_utils(coverage_container) immediately after the class declaration.
            #        """
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


# node for verification
def checker_node(state: AgentState):
    print("\nNode 3 Checker: Validate generated code...")
    code = state.get("generated_code", "")

    # extract the code
    generated_text = re.search(r"```systemverilog\n(.*?)```", code, re.DOTALL)
    if generated_text:
        clean_code = generated_text.group(1)
    else:
        clean_code = code
    
    # write the file on disk (create or open file first)
    file_path = r"C:\Users\Simina\An4\Licenta\LICENTA\FIFO_SIMULATION\TB-FIFO\coverage_container.sv"
    with open(file_path, "w") as f:
        f.write(clean_code)

    print(f"\nSystemVerilog code saved in {file_path}\n")

    # batch file path
    bat_file_path = r"C:\Users\Simina\An4\Licenta\LICENTA\FIFO_SIMULATION\SIM-FIFO\MakeSVfile.bat"

    #working directory
    working_dir = os.path.dirname(bat_file_path)

    
    # verify write function using verilog simulator
    print(f"\nCompiling {file_path} using VIVADO...")

    # execution time VIVADO
    start_time = time.time()
    try:
        result = subprocess.run(
            [bat_file_path], 
            cwd=working_dir,      
            capture_output=True, 
            text=True, 
            shell=True,
            timeout = 60      
        )

        raw_errors = result.stdout + "\n" + result.stderr
        returncode = result.returncode

    except subprocess.TimeoutExpired:
        print("VIVADO timeout")
        raw_errors = "ERROR: Timeout - Vivado simulation or compilation hanged."
        returncode = 1

    end_time = time.time()
    execution_time = time.time()
    exec_time = round(end_time - start_time, 2)

    raport_path = "raport_experimental.txt"
    csv_path = "experimental_metrics_FIFO2.csv"
    it = state.get("iterations", 0)

    # date, time for saving metrics
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # open or create CSV file
    if not os.path.exists(csv_path):
        with open(csv_path, mode = 'w', newline='' ) as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp","Iteration", "Status", "Time_Execution_sec", "Coverage", "Error_type"])    # test if compilation failed
    
    coverage_val = "N/A"
    status = "FAILED"
    error_summary = "N/A"

    if returncode != 0 or "ERROR:" in raw_errors:
        status = "FAILED"        
        if "not recognized" in raw_errors:
            errors = f"SYSTEM ERROR: Vivado path is incorrect or access denied. Path used: {VIVADO_BIN_PATH}"
            error_summary = "System/Path Error"
        else:
            errors = "\n".join([l for l in raw_errors.split('\n') if "ERROR:" in l or "coverage_container.sv" in l][:15])
            error_summary = "Syntax/Compilation Error"

        print(f"Compilation FAILED (Time: {exec_time}s): \n {errors}")   

        with open(raport_path, "a") as f:
            f.write(f"[{timestamp}]  Iteration: {it} | Erors: {errors}\n")
            f.write(f"Time_exec: {exec_time}\n")
            f.write("\n")

        with open(csv_path, mode = 'a', newline='') as file:
            csv.writer(file).writerow([timestamp,it, status, exec_time, coverage_val, error_summary])

        return {"compilation_error": errors}
    else:
        status = "SUCCESS"
        error_summary = "None"

        #coverage status
        cov_match = re.search(r'MY_COVERAGE.*?(\d+\.\d+|\d+)', raw_errors)

        if cov_match:
            coverage_float = float(cov_match.group(1))
            coverage_val = f"{coverage_float}%"

            if coverage_float < 75.0:
                status = "LOW COVERAGE"
                error_summary= "Coverage beloe target!"
                print(f"Compilation SUCCESSFUL, but COVERAGE IS TOO LOW: {coverage_float}. Target is 75%.")

                errors = f"Compilation was Successful, but functional coverage is only: {coverage_float}. The target is 75.0%. Please check the Action Plan and add more meaningful coverpoints, bins, or cross coverage to increase the value. DO NOT change the template strcuture."

                with open(raport_path, "a") as file:
                    file.write(f"[{timestamp}]  Iteration: {it} | Coverage: {coverage_val}\n")
                    file.write(f"Feedback send to agent: {errors}\n")
                    file.write("-" * 50 + "\n")       

                with open(csv_path, mode='a', newline='') as file:
                    csv.writer(file).writerow([timestamp, it, status, exec_time, coverage_val, error_summary]) 
                
                return {"compilation_error": errors}
            else:
                status = "SUCCESS"
                error_summary = "None"
                print(f"Compilation SUCCESSFUL, Target reached | Time exec: {exec_time} sec | COVERAGE : {coverage_val}\n")
                with open(raport_path, "a") as file:
                    file.write(f"[{timestamp}]  Iteration: {it} | Coverage: {coverage_val}\n")
                    file.write("-" * 50 + "\n")

                with open(csv_path, mode='a', newline='') as file:
                    csv.writer(file).writerow([timestamp, it, status, exec_time, coverage_val, error_summary])
                
                return {"compilation_error": ""}    

        else:
            coverage_val = "Extraction coverage value FAILED"
            status = "FAILED"
            error_summary = "Coverage Parse Error"
            errors = "Compilation successful, but could not extract MY_COVERAGE from logs. Make sure check_phase prints it."
            print(f"Error: {errors}")

            with open(raport_path, "a") as file:
                file.write(f"[{timestamp}]  Iteration: {it} | Status: {status} | Error: {errors}\n")
                file.write("-" * 50 + "\n")
                
            with open(csv_path, mode='a', newline='') as file:
                csv.writer(file).writerow([timestamp, it, status, exec_time, coverage_val, error_summary])

            return {"compilation_error": errors}