// FILE: top.sv
`include "include.sv"

module top;

   bit clk;
   bit reset;


   // ----------------------------------------------------------
   // Interfata de comanda comuna
   // ----------------------------------------------------------
   fifo_cmd_intf cmd_if(
      .clk(clk),
      .reset(reset)
   );


   // ----------------------------------------------------------
   // Interfetele de iesire pentru cele doua cozi
   // ----------------------------------------------------------
   fifo_out_intf out_if_q0(
      .clk(clk),
      .reset(reset)
   );

   fifo_out_intf out_if_q1(
      .clk(clk),
      .reset(reset)
   );


   // ----------------------------------------------------------
   // Instantierea DUT-ului nou
   // ----------------------------------------------------------
   dual_fifo_router dut (
      .clk(clk),
      .reset(reset),

      .wr_en(cmd_if.wr_en),
      .rd_en(cmd_if.rd_en),
      .flush(cmd_if.flush),
      .q_addr(cmd_if.q_addr),

      .data_in(cmd_if.data_in),

      .data_out_q0(out_if_q0.data_out),
      .data_out_q1(out_if_q1.data_out),

      .full_q0(out_if_q0.full),
      .full_q1(out_if_q1.full),

      .empty_q0(out_if_q0.empty),
      .empty_q1(out_if_q1.empty),

      .almost_full_q0(out_if_q0.almost_full),
      .almost_full_q1(out_if_q1.almost_full),

      .almost_empty_q0(out_if_q0.almost_empty),
      .almost_empty_q1(out_if_q1.almost_empty),

      .overflow_q0(out_if_q0.overflow),
      .overflow_q1(out_if_q1.overflow),

      .underflow_q0(out_if_q0.underflow),
      .underflow_q1(out_if_q1.underflow),

      .valid_q0(out_if_q0.valid),
      .valid_q1(out_if_q1.valid)
   );


initial begin

   uvm_config_db#(virtual fifo_cmd_intf)::set(
      null,
      "uvm_test_top.environment_h.agent_h.driver_h",
      "cmd_vintf",
      cmd_if
   );

   uvm_config_db#(virtual fifo_cmd_intf)::set(
      null,
      "uvm_test_top.environment_h.agent_h.input_monitor_h",
      "cmd_vintf",
      cmd_if
   );

   uvm_config_db#(virtual fifo_out_intf)::set(
      null,
      "uvm_test_top.environment_h.output_agent_q0_h.output_monitor_h",
      "out_vintf",
      out_if_q0
   );

   uvm_config_db#(virtual fifo_out_intf)::set(
      null,
      "uvm_test_top.environment_h.output_agent_q1_h.output_monitor_h",
      "out_vintf",
      out_if_q1
   );

end


   // ----------------------------------------------------------
   // Clock
   // ----------------------------------------------------------
   initial begin
      clk = 1'b0;
      forever #5 clk = ~clk;
   end


   // ----------------------------------------------------------
   // Reset activ pe 0
   // ----------------------------------------------------------
   initial begin
      reset = 1'b0;

      repeat (3) @(posedge clk);

      reset = 1'b1;
   end


   // ----------------------------------------------------------
   // Pornire test UVM
   // ----------------------------------------------------------
   initial begin
      run_test();
   end


   // ----------------------------------------------------------
   // Dump pentru waveform
   // ----------------------------------------------------------
   initial begin
      $dumpfile("dump.vcd");
      $dumpvars;
   end

endmodule