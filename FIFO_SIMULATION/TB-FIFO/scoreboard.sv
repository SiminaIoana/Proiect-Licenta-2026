`ifndef FIFO_SCOREBOARD_UVM
`define FIFO_SCOREBOARD_UVM

`include "include.sv"

typedef struct {
   bit queue_id;

   bit [`DATA_WIDTH-1:0] exp_data_out;

   bit exp_full;
   bit exp_empty;
   bit exp_almost_full;
   bit exp_almost_empty;

   bit exp_overflow;
   bit exp_underflow;
   bit exp_valid;

   bit check_data;
} sb_expected_s;


class scoreboard extends uvm_scoreboard;
   `uvm_component_utils(scoreboard)

   // Comenzile observate pe interfata de intrare
   uvm_tlm_analysis_fifo#(transaction) cmd_fifo;

   // Iesirile observate pentru fiecare coada
   uvm_tlm_analysis_fifo#(out_transaction) out_fifo_q0;
   uvm_tlm_analysis_fifo#(out_transaction) out_fifo_q1;

   // Modelul de referinta al celor doua FIFO-uri interne
   bit [`DATA_WIDTH-1:0] ref_q0[$];
   bit [`DATA_WIDTH-1:0] ref_q1[$];

   int unsigned checked_count = 0;
   int unsigned error_count   = 0;

   function new(string name = "scoreboard", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      cmd_fifo    = new("cmd_fifo", this);
      out_fifo_q0 = new("out_fifo_q0", this);
      out_fifo_q1 = new("out_fifo_q1", this);
   endfunction


   function void fill_expected(
      output sb_expected_s exp,
      input  bit queue_id,
      input  int unsigned q_size,
      input  bit [`DATA_WIDTH-1:0] exp_data_out,
      input  bit exp_overflow,
      input  bit exp_underflow,
      input  bit exp_valid,
      input  bit check_data
   );
      exp.queue_id = queue_id;

      exp.exp_data_out = exp_data_out;

      exp.exp_full         = (q_size == `FIFO_DEPTH);
      exp.exp_empty        = (q_size == 0);
      exp.exp_almost_full  = (q_size == (`FIFO_DEPTH - 1));
      exp.exp_almost_empty = (q_size == 1);

      exp.exp_overflow  = exp_overflow;
      exp.exp_underflow = exp_underflow;
      exp.exp_valid     = exp_valid;

      exp.check_data = check_data;
   endfunction


   function void build_expected_from_cmd(
      input  transaction cmd,
      output sb_expected_s exp_q0,
      output sb_expected_s exp_q1
   );
      int unsigned size_before;

      bit read_ok;
      bit write_ok;

      bit overflow_q0;
      bit underflow_q0;
      bit valid_q0;
      bit check_data_q0;
      bit [`DATA_WIDTH-1:0] exp_data_q0;

      bit overflow_q1;
      bit underflow_q1;
      bit valid_q1;
      bit check_data_q1;
      bit [`DATA_WIDTH-1:0] exp_data_q1;

      overflow_q0   = 1'b0;
      underflow_q0  = 1'b0;
      valid_q0      = 1'b0;
      check_data_q0 = 1'b0;
      exp_data_q0   = '0;

      overflow_q1   = 1'b0;
      underflow_q1  = 1'b0;
      valid_q1      = 1'b0;
      check_data_q1 = 1'b0;
      exp_data_q1   = '0;


      // ------------------------------------------------------
      // Comanda se aplica doar pe coada selectata de q_addr.
      // flush are prioritate peste wr_en si rd_en.
      // ------------------------------------------------------

      if (cmd.q_addr == 1'b0) begin

         if (cmd.flush == 1'b1) begin
            ref_q0.delete();
         end
         else begin
            size_before = ref_q0.size();

            read_ok  = (cmd.rd_en == 1'b1) && (size_before > 0);
            write_ok = (cmd.wr_en == 1'b1) &&
                       ((size_before < `FIFO_DEPTH) || read_ok);

            valid_q0     = read_ok;
            underflow_q0 = (cmd.rd_en == 1'b1) && !read_ok;
            overflow_q0  = (cmd.wr_en == 1'b1) && !write_ok;

            if (read_ok == 1'b1) begin
               exp_data_q0 = ref_q0.pop_front();
               check_data_q0 = 1'b1;
            end

            if (write_ok == 1'b1) begin
               ref_q0.push_back(cmd.data_in);
            end
         end

      end
      else begin

         if (cmd.flush == 1'b1) begin
            ref_q1.delete();
         end
         else begin
            size_before = ref_q1.size();

            read_ok  = (cmd.rd_en == 1'b1) && (size_before > 0);
            write_ok = (cmd.wr_en == 1'b1) &&
                       ((size_before < `FIFO_DEPTH) || read_ok);

            valid_q1     = read_ok;
            underflow_q1 = (cmd.rd_en == 1'b1) && !read_ok;
            overflow_q1  = (cmd.wr_en == 1'b1) && !write_ok;

            if (read_ok == 1'b1) begin
               exp_data_q1 = ref_q1.pop_front();
               check_data_q1 = 1'b1;
            end

            if (write_ok == 1'b1) begin
               ref_q1.push_back(cmd.data_in);
            end
         end

      end


      fill_expected(
         exp_q0,
         1'b0,
         ref_q0.size(),
         exp_data_q0,
         overflow_q0,
         underflow_q0,
         valid_q0,
         check_data_q0
      );

      fill_expected(
         exp_q1,
         1'b1,
         ref_q1.size(),
         exp_data_q1,
         overflow_q1,
         underflow_q1,
         valid_q1,
         check_data_q1
      );

   endfunction


   function void check_bit(
      input string field_name,
      input bit got,
      input bit expected,
      input bit queue_id
   );
      checked_count++;

      if (got !== expected) begin
         error_count++;

         `uvm_error("SCOREBOARD_MISMATCH",
            $sformatf("[Q%0d] %s mismatch: expected=%0b got=%0b",
                      queue_id,
                      field_name,
                      expected,
                      got))
      end
   endfunction


   function void check_data(
      input bit [`DATA_WIDTH-1:0] got,
      input bit [`DATA_WIDTH-1:0] expected,
      input bit queue_id
   );
      checked_count++;

      if (got !== expected) begin
         error_count++;

         `uvm_error("SCOREBOARD_DATA_MISMATCH",
            $sformatf("[Q%0d] data_out mismatch: expected=0x%08h got=0x%08h",
                      queue_id,
                      expected,
                      got))
      end
      else begin
         `uvm_info("SCOREBOARD_DATA_MATCH",
            $sformatf("[Q%0d] data_out match: 0x%08h",
                      queue_id,
                      got),
            UVM_LOW)
      end
   endfunction


   function void compare_output(
      input out_transaction got,
      input sb_expected_s exp
   );

      if (got.queue_id !== exp.queue_id) begin
         error_count++;

         `uvm_error("SCOREBOARD_QUEUE_ID",
            $sformatf("Queue ID mismatch: expected=%0d got=%0d",
                      exp.queue_id,
                      got.queue_id))
      end

      check_bit("full",
                got.full,
                exp.exp_full,
                exp.queue_id);

      check_bit("empty",
                got.empty,
                exp.exp_empty,
                exp.queue_id);

      check_bit("almost_full",
                got.almost_full,
                exp.exp_almost_full,
                exp.queue_id);

      check_bit("almost_empty",
                got.almost_empty,
                exp.exp_almost_empty,
                exp.queue_id);

      check_bit("overflow",
                got.overflow,
                exp.exp_overflow,
                exp.queue_id);

      check_bit("underflow",
                got.underflow,
                exp.exp_underflow,
                exp.queue_id);

      check_bit("valid",
                got.valid,
                exp.exp_valid,
                exp.queue_id);

      if (exp.check_data == 1'b1) begin
         check_data(got.data_out,
                    exp.exp_data_out,
                    exp.queue_id);
      end

   endfunction


   task run_phase(uvm_phase phase);
      transaction cmd;
      out_transaction out_q0;
      out_transaction out_q1;

      sb_expected_s exp_q0;
      sb_expected_s exp_q1;

      `uvm_info("SCOREBOARD_RUN",
                "Dual FIFO router scoreboard is running.",
                UVM_NONE)

      // ------------------------------------------------------
      // Consumam primul sample de output pentru aliniere.
      // Monitoarele de output observa iesirile inregistrate,
      // deci efectul unei comenzi se vede, practic, la urmatorul
      // sample de output.
      // ------------------------------------------------------
      out_fifo_q0.get(out_q0);
      out_fifo_q1.get(out_q1);

      forever begin
         cmd_fifo.get(cmd);

         build_expected_from_cmd(cmd, exp_q0, exp_q1);

         out_fifo_q0.get(out_q0);
         out_fifo_q1.get(out_q1);

         `uvm_info("SCOREBOARD_CMD",
            $sformatf("CMD: q_addr=%0d wr_en=%0b rd_en=%0b flush=%0b data_in=0x%08h | ref_q0_size=%0d ref_q1_size=%0d",
                      cmd.q_addr,
                      cmd.wr_en,
                      cmd.rd_en,
                      cmd.flush,
                      cmd.data_in,
                      ref_q0.size(),
                      ref_q1.size()),
            UVM_MEDIUM)

         compare_output(out_q0, exp_q0);
         compare_output(out_q1, exp_q1);
      end
   endtask


   function void report_phase(uvm_phase phase);
      `uvm_info("SCOREBOARD_SUMMARY", "================================================", UVM_NONE)
      `uvm_info("SCOREBOARD_SUMMARY", "              SCOREBOARD SUMMARY                ", UVM_NONE)
      `uvm_info("SCOREBOARD_SUMMARY", "================================================", UVM_NONE)

      `uvm_info("SCOREBOARD_SUMMARY",
         $sformatf("Total checks       : %0d", checked_count),
         UVM_NONE)

      `uvm_info("SCOREBOARD_SUMMARY",
         $sformatf("Total errors       : %0d", error_count),
         UVM_NONE)

      `uvm_info("SCOREBOARD_SUMMARY",
         $sformatf("Final ref_q0 size  : %0d", ref_q0.size()),
         UVM_NONE)

      `uvm_info("SCOREBOARD_SUMMARY",
         $sformatf("Final ref_q1 size  : %0d", ref_q1.size()),
         UVM_NONE)

      `uvm_info("SCOREBOARD_SUMMARY", "================================================", UVM_NONE)
   endfunction

endclass

`endif