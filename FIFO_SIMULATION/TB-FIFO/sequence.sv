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
      repeat(100) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==1;
                              we==1;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_TRANSACTION_COUNT","",UVM_NONE);
      end
   endtask

endclass




/*-------------------------------------------------------------*/
/*------------------------SEQUENCE_2---------------------------*/
/*-------------------------------------------------------------*/
class sequence_2 extends base_sequence;
    `uvm_object_utils(sequence_2)

   function new(string name="sequence_2");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      #20
      repeat(100) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==0;
                              we==1;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_TRANSACTION_COUNT","",UVM_NONE);
      end
      repeat(150) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
          trans.randomize with {
                              re==1;
                              we==1;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_TRANSACTION_COUNT","",UVM_NONE);
      end
   endtask

endclass

/*-------------------------------------------------------------*/
/*-------------------SEQUENCE_DATA_RANGES----------------------*/
/*-------------------------------------------------------------*/
class sequence_data_ranges extends base_sequence;
   `uvm_object_utils(sequence_data_ranges)

   function new(string name="sequence_data_ranges");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      repeat(100) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              data_in inside {[0:30]};
                              re==1;
                              we==1;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_DATA_RANGES","Generated transaction with data_in in [0:30]",UVM_NONE);
      end
   endtask

endclass

`endif



