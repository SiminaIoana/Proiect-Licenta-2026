// FILE: test.sv
`ifndef FIFO_TEST_UVM
`define FIFO_TEST_UVM

`include "include.sv"

/*-------------------------------------------------------------*/
/*------------------------BASE TEST----------------------------*/
/*-------------------------------------------------------------*/
class base_test extends uvm_test;
   `uvm_component_utils(base_test)
   environment environment_h;

   function new(string name="base_test",uvm_component parent=null);
      super.new(name,parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      environment_h=environment::type_id::create("environment_h",this);
   endfunction
endclass

/*-------------------------------------------------------------*/
/*---------------------TEST CASE 1-----------------------------*/
/*-------------------------------------------------------------*/
class test_case_1 extends base_test;
   `uvm_component_utils(test_case_1)
   
   function new(string name="test_case_1",uvm_component parent=null);
      super.new(name,parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
   endfunction

   task run_phase(uvm_phase phase);
      sequence_1 sequence_h;
      phase.raise_objection(this);
      sequence_h=sequence_1::type_id::create("sequence_h",this);
      `uvm_info("TEST_SEQUENCE_STARTED","",UVM_NONE);
      sequence_h.start(environment_h.agent_h.sequencer_h);
      phase.drop_objection(this);
   endtask
endclass

class test_data_bins extends base_test;
   `uvm_component_utils(test_data_bins)
   
   function new(string name="test_data_bins", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
   endfunction

   task run_phase(uvm_phase phase);
      sequence_data_bins sequence_h;
      phase.raise_objection(this);
      sequence_h = sequence_data_bins::type_id::create("sequence_h", this);
      `uvm_info("TEST_DATA_BINS", "Starting sequence_data_bins", UVM_NONE);
      sequence_h.start(environment_h.agent_h.sequencer_h);
      phase.drop_objection(this);
   endtask
endclass

`endif

