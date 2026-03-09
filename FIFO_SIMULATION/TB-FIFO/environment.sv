`ifndef FIFO_ENVIRONMENT_UVM
`define FIFO_ENVIRONMENT_UVM

`include "include.sv"
class environment extends uvm_env;
   `uvm_component_utils(environment)

   scoreboard scoreboard_h;
   subscriber subscriber_h;
   agent agent_h;
   //handler for coverage container
   coverage_container coverage_h;

   function new(string name="environment",uvm_component parent=null);
      super.new(name,parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      scoreboard_h=scoreboard::type_id::create("scoreboard_h",this);
      subscriber_h=subscriber::type_id::create("subscriber_h",this);
      agent_h=agent::type_id::create("agent_h",this);
      coverage_h=coverage_container::type_id::create("coverage_h", this);
      uvm_config_db#(coverage_container)::set(this, "*", "cov_handler", coverage_h);
   endfunction

   function void connect_phase(uvm_phase phase);
      super.connect_phase(phase);
      agent_h.mon2scor.connect(scoreboard_h.mon2scor.analysis_export);
      agent_h.mon2scor.connect(subscriber_h.mon2subs.analysis_export);
      agent_h.mon2scor.connect(coverage_h.analysis_export);
   endfunction
   
   task run_phase(uvm_phase phase);
      `uvm_info("ENVIRONMENT-RUN PHASE","",UVM_NONE);
   endtask

endclass

`endif