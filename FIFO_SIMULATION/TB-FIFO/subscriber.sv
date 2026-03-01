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
      we_cp:coverpoint trans.we;
      re_cp:coverpoint trans.re;
      full_cp:coverpoint trans.full;
      empty_cp:coverpoint trans.empty;
      data__in_cp:coverpoint trans.data_in {
            bins b1[10] = {[0:30]};
      }
      cp_data: coverpoint trans.data_in {
            bins corners = {32'h0, 32'hFFFF_FFFF, 32'hAAAA_AAAA, 32'h5555_5555};
      }
      ctrl_status_cross: cross we_cp, re_cp, full_cp, empty_cp {
            bins write_while_full = binsof(we_cp) intersect {1} && binsof(full_cp) intersect {1};
            bins read_while_empty = binsof(re_cp) intersect {1} && binsof(empty_cp) intersect {1};
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
