// FILE: sequence.sv
`ifndef FIFO_SEQUENCE_UVM
`define FIFO_SEQUENCE_UVM

`include "include.sv"

/*-------------------------------------------------------------*/
/*----------------------BASE SEQUENCE--------------------------*/
/*-------------------------------------------------------------*/
class base_sequence extends uvm_sequence#(transaction);
   `uvm_object_utils(base_sequence)

   function new(string name = "base_sequence");
      super.new(name);
   endfunction

endclass



/*-------------------------------------------------------------*/
/*-------------------------SEQUENCE_1--------------------------*/
/*-------------------------------------------------------------*/
class sequence_1 extends base_sequence;
   `uvm_object_utils(sequence_1)

   function new(string name = "sequence_1");
      super.new(name);
   endfunction


   task body();
      transaction trans;
      int i;

      `uvm_info("SEQUENCE_1_STARTED",
                "Starting simple directed sequence for dual_fifo_router.",
                UVM_NONE)


      // ------------------------------------------------------
      //  Flush pe ambele cozi, ca sa pornim dintr-o stare clara
      // ------------------------------------------------------

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 0;
         rd_en  == 0;
         flush  == 1;
         q_addr == 0;
         data_in == 0;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 0;
         rd_en  == 0;
         flush  == 1;
         q_addr == 1;
         data_in == 0;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in == 23;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 1;
         data_in == 44;
      };
      finish_item(trans);
   endtask
endclass

class seq_cmd_hole extends base_sequence;
   `uvm_object_utils(seq_cmd_hole)

   function new(string name = "seq_cmd_hole");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int i;

      `uvm_info("SEQ_CMD_HOLE_STARTED",
                "Starting directed sequence for NORMAL_READ and SIMULTANEOUS_RW coverage.",
                UVM_NONE)

      // ------------------------------------------------------
      // 1. Write some data to queue 0 so we can read it back
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in == 42;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in == 99;
      };
      finish_item(trans);

      // ------------------------------------------------------
      // 2. NORMAL_READ: read from queue 0 (rd_en=1, wr_en=0)
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 0;
         rd_en  == 1;
         flush  == 0;
         q_addr == 0;
      };
      finish_item(trans);

      // ------------------------------------------------------
      // 3. SIMULTANEOUS_RW: write and read queue 0 at same time
      //    (wr_en=1, rd_en=1) - FIFO has data from step 1
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 1;
         flush  == 0;
         q_addr == 0;
         data_in == 77;
      };
      finish_item(trans);

      `uvm_info("SEQ_CMD_HOLE_DONE",
                "Completed directed NORMAL_READ and SIMULTANEOUS_RW transactions.",
                UVM_NONE)
   endtask

endclass

class seq_overflow extends base_sequence;
   `uvm_object_utils(seq_overflow)

   function new(string name = "seq_overflow");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int i;

      `uvm_info("SEQ_OVERFLOW_STARTED",
                "Starting directed sequence to force overflow on queue 0 and queue 1.",
                UVM_NONE)

      // ------------------------------------------------------
      // 1. Fill queue 0 with 8 writes (depth = 8)
      // ------------------------------------------------------
      for (i = 0; i < 8; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize() with {
            wr_en  == 1;
            rd_en  == 0;
            flush  == 0;
            q_addr == 0;
         };
         finish_item(trans);
      end

      // ------------------------------------------------------
      // 2. Force overflow on queue 0 (9th write, no read)
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
      };
      finish_item(trans);

      // ------------------------------------------------------
      // 3. Fill queue 1 with 8 writes (depth = 8)
      // ------------------------------------------------------
      for (i = 0; i < 8; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize() with {
            wr_en  == 1;
            rd_en  == 0;
            flush  == 0;
            q_addr == 1;
         };
         finish_item(trans);
      end

      // ------------------------------------------------------
      // 4. Force overflow on queue 1 (9th write, no read)
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 1;
      };
      finish_item(trans);

      `uvm_info("SEQ_OVERFLOW_DONE",
                "Completed overflow sequence for both queues.",
                UVM_NONE)
   endtask
endclass

`endif