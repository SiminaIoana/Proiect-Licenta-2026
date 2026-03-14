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
    coverpoint trans.we {
        bins we_high = {1'b1};
        bins we_low = {1'b0};
    }
    coverpoint trans.data_in {
        bins data_in_low = {[32'h0000_0000:32'h0000_FFFF]};
        bins data_in_high = {[32'h0001_0000:32'hFFFF_FFFF]};
    }
    coverpoint trans.full {
        bins full_high = {1'b1};
        bins full_low = {1'b0};
    }
    coverpoint trans.re {
        bins re_high = {1'b1};
        bins re_low = {1'b0};
    }
    coverpoint trans.empty {
        bins empty_high = {1'b1};
        bins empty_low = {1'b0};
    }
    cross trans.we, trans.re;
    cross trans.full, trans.empty;
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
