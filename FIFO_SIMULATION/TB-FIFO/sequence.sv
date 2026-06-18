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
         `uvm_info("SEQUENCE_1_TRANSACTION_COUNT","",UVM_NONE);
      end
   endtask
endclass

class sequence_data_bins extends base_sequence;
   `uvm_object_utils(sequence_data_bins)

   function new(string name="sequence_data_bins");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      transaction read_trans;
      bit [31:0] data_values[8];
      data_values[0] = 4;   // mid1 bin [3:5]
      data_values[1] = 7;   // mid2 bin [6:8]
      data_values[2] = 10;  // mid3 bin [9:11]
      data_values[3] = 13;  // mid4 bin [12:14]
      data_values[4] = 16;  // mid5 bin [15:17]
      data_values[5] = 19;  // mid6 bin [18:20]
      data_values[6] = 22;  // mid7 bin [21:23]
      data_values[7] = 25;  // high bin [24:30]

      for (int i = 0; i < 8; i++) begin
         // Write transaction with specific data_in value
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            re == 0;
            we == 1;
            data_in == data_values[i];
         };
         finish_item(trans);
         `uvm_info("SEQUENCE_DATA_BINS", $sformatf("Write data_in=0x%08h", data_values[i]), UVM_NONE);

         // Read transaction to drain one entry (keep FIFO from filling up)
         read_trans = transaction::type_id::create("read_trans");
         start_item(read_trans);
         read_trans.randomize with {
            re == 1;
            we == 0;
         };
         finish_item(read_trans);
         `uvm_info("SEQUENCE_DATA_BINS", "Read transaction sent", UVM_NONE);
      end
   endtask
endclass

`endif




