`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

`include "include.sv"

class coverage_container extends uvm_subscriber#(transaction);
    `uvm_component_utils(coverage_container)

    transaction trans;

    covergroup fifo_cg();
        // Coverpoint for full and empty signal combinations
        cp_full_empty: coverpoint {trans.full, trans.empty} {
            bins full_and_not_empty = {2'b10};
            bins not_full_and_empty = {2'b01};
            bins not_full_and_not_empty = {2'b00};
            bins full_and_empty = {2'b11};
        }

        // Cross between full and empty signals
        cp_full_empty_cross: cross trans.full, trans.empty;

        // Coverpoint for write and read enable interactions
        cp_we_re: coverpoint {trans.we, trans.re} {
            bins write_only = {2'b10};
            bins read_only = {2'b01};
            bins write_and_read = {2'b11};
            bins no_write_no_read = {2'b00};
        }

        // Cross between we and re
        cp_we_re_cross: cross trans.we, trans.re;

        // Coverpoint for data_in values
        cp_data_in: coverpoint trans.data_in {
            bins low = {[0:100]};
            bins mid = {[101:500]};
            bins high = {[501:32'hFFFF_FFFE]};
            bins zero = {0};
            bins max_val = {32'hFFFF_FFFF};
        }

        // Coverpoint for data_out values
        cp_data_out: coverpoint trans.data_out {
            bins low = {[0:100]};
            bins mid = {[101:500]};
            bins high = {[501:32'hFFFF_FFFE]};
            bins zero = {0};
            bins max_val = {32'hFFFF_FFFF};
        }

        // Cross between data_in and data_out
        cp_data_in_out_cross: cross trans.data_in, trans.data_out;

        // Coverpoint for reset signal
        cp_reset: coverpoint trans.reset {
            bins reset_active = {0};
            bins reset_inactive = {1};
        }

        // Cross between reset and full/empty signals
        cp_reset_full_empty_cross: cross trans.reset, trans.full, trans.empty;

        // Coverpoint for clk signal
        cp_clk: coverpoint trans.clk {
            bins rising_edge = {1};
            bins falling_edge = {0};
        }

        // Cross between clk and we/re
        cp_clk_we_re_cross: cross trans.clk, trans.we, trans.re;
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
