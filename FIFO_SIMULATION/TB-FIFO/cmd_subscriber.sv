`ifndef FIFO_CMD_SUBSCRIBER_UVM
`define FIFO_CMD_SUBSCRIBER_UVM

`include "include.sv"

class cmd_subscriber extends uvm_subscriber#(transaction);
   `uvm_component_utils(cmd_subscriber)

   transaction trans;

   int unsigned sample_count = 0;

   covergroup cmd_cg;
      option.per_instance = 1;

      q_addr_cp: coverpoint trans.q_addr {
         bins q0 = {1'b0};
         bins q1 = {1'b1};
      }

      wr_en_cp: coverpoint trans.wr_en iff (trans.flush == 1'b0) {
         bins active = {1'b1};
      }

      rd_en_cp: coverpoint trans.rd_en iff (trans.flush == 1'b0) {
         bins active = {1'b1};
      }

      flush_cp: coverpoint trans.flush {
         bins active = {1'b1};
      }

      cmd_state_cp: coverpoint trans.fifo_state_tag {
         bins normal_write    = {NORMAL_WRITE};
         bins normal_read     = {NORMAL_READ};
         bins simultaneous_rw = {SIMULTANEOUS_RW};
         bins flush_op        = {FLUSH_OP};
         bins no_operation    = {NO_OPERATION};
      }

      simultaneous_rw_cp: coverpoint trans.fifo_state_tag {
         bins active = {SIMULTANEOUS_RW};
      }

      data_in_cp: coverpoint trans.data_in
                  iff (trans.wr_en == 1'b1 && trans.flush == 1'b0) {
         bins low     = {[0:2]};
         bins mid1    = {[3:5]};
         bins mid2    = {[6:8]};
         bins mid3    = {[9:11]};
         bins mid4    = {[12:14]};
         bins mid5    = {[15:17]};
         bins mid6    = {[18:20]};
         bins mid7    = {[21:23]};
         bins high    = {[24:30]};

         bins corners = {
            32'h0000_0000,
            32'hFFFF_FFFF,
            32'hAAAA_AAAA,
            32'h5555_5555
         };
      }

      write_queue_cross: cross wr_en_cp, q_addr_cp {
         bins write_q0 = binsof(wr_en_cp.active) && binsof(q_addr_cp.q0);
         bins write_q1 = binsof(wr_en_cp.active) && binsof(q_addr_cp.q1);
      }

      read_queue_cross: cross rd_en_cp, q_addr_cp {
         bins read_q0 = binsof(rd_en_cp.active) && binsof(q_addr_cp.q0);
         bins read_q1 = binsof(rd_en_cp.active) && binsof(q_addr_cp.q1);
      }

      flush_queue_cross: cross flush_cp, q_addr_cp {
         bins flush_q0 = binsof(flush_cp.active) && binsof(q_addr_cp.q0);
         bins flush_q1 = binsof(flush_cp.active) && binsof(q_addr_cp.q1);
      }

      simultaneous_rw_queue_cross: cross simultaneous_rw_cp, q_addr_cp {
         bins simultaneous_rw_q0 =
            binsof(simultaneous_rw_cp.active) && binsof(q_addr_cp.q0);

         bins simultaneous_rw_q1 =
            binsof(simultaneous_rw_cp.active) && binsof(q_addr_cp.q1);
      }

   endgroup


   function new(string name = "cmd_subscriber", uvm_component parent = null);
      super.new(name, parent);
      cmd_cg = new();
   endfunction


   function void write(transaction t);
      trans = t;
      trans.update_cmd_state();

      cmd_cg.sample();
      sample_count++;

      `uvm_info("CMD_SUBSCRIBER_SAMPLE",
         $sformatf("Sampled CMD coverage: q_addr=%0d wr_en=%0b rd_en=%0b flush=%0b data_in=0x%08h state=%s",
                   trans.q_addr,
                   trans.wr_en,
                   trans.rd_en,
                   trans.flush,
                   trans.data_in,
                   trans.get_state_str()),
         UVM_HIGH)
   endfunction


   function void check_phase(uvm_phase phase);
      `uvm_info("CMD_COVERAGE", "------------------------------------------------", UVM_NONE)

      `uvm_info("CMD_COVERAGE",
         $sformatf("Command coverage : %0.2f %%", cmd_cg.get_coverage()),
         UVM_NONE)

      `uvm_info("CMD_COVERAGE",
         $sformatf("CMD samples      : %0d", sample_count),
         UVM_NONE)

      `uvm_info("CMD_COVERAGE", "------------------------------------------------", UVM_NONE)
   endfunction

endclass

`endif