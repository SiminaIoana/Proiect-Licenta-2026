`ifndef FIFO_ENVIRONMENT_UVM
`define FIFO_ENVIRONMENT_UVM

`include "include.sv"

class environment extends uvm_env;
   `uvm_component_utils(environment)

   scoreboard scoreboard_h;

   cmd_subscriber cmd_subscriber_h;
   out_subscriber out_subscriber_h;

   input_agent agent_h;

   output_agent output_agent_q0_h;
   output_agent output_agent_q1_h;


   function new(string name = "environment", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      scoreboard_h = scoreboard::type_id::create("scoreboard_h", this);

      cmd_subscriber_h =
         cmd_subscriber::type_id::create("cmd_subscriber_h", this);

      out_subscriber_h =
         out_subscriber::type_id::create("out_subscriber_h", this);

      agent_h = input_agent::type_id::create("agent_h", this);

      uvm_config_db#(int)::set(
         this,
         "output_agent_q0_h.output_monitor_h",
         "queue_id",
         0
      );

      uvm_config_db#(int)::set(
         this,
         "output_agent_q1_h.output_monitor_h",
         "queue_id",
         1
      );

      output_agent_q0_h =
         output_agent::type_id::create("output_agent_q0_h", this);

      output_agent_q1_h =
         output_agent::type_id::create("output_agent_q1_h", this);
   endfunction


   function void connect_phase(uvm_phase phase);
      super.connect_phase(phase);

      // Comenzile de intrare merg catre scoreboard si cmd_subscriber.
      agent_h.cmd_ap.connect(scoreboard_h.cmd_fifo.analysis_export);
      agent_h.cmd_ap.connect(cmd_subscriber_h.analysis_export);

      // Iesirea Q0 merge catre scoreboard si catre subscriber-ul comun de output.
      output_agent_q0_h.out_ap.connect(scoreboard_h.out_fifo_q0.analysis_export);
      output_agent_q0_h.out_ap.connect(out_subscriber_h.analysis_export);

      // Iesirea Q1 merge catre scoreboard si catre acelasi subscriber comun de output.
      output_agent_q1_h.out_ap.connect(scoreboard_h.out_fifo_q1.analysis_export);
      output_agent_q1_h.out_ap.connect(out_subscriber_h.analysis_export);
   endfunction


   task run_phase(uvm_phase phase);
      `uvm_info("ENVIRONMENT_RUN_PHASE",
                "Dual FIFO router environment is running.",
                UVM_NONE)
   endtask

endclass

`endif