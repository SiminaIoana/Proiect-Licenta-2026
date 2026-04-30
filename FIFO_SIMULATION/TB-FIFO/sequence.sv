// FILE: sequence.sv
`ifndef FIFO_SEQUENCE_UVM
`define FIFO_SEQUENCE_UVM

`include "include.sv"
/*-------------------------------------------------------------*/
/*----------------------BASE SEQUENCE--------------------------*/
/*-------------------------------------------------------------*/
class base_sequence extends uvm_sequence#(transaction);
   `uvm_object_utils(base_sequence)

   function new(string name="base_sequence");
      super.new(name);
   endfunction
 
endclass



/*-------------------------------------------------------------*/
/*-------------------------SEQUENCE_1--------------------------*/
/*-------------------------------------------------------------*/
class sequence_1 extends base_sequence;
   `uvm_object_utils(sequence_1)

   function new(string name="sequence_1");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      repeat(5) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==0;
                              we==1;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_TRANSACTION_COUNT","",UVM_NONE);
      end
   endtask

endclass

// ... (existing content) ...

/*-------------------------------------------------------------*/
/*---------------------FILL_FIFO_SEQUENCE----------------------*/
/*-------------------------------------------------------------*/
class fill_fifo_sequence extends base_sequence;
   `uvm_object_utils(fill_fifo_sequence)

   function new(string name="fill_fifo_sequence");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      repeat(10) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re == 0;
                              we == 1;
                             };
         finish_item(trans);
         `uvm_info("FILL_FIFO_SEQ", "Write transaction completed", UVM_NONE);
      end
   endtask

endclass

/*-------------------------------------------------------------*/
/*---------------------DATA_RANGE_SEQUENCE---------------------*/
/*-------------------------------------------------------------*/
class data_range_sequence extends base_sequence;
   `uvm_object_utils(data_range_sequence)

   function new(string name="data_range_sequence");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      repeat(30) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re == 0;
                              we == 1;
                              data_in inside {[0:30]};
                             };
         finish_item(trans);
         `uvm_info("DATA_RANGE_SEQ", "Write transaction with data_in in [0:30]", UVM_NONE);
      end
   endtask

endclass

`endif




