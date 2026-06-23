`ifndef FIFO_OUTPUT_MONITOR_UVM
`define FIFO_OUTPUT_MONITOR_UVM

`include "include.sv"

`define out_vintf vif.monitor_cb

class output_monitor extends uvm_monitor;
   `uvm_component_utils(output_monitor)

   virtual fifo_out_intf vif;

   uvm_analysis_port#(out_transaction) out_ap;

   int queue_id;
   int unsigned clk_cycle_count = 0;

   int unsigned cnt_valid_read = 0;
   int unsigned cnt_overflow = 0;
   int unsigned cnt_underflow = 0;
   int unsigned cnt_full_cycles = 0;
   int unsigned cnt_empty_cycles = 0;
   int unsigned cnt_almost_full_cycles = 0;
   int unsigned cnt_almost_empty_cycles = 0;

   function new(string name = "output_monitor", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      out_ap = new("out_ap", this);

      if (!uvm_config_db#(virtual fifo_out_intf)::get(this, "", "out_vintf", vif)) begin
         `uvm_fatal("OUTPUT_MONITOR_CONNECTION_NOT_ESTABLISHED", "")
      end

      if (!uvm_config_db#(int)::get(this, "", "queue_id", queue_id)) begin
         `uvm_fatal("OUTPUT_MONITOR_QUEUE_ID_NOT_SET", "")
      end

      `uvm_info("OUTPUT_MONITOR_CONNECTION_ESTABLISHED",
         $sformatf("Output monitor connected for queue %0d", queue_id),
         UVM_NONE)

      `uvm_info("OUT_MON_CSV_HEADER",
         "TIME,CLK_CYCLE,QUEUE_ID,DATA_OUT,FULL,EMPTY,ALMOST_FULL,ALMOST_EMPTY,OVERFLOW,UNDERFLOW,VALID,STATE",
         UVM_NONE)
   endfunction


   function void update_stats(out_transaction t);
      if (t.valid)
         cnt_valid_read++;

      if (t.overflow)
         cnt_overflow++;

      if (t.underflow)
         cnt_underflow++;

      if (t.full)
         cnt_full_cycles++;

      if (t.empty)
         cnt_empty_cycles++;

      if (t.almost_full)
         cnt_almost_full_cycles++;

      if (t.almost_empty)
         cnt_almost_empty_cycles++;
   endfunction


   function void log_output_event(out_transaction t);
      `uvm_info("OUT_MON_CSV_DATA", t.to_csv_row($time), UVM_NONE)

      if (t.valid == 1) begin
         `uvm_info("OUT_MON_EVENT",
            $sformatf("[Q%0d] VALID READ at t=%0t | data_out=0x%08h",
            t.queue_id, $time, t.data_out),
            UVM_NONE)
      end

      if (t.overflow == 1) begin
         `uvm_info("OUT_MON_SPECIAL_EVENT",
            $sformatf("[Q%0d] OVERFLOW detected at t=%0t | full=%0b | write was blocked",
            t.queue_id, $time, t.full),
            UVM_NONE)
      end

      if (t.underflow == 1) begin
         `uvm_info("OUT_MON_SPECIAL_EVENT",
            $sformatf("[Q%0d] UNDERFLOW detected at t=%0t | empty=%0b | read was blocked",
            t.queue_id, $time, t.empty),
            UVM_NONE)
      end

      if (t.almost_full == 1) begin
         `uvm_info("OUT_MON_STATUS",
            $sformatf("[Q%0d] ALMOST_FULL active at t=%0t",
            t.queue_id, $time),
            UVM_MEDIUM)
      end

      if (t.almost_empty == 1) begin
         `uvm_info("OUT_MON_STATUS",
            $sformatf("[Q%0d] ALMOST_EMPTY active at t=%0t",
            t.queue_id, $time),
            UVM_MEDIUM)
      end
   endfunction


   task run_phase(uvm_phase phase);
      out_transaction trans;

      forever begin
         @(vif.monitor_cb);
         clk_cycle_count++;

         if (vif.reset == 1) begin
            trans = out_transaction::type_id::create("trans", this);

            trans.queue_id = queue_id[0];
            trans.cycle_count = clk_cycle_count;

            trans.data_out = `out_vintf.data_out;

            trans.full = `out_vintf.full;
            trans.empty = `out_vintf.empty;
            trans.almost_full = `out_vintf.almost_full;
            trans.almost_empty = `out_vintf.almost_empty;

            trans.overflow = `out_vintf.overflow;
            trans.underflow = `out_vintf.underflow;
            trans.valid = `out_vintf.valid;

            trans.update_out_state();

            update_stats(trans);
            log_output_event(trans);

            out_ap.write(trans);
         end
      end
   endtask


   function void report_phase(uvm_phase phase);
      `uvm_info("OUT_MON_SUMMARY", "================================================", UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY",
         $sformatf("        OUTPUT MONITOR SUMMARY FOR QUEUE %0d       ", queue_id),
         UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", "================================================", UVM_NONE)

      `uvm_info("OUT_MON_SUMMARY", $sformatf("Clock cycles observed       : %0d", clk_cycle_count), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Valid reads                 : %0d", cnt_valid_read), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Overflow events             : %0d", cnt_overflow), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Underflow events            : %0d", cnt_underflow), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Full active cycles          : %0d", cnt_full_cycles), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Empty active cycles         : %0d", cnt_empty_cycles), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Almost full active cycles   : %0d", cnt_almost_full_cycles), UVM_NONE)
      `uvm_info("OUT_MON_SUMMARY", $sformatf("Almost empty active cycles  : %0d", cnt_almost_empty_cycles), UVM_NONE)

      `uvm_info("OUT_MON_SUMMARY", "================================================", UVM_NONE)

      if (cnt_valid_read == 0)
         `uvm_warning("OUT_COVERAGE_RISK",
            $sformatf("Queue %0d did not produce any valid read.", queue_id))

      if (cnt_overflow == 0)
         `uvm_warning("OUT_COVERAGE_RISK",
            $sformatf("Queue %0d did not produce overflow.", queue_id))

      if (cnt_underflow == 0)
         `uvm_warning("OUT_COVERAGE_RISK",
            $sformatf("Queue %0d did not produce underflow.", queue_id))

      if (cnt_almost_full_cycles == 0)
         `uvm_warning("OUT_COVERAGE_RISK",
            $sformatf("Queue %0d never reached almost_full.", queue_id))

      if (cnt_almost_empty_cycles == 0)
         `uvm_warning("OUT_COVERAGE_RISK",
            $sformatf("Queue %0d never reached almost_empty.", queue_id))
   endfunction

endclass

`endif