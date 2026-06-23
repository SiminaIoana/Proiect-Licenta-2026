`ifndef FIFO_INPUT_MONITOR_UVM
`define FIFO_INPUT_MONITOR_UVM

`include "include.sv"

`define cmd_mon_vintf vif.monitor_cb

class input_monitor extends uvm_monitor;
   `uvm_component_utils(input_monitor)

   virtual fifo_cmd_intf vif;

   uvm_analysis_port#(transaction) cmd_ap;

   int unsigned clk_cycle_count = 0;
   int unsigned cmd_packet_count = 0;

   int unsigned cnt_write_q0 = 0;
   int unsigned cnt_write_q1 = 0;
   int unsigned cnt_read_q0  = 0;
   int unsigned cnt_read_q1  = 0;
   int unsigned cnt_flush_q0 = 0;
   int unsigned cnt_flush_q1 = 0;
   int unsigned cnt_simultaneous_rw = 0;
   int unsigned cnt_no_op = 0;

   function new(string name = "input_monitor", uvm_component parent = null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      cmd_ap = new("cmd_ap", this);

      if (!uvm_config_db#(virtual fifo_cmd_intf)::get(this, "", "cmd_vintf", vif)) begin
         `uvm_fatal("INPUT_MONITOR_CONNECTION_NOT_ESTABLISHED", "")
      end
      else begin
         `uvm_info("INPUT_MONITOR_CONNECTION_ESTABLISHED", "", UVM_NONE)
      end

      `uvm_info("CMD_MON_CSV_HEADER",
         "PKT_ID,TIME,CLK_CYCLE,Q_ADDR,WR_EN,RD_EN,FLUSH,DATA_IN,CMD_STATE",
         UVM_NONE)
   endfunction


   function void update_stats(transaction t);
      if (t.flush == 1) begin
         if (t.q_addr == 0)
            cnt_flush_q0++;
         else
            cnt_flush_q1++;
      end
      else if (t.wr_en == 1 && t.rd_en == 1) begin
         cnt_simultaneous_rw++;
      end
      else if (t.wr_en == 1) begin
         if (t.q_addr == 0)
            cnt_write_q0++;
         else
            cnt_write_q1++;
      end
      else if (t.rd_en == 1) begin
         if (t.q_addr == 0)
            cnt_read_q0++;
         else
            cnt_read_q1++;
      end
      else begin
         cnt_no_op++;
      end
   endfunction


   function void log_command(transaction t);
      `uvm_info("CMD_MON_CSV_DATA", t.to_csv_row($time), UVM_NONE)

      case (t.fifo_state_tag)

         NORMAL_WRITE: begin
            `uvm_info("CMD_MON_EVENT",
               $sformatf("[PKT#%0d] WRITE command | q_addr=%0d | data_in=0x%08h",
               t.packet_id, t.q_addr, t.data_in),
               UVM_NONE)
         end

         NORMAL_READ: begin
            `uvm_info("CMD_MON_EVENT",
               $sformatf("[PKT#%0d] READ command | q_addr=%0d",
               t.packet_id, t.q_addr),
               UVM_NONE)
         end

         SIMULTANEOUS_RW: begin
            `uvm_info("CMD_MON_SPECIAL_EVENT",
               $sformatf("[PKT#%0d] SIMULTANEOUS_RW command | q_addr=%0d | data_in=0x%08h",
               t.packet_id, t.q_addr, t.data_in),
               UVM_NONE)
         end

         FLUSH_OP: begin
            `uvm_info("CMD_MON_SPECIAL_EVENT",
               $sformatf("[PKT#%0d] FLUSH command | q_addr=%0d",
               t.packet_id, t.q_addr),
               UVM_NONE)
         end

         NO_OPERATION: begin
            `uvm_info("CMD_MON_EVENT",
               $sformatf("[PKT#%0d] NO_OPERATION", t.packet_id),
               UVM_HIGH)
         end

         default: ;
      endcase
   endfunction


   task run_phase(uvm_phase phase);
      transaction trans;

      forever begin
         @(vif.monitor_cb);
         clk_cycle_count++;

         if (vif.reset == 1) begin
            trans = transaction::type_id::create("trans", this);

            trans.packet_id = cmd_packet_count;
            cmd_packet_count++;

            trans.cycle_count = clk_cycle_count;

            trans.wr_en   = `cmd_mon_vintf.wr_en;
            trans.rd_en   = `cmd_mon_vintf.rd_en;
            trans.flush   = `cmd_mon_vintf.flush;
            trans.q_addr  = `cmd_mon_vintf.q_addr;
            trans.data_in = `cmd_mon_vintf.data_in;

            trans.update_cmd_state();

            update_stats(trans);
            log_command(trans);

            cmd_ap.write(trans);
         end
      end
   endtask


   function void report_phase(uvm_phase phase);
      int unsigned total_cmds;

      total_cmds = cnt_write_q0 + cnt_write_q1 +
                   cnt_read_q0  + cnt_read_q1  +
                   cnt_flush_q0 + cnt_flush_q1 +
                   cnt_simultaneous_rw + cnt_no_op;

      `uvm_info("CMD_MON_SUMMARY", "================================================", UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", "          INPUT MONITOR COMMAND SUMMARY          ", UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", "================================================", UVM_NONE)

      `uvm_info("CMD_MON_SUMMARY", $sformatf("Total observed commands : %0d", total_cmds), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("Clock cycles observed   : %0d", clk_cycle_count), UVM_NONE)

      `uvm_info("CMD_MON_SUMMARY", "------------------------------------------------", UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("WRITE Q0          : %0d", cnt_write_q0), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("WRITE Q1          : %0d", cnt_write_q1), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("READ Q0           : %0d", cnt_read_q0), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("READ Q1           : %0d", cnt_read_q1), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("FLUSH Q0          : %0d", cnt_flush_q0), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("FLUSH Q1          : %0d", cnt_flush_q1), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("SIMULTANEOUS_RW   : %0d", cnt_simultaneous_rw), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", $sformatf("NO_OPERATION      : %0d", cnt_no_op), UVM_NONE)
      `uvm_info("CMD_MON_SUMMARY", "================================================", UVM_NONE)

      if (cnt_write_q1 == 0)
         `uvm_warning("CMD_COVERAGE_RISK", "No WRITE command was observed on queue 1.")

      if (cnt_read_q1 == 0)
         `uvm_warning("CMD_COVERAGE_RISK", "No READ command was observed on queue 1.")

      if (cnt_flush_q0 == 0 || cnt_flush_q1 == 0)
         `uvm_warning("CMD_COVERAGE_RISK", "Flush was not observed on both queues.")

      if (cnt_simultaneous_rw == 0)
         `uvm_warning("CMD_COVERAGE_RISK", "SIMULTANEOUS_RW command did not appear in simulation.")
   endfunction

endclass

`endif