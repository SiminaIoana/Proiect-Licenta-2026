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
      int write_count;
      int unsigned bin_values[8] = '{4, 7, 10, 13, 16, 19, 22, 27};
      int idx = 0;
      
      // Write until full is observed, max 16 attempts
      for (write_count = 0; write_count < 16; write_count++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re == 0;
                              we == 1;
                              data_in == bin_values[idx % 8];
                             };
         idx++;
         finish_item(trans);
         `uvm_info("SEQUENCE_1", $sformatf("Write %0d sent", write_count+1), UVM_NONE);
         
         // Check if DUT is full by looking at the transaction's full field
         // The full signal is captured by the monitor and reflected in trans.full
         if (trans.full == 1) begin
            `uvm_info("SEQUENCE_1", "FIFO is full, stopping writes", UVM_NONE);
            break;
         end
      end
      
      // Drain the FIFO with 8 reads to allow full flag sampling
      repeat(8) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re == 1;
                              we == 0;
                             };
         finish_item(trans);
         `uvm_info("SEQUENCE_1", "Read after full", UVM_NONE);
      end
      
   endtask
endclass

class read_sequence extends base_sequence;
   `uvm_object_utils(read_sequence)

   function new(string name="read_sequence");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      
      // 3 reads while FIFO is empty (re==1, we==0)
      repeat(3) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==1;
                              we==0;
                                 };
         finish_item(trans);
         `uvm_info("READ_SEQUENCE", "Read while empty", UVM_NONE);
      end
      
      // 3 writes to fill the FIFO (we==1, re==0)
      repeat(3) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              we==1;
                              re==0;
                                 };
         finish_item(trans);
         `uvm_info("READ_SEQUENCE", "Write to fill", UVM_NONE);
      end
      
      // 2 normal reads while FIFO is not empty (re==1, we==0)
      repeat(2) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==1;
                              we==0;
                                 };
         finish_item(trans);
         `uvm_info("READ_SEQUENCE", "Normal read", UVM_NONE);
      end
      
   endtask
endclass

`endif




