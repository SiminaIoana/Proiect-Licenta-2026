`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

`include "include.sv"

class coverage_container extends uvm_subscriber#(transaction);
    `uvm_component_utils(coverage_container)

    transaction trans;

    covergroup fifo_cg();
        // Coverpoint for we: to cover all possible values of we (0 and 1)
        cp_we: coverpoint trans.we {
            bins we_0 = {0};
            bins we_1 = {1};
        }

        // Coverpoint for re: to cover all possible values of re (0 and 1)
        cp_re: coverpoint trans.re {
            bins re_0 = {0};
            bins re_1 = {1};
        }

        // Coverpoint for data_in: to cover all possible values of data_in (32-bit values)
        cp_data_in: coverpoint trans.data_in {
            bins zero = {0};
            bins low = {[1:100]};
            bins mid = {[101:500]};
            bins high = {[501:32'hFFFF_FFFE]};
            bins max_val = {32'hFFFF_FFFF};
        }

        // Coverpoint for full: to cover all possible values of full (0 and 1)
        cp_full: coverpoint trans.full {
            bins full_0 = {0};
            bins full_1 = {1};
        }

        // Coverpoint for empty: to cover all possible values of empty (0 and 1)
        cp_empty: coverpoint trans.empty {
            bins empty_0 = {0};
            bins empty_1 = {1};
        }

        // Cross coverage for we and re
        cp_we_re: cross cp_we, cp_re;

        // Cross coverage for we and full
        cp_we_full: cross cp_we, cp_full;

        // Cross coverage for re and empty
        cp_re_empty: cross cp_re, cp_empty;
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
