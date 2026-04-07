`ifndef FIFO_TRANSACTION_UVM
`define FIFO_TRANSACTION_UVM

`include "include.sv"

typedef enum int{ 
   FIFO_IDLE         = 0,     //RESET ACTIVE
   NORMAL_WRITE      = 1,     // we = 1, re = 0, full = 0
   NORMAL_READ       = 2,     // we = 0, re = 1, empty = 0
   SIMULTANEOUS_RW   = 3,     // we = 1, re = 1
   WRITE_WHILE_FULL  = 4,     // we = 1, full = 1
   READ_WHILE_EMPTY  = 5,     // re = 1, empty = 1
   NO_OPERATION      = 6      // we = 0, re = 0
 } fifo_state_e;


class transaction extends uvm_sequence_item;

   rand bit re;
   rand bit we;
   rand bit [`DATA_WIDTH-1:0]data_in;
   bit [`DATA_WIDTH-1:0]data_out;
   bit empty;
   bit full;
   static int global_counter=0;
   int packet_id;

   // fifo state
   fifo_state_e fifo_state_tag = FIFO_IDLE;

   constraint c_indata{data_in inside{[0:32'hFFFF_FFFF]};}
   constraint ctrl{soft re inside {0,1}; we inside {0,1};}


   `uvm_object_utils_begin(transaction)
   `uvm_field_int(re,UVM_ALL_ON)
   `uvm_field_int(we,UVM_ALL_ON)
   `uvm_field_int(data_in,UVM_ALL_ON)
   `uvm_field_int(data_out,UVM_ALL_ON)
   `uvm_field_int(empty,UVM_ALL_ON)
   `uvm_field_int(full,UVM_ALL_ON)
   `uvm_field_int(packet_id, UVM_ALL_ON | UVM_DEC)
   `uvm_field_enum(fifo_state_e, fifo_state_tag, UVM_ALL_ON)
   `uvm_object_utils_end

   function new(string name="transaction");
      super.new(name);
   endfunction

   function void post_randomize();
        this.packet_id = global_counter;
        global_counter++;
    endfunction

   // function for logging in monitor
   function string get_state_str();
      case (fifo_state_tag)
         FIFO_IDLE:        return "IDLE";
         NORMAL_WRITE:     return "NORMAL_WRITE";
         NORMAL_READ:      return "NORMAL_READ";
         SIMULTANEOUS_RW:  return "SIMULTANEOUS_RW";
         WRITE_WHILE_FULL: return "WRITE_WHILE_FULL";
         READ_WHILE_EMPTY: return "READ_WHILE_EMPTY";
         NO_OPERATION:     return "NO_OP";
         default:          return "UNKNOWN";
      endcase
   endfunction

   function string to_csv_row(longint unsigned clk_time);
        return $sformatf("%0d,%0t,%0b,%0b,0x%08h,0x%08h,%0b,%0b,%s",
            packet_id, clk_time, we, re, data_in, data_out,
            full, empty, get_state_str());
    endfunction

endclass

`endif