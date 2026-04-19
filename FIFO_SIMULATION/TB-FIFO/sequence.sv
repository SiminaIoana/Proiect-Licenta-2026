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
/*------------------------SEQUENCE_3---------------------------*/
/*-------------------------------------------------------------*/
class sequence_3 extends base_sequence;
    `uvm_object_utils(sequence_3)

    int count3;

   function new(string name="sequence_3");
      super.new(name);
   endfunction
   task body();
      transaction trans;
      repeat(100) begin
         trans=transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize with {
                              re==1;
                              we==0;
                                 };
         finish_item(trans);
         `uvm_info("SEQUENCE_TRANSACTION_COUNT","",UVM_NONE);
      end
      repeat(200) begin
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


// FILE: sequence.sv
/*-------------------------------------------------------------*/
/*------------------------SEQUENCE_4---------------------------*/
/*-------------------------------------------------------------*/
class sequence_4 extends base_sequence;
    `uvm_object_utils(sequence_4)

    function new(string name="sequence_4");
        super.new(name);
    endfunction

    task body();
        transaction trans;
        // Generate values in the 0-30 range to hit the coverage bins
        repeat(50) begin
            trans = transaction::type_id::create("trans");
            start_item(trans);
            // Constrain data_in to be in the small range [0:30]
            // Also include corner cases for full 32-bit range
           if (!trans.randomize() with {
                data_in inside {[0:30]};
                re inside {0,1};
                we inside {0,1};
            }) begin
                `uvm_error("SEQ4", "Randomization failed")
            end
            finish_item(trans);
            `uvm_info("SEQUENCE_4", $sformatf("Generated data_in=0x%0h (%0d)", trans.data_in, trans.data_in), UVM_MEDIUM);
        end
        
        // Generate corner cases to ensure all bins are covered
        repeat(10) begin
            trans = transaction::type_id::create("trans");
            start_item(trans);
            // Generate specific corner values
            if (!trans.randomize() with{
                data_in inside {32'h0, 32'hFFFF_FFFF, 32'h0000_0001, 32'h7FFF_FFFF, 32'h8000_0000};
                re inside {0,1};
                we inside {0,1};
            }) begin
                `uvm_error("SEQ4", "Randomization failed")
            end
            finish_item(trans);
            `uvm_info("SEQUENCE_4", $sformatf("Corner case data_in=0x%0h", trans.data_in), UVM_MEDIUM);
        end
    endtask
endclass
`endif