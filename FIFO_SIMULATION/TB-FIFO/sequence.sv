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
                "Starting directed sequence to hit cmd coverage holes.",
                UVM_NONE)

      // ------------------------------------------------------
      //  Flush both queues to start from a clean state
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

      // ------------------------------------------------------
      //  Generate 12 transactions targeting various cmd states
      //  and data ranges to hit uncovered coverage bins
      // ------------------------------------------------------
      for (i = 0; i < 12; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         // Alternate between write, read, simultaneous, and no-op
         // Use inline constraints to hit specific data ranges
         if (i < 4) begin
            // Writes with data in low range
            trans.randomize() with {
               wr_en  == 1;
               rd_en  == 0;
               flush  == 0;
               q_addr == (i % 2);
               data_in inside {[0:2]};
            };
         end else if (i < 8) begin
            // Reads (need data in queue first - write then read)
            // For simplicity, do simultaneous read/write to cover that bin
            trans.randomize() with {
               wr_en  == 1;
               rd_en  == 1;
               flush  == 0;
               q_addr == (i % 2);
               data_in inside {[3:5]};
            };
         end else begin
            // No-operation and flush-like commands
            trans.randomize() with {
               wr_en  == 0;
               rd_en  == 0;
               flush  == 0;
               q_addr == (i % 2);
               data_in inside {[6:8]};
            };
         end
         finish_item(trans);
      end

      // ------------------------------------------------------
      //  Additional transactions to hit corner data values
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in == 32'hFFFF_FFFF;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 1;
         data_in == 32'hAAAA_AAAA;
      };
      finish_item(trans);

      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in == 32'h5555_5555;
      };
      finish_item(trans);

      `uvm_info("SEQ_CMD_HOLE_DONE",
                "Completed directed sequence for cmd coverage holes.",
                UVM_NONE)
   endtask
endclass

class seq_fill_fifo extends base_sequence;
   `uvm_object_utils(seq_fill_fifo)

   function new(string name = "seq_fill_fifo");
      super.new(name);
   endfunction

   task body();
      transaction trans;
      int i;

      `uvm_info("SEQ_FILL_FIFO_STARTED",
                "Starting directed sequence to fill FIFO to full state.",
                UVM_NONE)

      // ------------------------------------------------------
      //  Flush both queues to start from a clean state
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

      // ------------------------------------------------------
      //  Fill queue 0 with 8 consecutive writes (no reads)
      //  to reach full state (FIFO depth = 8)
      // ------------------------------------------------------
      for (i = 0; i < 8; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize() with {
            wr_en  == 1;
            rd_en  == 0;
            flush  == 0;
            q_addr == 0;
            data_in inside {[0:2]};
         };
         finish_item(trans);
      end

      // ------------------------------------------------------
      //  One more write to queue 0 to trigger overflow
      //  (write while full)
      // ------------------------------------------------------
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 0;
         data_in inside {[0:2]};
      };
      finish_item(trans);

      // ------------------------------------------------------
      //  Flush queue 0 and repeat for queue 1
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

      // Fill queue 1 with 8 consecutive writes
      for (i = 0; i < 8; i++) begin
         trans = transaction::type_id::create("trans");
         start_item(trans);
         trans.randomize() with {
            wr_en  == 1;
            rd_en  == 0;
            flush  == 0;
            q_addr == 1;
            data_in inside {[0:2]};
         };
         finish_item(trans);
      end

      // Overflow write to queue 1
      trans = transaction::type_id::create("trans");
      start_item(trans);
      trans.randomize() with {
         wr_en  == 1;
         rd_en  == 0;
         flush  == 0;
         q_addr == 1;
         data_in inside {[0:2]};
      };
      finish_item(trans);

      `uvm_info("SEQ_FILL_FIFO_DONE",
                "Completed directed sequence for FIFO full coverage.",
                UVM_NONE)
   endtask
endclass

`endif