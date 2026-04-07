`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

`include "include.sv"

class coverage_container extends uvm_subscriber#(transaction);
    `uvm_component_utils(coverage_container)
     uvm_tlm_analysis_fifo#(transaction) mon2subs;
     transaction trans;

    covergroup fifo_cg();
      we_cp:coverpoint trans.we;
      re_cp:coverpoint trans.re;
      full_cp:coverpoint trans.full;
      empty_cp:coverpoint trans.empty;
      
      cp_data: coverpoint trans.data_in {
            bins ranges[10] = {[0:30]};
            bins corners = {32'h0, 32'hFFFF_FFFF, 32'hAAAA_AAAA, 32'h5555_5555};
      }
      
      ctrl_status_cross: cross we_cp, re_cp, full_cp, empty_cp {
         bins write_while_full = binsof(we_cp) intersect {1} && binsof(full_cp) intersect {1};
         bins read_while_empty = binsof(re_cp) intersect {1} && binsof(empty_cp) intersect {1};

         ignore_bins impossible_state = binsof(full_cp) intersect {1} && binsof(empty_cp) intersect {1};
      }
   /*
      write_protocol_cross: cross we_cp, full_cp {
        bins write_ok    = binsof(we_cp) intersect {1} && binsof(full_cp) intersect {0};
        bins write_full  = binsof(we_cp) intersect {1} && binsof(full_cp) intersect {1}; // Corner case: overflow
        ignore_bins no_write = binsof(we_cp) intersect {0};
    }

    read_protocol_cross: cross re_cp, empty_cp {
        bins read_ok     = binsof(re_cp) intersect {1} && binsof(empty_cp) intersect {0};
        bins read_empty  = binsof(re_cp) intersect {1} && binsof(empty_cp) intersect {1}; // Corner case: underflow
        ignore_bins no_read = binsof(re_cp) intersect {0};
    }

    rw_simultaneous_cross: cross we_cp, re_cp {
        bins both_active = binsof(we_cp) intersect {1} && binsof(re_cp) intersect {1};
        ignore_bins others = !binsof(we_cp) intersect {1} || !binsof(re_cp) intersect {1};
    }
    */  
   endgroup


    function new(string name="coverage_container",uvm_component parent=null);
        super.new(name, parent); 
        fifo_cg = new();         
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
    endfunction

    function void write(transaction t);
        this.trans = t;
        fifo_cg.sample();
    endfunction

    function void check_phase(uvm_phase phase);
        $display("----------------------------------------------------------------");
        `uvm_info("MY_COVERAGE",$sformatf("%0f",fifo_cg.get_coverage()),UVM_NONE);
        $display("----------------------------------------------------------------");
    endfunction

endclass
`endif
