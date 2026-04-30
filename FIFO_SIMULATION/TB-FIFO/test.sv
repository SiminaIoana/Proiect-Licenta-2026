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

// ... (existing content) ...

/*-------------------------------------------------------------*/
/*---------------------TEST_FILL_FIFO--------------------------*/
/*-------------------------------------------------------------*/
class test_fill_fifo extends base_test;
   `uvm_component_utils(test_fill_fifo)

   function new(string name="test_fill_fifo", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
   endfunction

   task run_phase(uvm_phase phase);
      fill_fifo_sequence sequence_h;
      phase.raise_objection(this);
      sequence_h = fill_fifo_sequence::type_id::create("sequence_h", this);
      `uvm_info("TEST_FILL_FIFO", "Starting fill_fifo_sequence", UVM_NONE);
      sequence_h.start(environment_h.agent_h.sequencer_h);
      phase.drop_objection(this);
   endtask

endclass

/*-------------------------------------------------------------*/
/*---------------------TEST_DATA_RANGE-------------------------*/
/*-------------------------------------------------------------*/
class test_data_range extends base_test;
   `uvm_component_utils(test_data_range)

   function new(string name="test_data_range", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
   endfunction

   task run_phase(uvm_phase phase);
      data_range_sequence sequence_h;
      phase.raise_objection(this);
      sequence_h = data_range_sequence::type_id::create("sequence_h", this);
      `uvm_info("TEST_DATA_RANGE", "Starting data_range_sequence", UVM_NONE);
      sequence_h.start(environment_h.agent_h.sequencer_h);
      phase.drop_objection(this);
   endtask

endclass

`endif

