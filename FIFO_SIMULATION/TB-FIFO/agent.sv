`ifndef FIFO_AGENT_UVM
`define FIFO_AGENT_UVM

`include "include.sv"

// -------------------------------------------------------------
// Input agent
// Activ: contine sequencer, driver si input_monitor
// -------------------------------------------------------------
class input_agent extends uvm_agent;
   `uvm_component_utils(input_agent)

   sequencer sequencer_h;
   driver driver_h;
   input_monitor input_monitor_h;

   uvm_analysis_port#(transaction) cmd_ap;

   function new(string name = "input_agent", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      cmd_ap = new("cmd_ap", this);

      sequencer_h = sequencer::type_id::create("sequencer_h", this);
      driver_h = driver::type_id::create("driver_h", this);
      input_monitor_h = input_monitor::type_id::create("input_monitor_h", this);
   endfunction


   function void connect_phase(uvm_phase phase);
      super.connect_phase(phase);

      driver_h.seq_item_port.connect(sequencer_h.seq_item_export);
      input_monitor_h.cmd_ap.connect(cmd_ap);
   endfunction


   task run_phase(uvm_phase phase);
      `uvm_info("INPUT_AGENT_RUN",
                "Input agent is running.",
                UVM_NONE)
   endtask

endclass


`endif