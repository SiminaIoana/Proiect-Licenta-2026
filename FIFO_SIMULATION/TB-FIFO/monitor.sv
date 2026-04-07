`ifndef FIFO_MONITOR_UVM
`define FIFO_MONITOR_UVM
`include "include.sv"


`define vintf_h vif.monitor_cb
class monitor extends uvm_monitor;
   `uvm_component_utils(monitor)

   virtual fifo_intf.monitor_mp vif;
   transaction trans;

   uvm_analysis_port#(transaction) mon2scor;

   // clock cycle contor used for log events
   int unsigned clk_cycle_count = 0;

   // statistics simulation
   int unsigned cnt_normal_write     = 0;       // normal write packet
   int unsigned cnt_normal_read      = 0;       // normal read packet
   int unsigned cnt_simultaneous_rw  = 0;       // we and re simultan
   int unsigned cnt_write_while_full = 0;       // write while fifo is full  
   int unsigned cnt_read_while_empty = 0;       // read while fifo is empty
   int unsigned cnt_no_op            = 0;       // no operation => no read and no write

   function new(string name="monitor",uvm_component parent=null);
      super.new(name,parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor=new("mon2scor",this);
       if(!uvm_config_db#(virtual fifo_intf)::get(this,"","vintf",vif)) begin
         `uvm_fatal("MONITOR_CONNECTION_NOT_ESTABLISHED","");
      end
      else begin
         `uvm_info("MONITOR_CONNECTION_ESTABLISHED","",UVM_NONE);
      end

      // send info for CSV
      `uvm_info("MON_CSV_HEADER","PKT_ID,CLK_CYCLE,WE,RE,DATA_IN,DATA_OUT,FULL,EMPTY,STATE",UVM_NONE)
   endfunction

   // getting state for transaction
   function fifo_state_e classify_transaction(transaction t);
        if (t.we == 1 && t.re == 1)
            return SIMULTANEOUS_RW;
        else if (t.we == 1 && t.full == 1)
            return WRITE_WHILE_FULL;
        else if (t.re == 1 && t.empty == 1)
            return READ_WHILE_EMPTY;
        else if (t.we == 1 && t.re == 0 && t.full == 0)
            return NORMAL_WRITE;
        else if (t.we == 0 && t.re == 1 && t.empty == 0)
            return NORMAL_READ;
        else
            return NO_OPERATION;
   endfunction

   // intern function for updating statistics
   function void update_stats(fifo_state_e state);
        case (state)
            NORMAL_WRITE:     cnt_normal_write++;
            NORMAL_READ:      cnt_normal_read++;
            SIMULTANEOUS_RW:  cnt_simultaneous_rw++;
            WRITE_WHILE_FULL: cnt_write_while_full++;
            READ_WHILE_EMPTY: cnt_read_while_empty++;
            NO_OPERATION:     cnt_no_op++;
            default: ; 
        endcase
   endfunction

function void log_transaction(transaction t);
   string csv_line;
   csv_line = t.to_csv_row($time);

   // agent parsing the line
   `uvm_info("MON_CSV_DATA", csv_line, UVM_NONE)

   // logs used for monitor every type of packet that is read or write
   case (t.fifo_state_tag)
      WRITE_WHILE_FULL: begin
         `uvm_info("MONITOR_SPECIAL_EVENT",
                    $sformatf("[PKT#%0d] WRITE_WHILE_FULL detected at t=%0t | we=%0b full=%0b | data_in=0x%08h -- write was blocked",
                    t.packet_id, $time, t.we, t.full, t.data_in), UVM_NONE)
      end
      READ_WHILE_EMPTY: begin
         `uvm_info("MON_SPECIAL_EVENT",
                    $sformatf("[PKT#%0d] READ_WHILE_EMPTY detected at t=%0t | re=%0b empty=%0b -- read was blocked ",
                    t.packet_id, $time, t.re, t.empty),UVM_NONE)
      end
      SIMULTANEOUS_RW: begin
         `uvm_info("MON_SPECIAL_EVENT",
                    $sformatf("[PKT#%0d] SIMULTANEOUS_RW detected at t=%0t | we=%0b re=%0b full=%0b empty=%0b | data_in=0x%08h data_out=0x%08h",
                    t.packet_id, $time, t.we, t.re, t.full, t.empty, t.data_in, t.data_out), UVM_NONE)
      end
      default: ; // normal tranzaction
   endcase
endfunction


task run_phase(uvm_phase phase);
   forever begin
      @(vif.monitor_cb);
      clk_cycle_count++;

      if(vif.reset == 1) begin
         trans = transaction::type_id::create("trans", this);
         
         trans.we       = `vintf_h.we;
         trans.re       = `vintf_h.re;
         trans.data_in  = `vintf_h.data_in;
         trans.data_out = `vintf_h.data_out; 
         trans.full     = `vintf_h.full;
         trans.empty    = `vintf_h.empty;

         // classify and set the tag
         trans.fifo_state_tag = classify_transaction(trans);

         // statistics
         update_stats(trans.fifo_state_tag);

         //log information
         log_transaction(trans);

         // send to scoreboard 
         mon2scor.write(trans);

      end
   end
endtask

function void report_phase(uvm_phase phase);
   // used for monitor number of transaction
   int unsigned total_transactions;
   total_transactions = cnt_normal_write + cnt_normal_read + cnt_simultaneous_rw + cnt_write_while_full + cnt_read_while_empty + cnt_no_op;

   `uvm_info("MON_SUMMARY", "================================================", UVM_NONE)
   `uvm_info("MON_SUMMARY", "       SUMMARY STATISTIC MONITOR FIFO           ", UVM_NONE)
   `uvm_info("MON_SUMMARY", "================================================", UVM_NONE)

   `uvm_info("MON_SUMMARY", $sformatf("Total observed transaction : %0d", total_transactions),UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("Clock cycle: %0d", clk_cycle_count), UVM_NONE)

   `uvm_info("MON_SUMMARY", "------------------------------------------------", UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("NORMAL_WRITE      (we=1,re=0,full=0)  : %0d", cnt_normal_write), UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("NORMAL_READ       (we=0,re=1,empty=0) : %0d", cnt_normal_read), UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("SIMULTANEOUS_RW   (we=1,re=1)         : %0d", cnt_simultaneous_rw), UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("WRITE_WHILE_FULL  (we=1,full=1)       : %0d", cnt_write_while_full), UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("READ_WHILE_EMPTY  (re=1,empty=1)      : %0d", cnt_read_while_empty), UVM_NONE)
   `uvm_info("MON_SUMMARY", $sformatf("NO_OPERATION      (we=0,re=0)         : %0d", cnt_no_op), UVM_NONE)
   `uvm_info("MON_SUMMARY", "================================================", UVM_NONE)
 
   if (cnt_write_while_full == 0)
      `uvm_warning("MON_COVERAGE_RISK", "WRITE_WHILE_FULL did not appear in the simualtion! Bins for writing while FIFO is full should be uncovered")
   if (cnt_read_while_empty == 0)
      `uvm_warning("MON_COVERAGE_RISK", "READ_WHILE_EMPTY did not appear in the simualtion! Bins for reading while FIFO is empty should be uncovered")
   if (cnt_simultaneous_rw == 0)
      `uvm_warning("MON_COVERAGE_RISK", "SIMULTANEOUS_RW did not appear in the simualtion! Cross for we and re active should be uncovered")
endfunction
endclass
`endif
