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

class sequence_3 extends base_sequence;
   `uvm_object_utils(sequence_3)

   function new(string name="sequence_3");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      // Cycle through values 0 to 30 to cover all ranges[0] through ranges[9]
      for (int i = 0; i <= 30; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            re == 1;
            we == 1;
            data_in == i;
         };
         finish_item(trans);
         `uvm_info("SEQUENCE_3", $sformatf("Sent data_in = %0d", i), UVM_NONE);
      end
   endtask
endclass

`endif



