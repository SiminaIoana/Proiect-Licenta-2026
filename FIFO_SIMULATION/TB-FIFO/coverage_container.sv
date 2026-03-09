`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

class coverage_container extends uvm_subscriber#(transaction);
   `uvm_component_utils(coverage_container)

   transaction trans;

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

   function new(string name="coverage_container", uvm_component parent=null);
      super.new(name, parent);
      fifo_cg = new(); 
   endfunction

   //automated method for sampling
   virtual function void write(transaction t);
      this.trans = t; 
      fifo_cg.sample();
   endfunction

    //manual sample where is necessary
   virtual function void sample_manual(transaction t);
      this.trans = t;
      fifo_cg.sample();
   endfunction

   function void check_phase(uvm_phase phase);
      $display("----------------------------------------------------------------");
      `uvm_info("CONTAINER_COVERAGE", $sformatf("%0f%%", fifo_cg.get_inst_coverage()), UVM_NONE);
      $display("----------------------------------------------------------------");
   endfunction
endclass
`endif