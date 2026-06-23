
`ifndef FIFO_OUT_AGENT_UVM
`define FIFO_OUT_AGENT_UVM

`include "include.sv"

// -------------------------------------------------------------
// Output agent
// Pasiv: contine doar output_monitor
// Se instantiaza de doua ori: Q0 si Q1
// -------------------------------------------------------------
class output_agent extends uvm_agent;
   `uvm_component_utils(output_agent)

   output_monitor output_monitor_h;

   uvm_analysis_port#(out_transaction) out_ap;

   function new(string name = "output_agent", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      out_ap = new("out_ap", this);

      output_monitor_h =
         output_monitor::type_id::create("output_monitor_h", this);
   endfunction


   function void connect_phase(uvm_phase phase);
      super.connect_phase(phase);

      output_monitor_h.out_ap.connect(out_ap);
   endfunction


   task run_phase(uvm_phase phase);
      `uvm_info("OUTPUT_AGENT_RUN",
                "Output agent is running.",
                UVM_NONE)
   endtask

endclass

`endif