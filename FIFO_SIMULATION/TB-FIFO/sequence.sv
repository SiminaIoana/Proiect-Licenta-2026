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
     
      
      // Existing 3 random writes
      repeat(3) begin
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

class sequence_data_bins_v2 extends base_sequence;
   `uvm_object_utils(sequence_data_bins_v2)

   function new(string name="sequence_data_bins_v2");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int values[8] = '{4, 7, 10, 13, 16, 19, 22, 27};
      
      foreach (values[i]) begin
         // Write the directed value
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            re == 0;
            we == 1;
            data_in == values[i];
         };
         finish_item(trans);
         
         // Read to keep FIFO from filling up (depth is 8, so one read per write is safe)
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            re == 1;
            we == 0;
         };
         finish_item(trans);
      end
   endtask

endclass

`endif




