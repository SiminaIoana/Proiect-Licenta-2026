`ifndef FIFO_COVERAGE_CONTAINER_UVM
`define FIFO_COVERAGE_CONTAINER_UVM

`include "include.sv"
class coverage_container extends uvm_subscriber#(transaction);
`uvm_component_utils(coverage_container)

uvm_tlm_analysis_fifo#(transaction) mon2subs;
transaction trans;
   
function new(string name="coverage_container",uvm_component parent=null);
    super.new(name,parent);
    fifo_cg=new();
endfunction

function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    mon2subs=new("mon2subs",this);
endfunction

covergroup fifo_cg();
    we_cp: coverpoint trans.we {
        bins we_high = {1};
        bins we_low = {0};
    }
    re_cp: coverpoint trans.re {
        bins re_high = {1};
        bins re_low = {0};
    }
    data_in_cp: coverpoint trans.data_in {
        bins data_in_zero = {0};
        bins data_in_non_zero = {[1:32'hFFFFFFFF]};
    }
    full_cp: coverpoint trans.full {
        bins full_high = {1};
        bins full_low = {0};
    }
    empty_cp: coverpoint trans.empty {
        bins empty_high = {1};
        bins empty_low = {0};
    }
    we_re_cross: cross we_cp, re_cp;
endgroup

function void write(transaction t);
    mon2subs.write(t); 
endfunction

task run_phase(uvm_phase phase);
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
