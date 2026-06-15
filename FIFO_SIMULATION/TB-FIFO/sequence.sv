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

class sequence_read extends base_sequence;
   `uvm_object_utils(sequence_read)

   function new(string name = "sequence_read");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int i;

      // Write 4 data items to fill FIFO partially
      for (i = 0; i < 4; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            we == 1;
            re == 0;
         };
         finish_item(trans);
         `uvm_info("SEQ_READ", $sformatf("Write transaction %0d", i), UVM_NONE);
      end

      // Read 4 data items to assert re=1
      for (i = 0; i < 4; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            we == 0;
            re == 1;
         };
         finish_item(trans);
         `uvm_info("SEQ_READ", $sformatf("Read transaction %0d", i), UVM_NONE);
      end
   endtask
endclass

class sequence_data_bins_cr extends base_sequence;
   `uvm_object_utils(sequence_data_bins_cr)

   function new(string name="sequence_data_bins_cr");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int write_count;
      // Use randc to cycle through uncovered bins
      randc int bin_selector;
      // Constrain bin_selector to values 1..8 (mid1..mid7, high)
      constraint bin_c { bin_selector inside {[1:8]}; }
      
      // Local variables for data ranges
      int data_low, data_high;
      
      write_count = 0;
      
      // Run 50 iterations to ensure all bins are hit
      repeat (50) begin
         // Randomize bin_selector to pick next target bin
         if (!this.randomize(bin_selector)) begin
            `uvm_error("SEQ_CR", "Failed to randomize bin_selector")
         end
        
         // Map bin_selector to data range
         case (bin_selector)
            1: begin data_low = 3;  data_high = 5;  end
            2: begin data_low = 6;  data_high = 8;  end
            3: begin data_low = 9;  data_high = 11; end
            4: begin data_low = 12; data_high = 14; end
            5: begin data_low = 15; data_high = 17; end
            6: begin data_low = 18; data_high = 20; end
            7: begin data_low = 21; data_high = 23; end
            8: begin data_low = 24; data_high = 30; end
         endcase
        
         // Write transaction targeting uncovered bin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
            we == 1;
            re == 0;
            data_in inside {[data_low:data_high]};
         };
         finish_item(trans);
         write_count++;
         `uvm_info("SEQ_CR", $sformatf("Write %0d: data_in=0x%08h (bin %0d)", write_count, trans.data_in, bin_selector), UVM_NONE);
        
         // After every 2 writes, perform a read to prevent FIFO overflow
         if (write_count % 2 == 0) begin
            trans = transaction::type_id::create("trans");
            start_item(trans);
            trans.randomize with {
               we == 0;
               re == 1;
            };
            finish_item(trans);
            `uvm_info("SEQ_CR", "Read transaction to prevent FIFO overflow", UVM_NONE);
         end
      end
   endtask
endclass

`endif




