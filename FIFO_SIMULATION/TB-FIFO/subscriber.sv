`ifndef FIFO_SUBSCRIBER_UVM
`define FIFO_SUBSCRIBER_UVM

`include "include.sv"
class subscriber extends uvm_subscriber#(transaction);
   `uvm_component_utils(subscriber)

   uvm_tlm_analysis_fifo#(transaction) mon2subs;

   transaction trans;
   
   function new(string name="environment",uvm_component parent=null);
      super.new(name,parent);
      fifo_cg=new();
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2subs=new("mon2subs",this);
   endfunction

   
   covergroup fifo_cg();
      we_cp: coverpoint trans.we {
        bins active   = {1};
        bins inactive = {0};
    }

    re_cp: coverpoint trans.re {
        bins active   = {1};
        bins inactive = {0};
    }

    full_cp: coverpoint trans.full {
        bins is_full  = {1};
        bins not_full = {0};
    }

    empty_cp: coverpoint trans.empty {
        bins is_empty  = {1};
        bins not_empty = {0};
    }

    cp_data: coverpoint trans.data_in {
        bins ranges[10] = {[0:30]};
        bins corners = {32'h0, 32'hFFFF_FFFF, 32'hAAAA_AAAA, 32'h5555_5555};
    }
      write_protocol_cross: cross we_cp, full_cp {
        // Write is active AND FIFO is not full
        bins write_ok   = binsof(we_cp.active) && binsof(full_cp.not_full);
        bins write_full = binsof(we_cp.active) && binsof(full_cp.is_full); // Corner case: overflow
        
        ignore_bins no_write = binsof(we_cp.inactive);
    }

    read_protocol_cross: cross re_cp, empty_cp {
        bins read_ok    = binsof(re_cp.active) && binsof(empty_cp.not_empty);
        bins read_empty = binsof(re_cp.active) && binsof(empty_cp.is_empty); // Corner case: underflow
        
        ignore_bins no_read = binsof(re_cp.inactive);
    }
    impossible_state_cross: cross full_cp, empty_cp {
        ignore_bins impossible = binsof(full_cp.is_full) && binsof(empty_cp.is_empty);
    }

   endgroup


   function void write(transaction t);
      mon2subs.write(t); 
   endfunction

   task run_phase(uvm_phase phase);
      `uvm_info("SUBSCRIBER-RUN PHASE","",UVM_NONE);
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
