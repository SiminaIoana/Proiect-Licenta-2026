`ifndef FIFO_TRANSACTION_UVM
`define FIFO_TRANSACTION_UVM

typedef enum int { 
   FIFO_IDLE         = 0,
   NORMAL_WRITE      = 1,
   NORMAL_READ       = 2,
   SIMULTANEOUS_RW   = 3,
   FLUSH_OP          = 4,
   WRITE_WHILE_FULL  = 5,
   READ_WHILE_EMPTY  = 6,
   NO_OPERATION      = 7
} fifo_state_e;


// -------------------------------------------------------------
// Command transaction
// Folosita de: sequence, sequencer, driver, input_monitor
// -------------------------------------------------------------
class transaction extends uvm_sequence_item;

   rand bit wr_en;
   rand bit rd_en;
   rand bit flush;
   rand bit q_addr;

   rand bit [`DATA_WIDTH-1:0] data_in;

   static int global_counter = 0;
   int packet_id;

   longint unsigned cycle_count;

   fifo_state_e fifo_state_tag = FIFO_IDLE;

   constraint c_data {
      data_in inside {[0:32'hFFFF_FFFF]};
   }

   constraint c_ctrl {
      soft wr_en inside {0, 1};
      soft rd_en inside {0, 1};
      soft flush == 0;
      soft q_addr inside {0, 1};
   }

   // Daca avem flush, nu facem simultan read/write.
   constraint c_flush_exclusive {
      if (flush == 1) {
         wr_en == 0;
         rd_en == 0;
      }
   }

   `uvm_object_utils_begin(transaction)
      `uvm_field_int(wr_en, UVM_ALL_ON)
      `uvm_field_int(rd_en, UVM_ALL_ON)
      `uvm_field_int(flush, UVM_ALL_ON)
      `uvm_field_int(q_addr, UVM_ALL_ON)
      `uvm_field_int(data_in, UVM_ALL_ON)

      `uvm_field_int(packet_id, UVM_ALL_ON | UVM_DEC)
      `uvm_field_int(cycle_count, UVM_ALL_ON | UVM_DEC)
      `uvm_field_enum(fifo_state_e, fifo_state_tag, UVM_ALL_ON)
   `uvm_object_utils_end

   function new(string name = "transaction");
      super.new(name);
   endfunction

   function void post_randomize();
      this.packet_id = global_counter;
      global_counter++;
      update_cmd_state();
   endfunction

   function void update_cmd_state();
      if (flush == 1)
         fifo_state_tag = FLUSH_OP;
      else if (wr_en == 1 && rd_en == 1)
         fifo_state_tag = SIMULTANEOUS_RW;
      else if (wr_en == 1 && rd_en == 0)
         fifo_state_tag = NORMAL_WRITE;
      else if (wr_en == 0 && rd_en == 1)
         fifo_state_tag = NORMAL_READ;
      else
         fifo_state_tag = NO_OPERATION;
   endfunction

   function string get_state_str();
      case (fifo_state_tag)
         FIFO_IDLE:        return "IDLE";
         NORMAL_WRITE:     return "NORMAL_WRITE";
         NORMAL_READ:      return "NORMAL_READ";
         SIMULTANEOUS_RW:  return "SIMULTANEOUS_RW";
         FLUSH_OP:         return "FLUSH";
         WRITE_WHILE_FULL: return "WRITE_WHILE_FULL";
         READ_WHILE_EMPTY: return "READ_WHILE_EMPTY";
         NO_OPERATION:     return "NO_OP";
         default:          return "UNKNOWN";
      endcase
   endfunction

   function string to_csv_row(longint unsigned clk_time);
      update_cmd_state();

      return $sformatf("%0d,%0t,%0d,%0b,%0b,%0b,0x%08h,%s",
                       packet_id,
                       clk_time,
                       q_addr,
                       wr_en,
                       rd_en,
                       flush,
                       data_in,
                       get_state_str());
   endfunction

endclass


// -------------------------------------------------------------
// Output transaction
// Folosita de: output_monitor_q0 si output_monitor_q1
// -------------------------------------------------------------
class out_transaction extends uvm_sequence_item;

   bit queue_id;

   bit [`DATA_WIDTH-1:0] data_out;

   bit full;
   bit empty;
   bit almost_full;
   bit almost_empty;

   bit overflow;
   bit underflow;
   bit valid;

   longint unsigned cycle_count;

   fifo_state_e fifo_state_tag = FIFO_IDLE;

   `uvm_object_utils_begin(out_transaction)
      `uvm_field_int(queue_id, UVM_ALL_ON)
      `uvm_field_int(data_out, UVM_ALL_ON)

      `uvm_field_int(full, UVM_ALL_ON)
      `uvm_field_int(empty, UVM_ALL_ON)
      `uvm_field_int(almost_full, UVM_ALL_ON)
      `uvm_field_int(almost_empty, UVM_ALL_ON)

      `uvm_field_int(overflow, UVM_ALL_ON)
      `uvm_field_int(underflow, UVM_ALL_ON)
      `uvm_field_int(valid, UVM_ALL_ON)

      `uvm_field_int(cycle_count, UVM_ALL_ON | UVM_DEC)
      `uvm_field_enum(fifo_state_e, fifo_state_tag, UVM_ALL_ON)
   `uvm_object_utils_end

   function new(string name = "out_transaction");
      super.new(name);
   endfunction

   function void update_out_state();
      if (overflow == 1)
         fifo_state_tag = WRITE_WHILE_FULL;
      else if (underflow == 1)
         fifo_state_tag = READ_WHILE_EMPTY;
      else if (valid == 1)
         fifo_state_tag = NORMAL_READ;
      else
         fifo_state_tag = FIFO_IDLE;
   endfunction

   function string get_state_str();
      case (fifo_state_tag)
         FIFO_IDLE:        return "IDLE";
         NORMAL_WRITE:     return "NORMAL_WRITE";
         NORMAL_READ:      return "NORMAL_READ";
         SIMULTANEOUS_RW:  return "SIMULTANEOUS_RW";
         FLUSH_OP:         return "FLUSH";
         WRITE_WHILE_FULL: return "WRITE_WHILE_FULL";
         READ_WHILE_EMPTY: return "READ_WHILE_EMPTY";
         NO_OPERATION:     return "NO_OP";
         default:          return "UNKNOWN";
      endcase
   endfunction

   function string to_csv_row(longint unsigned clk_time);
      update_out_state();

      return $sformatf("%0t,%0d,0x%08h,%0b,%0b,%0b,%0b,%0b,%0b,%0b,%s",
                       clk_time,
                       queue_id,
                       data_out,
                       full,
                       empty,
                       almost_full,
                       almost_empty,
                       overflow,
                       underflow,
                       valid,
                       get_state_str());
   endfunction

endclass

`endif