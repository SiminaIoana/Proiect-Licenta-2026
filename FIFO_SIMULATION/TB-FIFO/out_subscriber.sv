`ifndef FIFO_OUT_SUBSCRIBER_UVM
`define FIFO_OUT_SUBSCRIBER_UVM

`include "include.sv"

class out_subscriber extends uvm_subscriber#(out_transaction);
   `uvm_component_utils(out_subscriber)

   out_transaction trans;

   int unsigned sample_count = 0;

   covergroup out_cg;
      option.per_instance = 1;

      queue_id_cp: coverpoint trans.queue_id {
         bins q0 = {1'b0};
         bins q1 = {1'b1};
      }

      full_cp: coverpoint trans.full {
         bins active = {1'b1};
      }

      empty_cp: coverpoint trans.empty {
         bins active = {1'b1};
      }

      almost_full_cp: coverpoint trans.almost_full {
         bins active = {1'b1};
      }

      almost_empty_cp: coverpoint trans.almost_empty {
         bins active = {1'b1};
      }

      overflow_cp: coverpoint trans.overflow {
         bins active = {1'b1};
      }

      underflow_cp: coverpoint trans.underflow {
         bins active = {1'b1};
      }

      valid_cp: coverpoint trans.valid {
         bins active = {1'b1};
      }

      out_state_cp: coverpoint trans.fifo_state_tag {
         bins idle             = {FIFO_IDLE};
         bins valid_read       = {NORMAL_READ};
         bins write_while_full = {WRITE_WHILE_FULL};
         bins read_while_empty = {READ_WHILE_EMPTY};
      }

      data_out_cp: coverpoint trans.data_out iff (trans.valid == 1'b1) {
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

      full_queue_cross: cross full_cp, queue_id_cp {
         bins full_q0 = binsof(full_cp.active) && binsof(queue_id_cp.q0);
         bins full_q1 = binsof(full_cp.active) && binsof(queue_id_cp.q1);
      }

      empty_queue_cross: cross empty_cp, queue_id_cp {
         bins empty_q0 = binsof(empty_cp.active) && binsof(queue_id_cp.q0);
         bins empty_q1 = binsof(empty_cp.active) && binsof(queue_id_cp.q1);
      }

      almost_full_queue_cross: cross almost_full_cp, queue_id_cp {
         bins almost_full_q0 =
            binsof(almost_full_cp.active) && binsof(queue_id_cp.q0);

         bins almost_full_q1 =
            binsof(almost_full_cp.active) && binsof(queue_id_cp.q1);
      }

      almost_empty_queue_cross: cross almost_empty_cp, queue_id_cp {
         bins almost_empty_q0 =
            binsof(almost_empty_cp.active) && binsof(queue_id_cp.q0);

         bins almost_empty_q1 =
            binsof(almost_empty_cp.active) && binsof(queue_id_cp.q1);
      }

      overflow_queue_cross: cross overflow_cp, queue_id_cp {
         bins overflow_q0 =
            binsof(overflow_cp.active) && binsof(queue_id_cp.q0);

         bins overflow_q1 =
            binsof(overflow_cp.active) && binsof(queue_id_cp.q1);
      }

      underflow_queue_cross: cross underflow_cp, queue_id_cp {
         bins underflow_q0 =
            binsof(underflow_cp.active) && binsof(queue_id_cp.q0);

         bins underflow_q1 =
            binsof(underflow_cp.active) && binsof(queue_id_cp.q1);
      }

      valid_queue_cross: cross valid_cp, queue_id_cp {
         bins valid_read_q0 =
            binsof(valid_cp.active) && binsof(queue_id_cp.q0);

         bins valid_read_q1 =
            binsof(valid_cp.active) && binsof(queue_id_cp.q1);
      }

   endgroup


   function new(string name = "out_subscriber", uvm_component parent = null);
      super.new(name, parent);
      out_cg = new();
   endfunction


   function void write(out_transaction t);
      trans = t;
      trans.update_out_state();

      out_cg.sample();
      sample_count++;

      `uvm_info("OUT_SUBSCRIBER_SAMPLE",
         $sformatf("Sampled OUT coverage: queue_id=%0d full=%0b empty=%0b almost_full=%0b almost_empty=%0b overflow=%0b underflow=%0b valid=%0b data_out=0x%08h state=%s",
                   trans.queue_id,
                   trans.full,
                   trans.empty,
                   trans.almost_full,
                   trans.almost_empty,
                   trans.overflow,
                   trans.underflow,
                   trans.valid,
                   trans.data_out,
                   trans.get_state_str()),
         UVM_HIGH)
   endfunction


   function void check_phase(uvm_phase phase);
      `uvm_info("OUT_COVERAGE", "------------------------------------------------", UVM_NONE)

      `uvm_info("OUT_COVERAGE",
         $sformatf("Output coverage for both queues : %0.2f %%",
                   out_cg.get_coverage()),
         UVM_NONE)

      `uvm_info("OUT_COVERAGE",
         $sformatf("OUT samples total               : %0d",
                   sample_count),
         UVM_NONE)

      `uvm_info("OUT_COVERAGE", "------------------------------------------------", UVM_NONE)
   endfunction

endclass

`endif