`ifndef FIFO_INTERFACE_UVM
`define FIFO_INTERFACE_UVM

// -------------------------------------------------------------
// Interfata de comanda / intrare
// Folosita de:
// - driver
// - input_monitor
// -------------------------------------------------------------
interface fifo_cmd_intf(input logic clk, reset);

   logic wr_en;
   logic rd_en;
   logic flush;
   logic q_addr;
   logic [`DATA_WIDTH-1:0] data_in;


   // Clocking block pentru driver
   clocking driver_cb @(posedge clk);
      output wr_en;
      output rd_en;
      output flush;
      output q_addr;
      output data_in;
   endclocking


   // Clocking block pentru input_monitor
   clocking monitor_cb @(posedge clk);
      input wr_en;
      input rd_en;
      input flush;
      input q_addr;
      input data_in;
   endclocking


   modport driver_mp(
      clocking driver_cb,
      input clk,
      input reset
   );


   modport monitor_mp(
      clocking monitor_cb,
      input clk,
      input reset
   );

endinterface



// -------------------------------------------------------------
// Interfata de iesire pentru o singura coada FIFO
// Se instantiaza de doua ori in top.sv:
// - out_if_q0
// - out_if_q1
// -------------------------------------------------------------
interface fifo_out_intf(input logic clk, reset);

   logic [`DATA_WIDTH-1:0] data_out;

   logic full;
   logic empty;
   logic almost_full;
   logic almost_empty;

   logic overflow;
   logic underflow;
   logic valid;


   // Clocking block pentru output_monitor
   clocking monitor_cb @(posedge clk);
      input data_out;
      input full;
      input empty;
      input almost_full;
      input almost_empty;
      input overflow;
      input underflow;
      input valid;
   endclocking


   modport monitor_mp(
      clocking monitor_cb,
      input clk,
      input reset
   );


   // ----------------------------------------------------------
   // Assertions locale pe semnalele unei singure cozi FIFO
   // ----------------------------------------------------------
   // Aceste verificari nu inlocuiesc scoreboard-ul.
   // Ele verifica doar combinatii locale de semnale care nu ar
   // trebui sa apara niciodata pentru o coada FIFO corecta.
   // ----------------------------------------------------------

   property p_not_full_and_empty;
      @(posedge clk) disable iff (reset == 1'b0)
         !(full && empty);
   endproperty


   property p_not_almost_full_and_almost_empty;
      @(posedge clk) disable iff (reset == 1'b0)
         !(almost_full && almost_empty);
   endproperty


   property p_not_full_and_almost_empty;
      @(posedge clk) disable iff (reset == 1'b0)
         !(full && almost_empty);
   endproperty


   property p_not_empty_and_almost_full;
      @(posedge clk) disable iff (reset == 1'b0)
         !(empty && almost_full);
   endproperty




   property p_not_overflow_and_valid;
      @(posedge clk) disable iff (reset == 1'b0)
         !(overflow && valid);
   endproperty


   property p_not_underflow_and_valid;
      @(posedge clk) disable iff (reset == 1'b0)
         !(underflow && valid);
   endproperty


   property p_not_overflow_and_underflow;
      @(posedge clk) disable iff (reset == 1'b0)
         !(overflow && underflow);
   endproperty


   assert property (p_not_full_and_empty)
      else $error("FIFO_OUT_ASSERT: full and empty are active at the same time.");


   assert property (p_not_almost_full_and_almost_empty)
      else $error("FIFO_OUT_ASSERT: almost_full and almost_empty are active at the same time.");


   assert property (p_not_full_and_almost_empty)
      else $error("FIFO_OUT_ASSERT: full and almost_empty are active at the same time.");


   assert property (p_not_empty_and_almost_full)
      else $error("FIFO_OUT_ASSERT: empty and almost_full are active at the same time.");


   assert property (p_not_overflow_and_valid)
      else $error("FIFO_OUT_ASSERT: overflow and valid are active at the same time.");


   assert property (p_not_underflow_and_valid)
      else $error("FIFO_OUT_ASSERT: underflow and valid are active at the same time.");


   assert property (p_not_overflow_and_underflow)
      else $error("FIFO_OUT_ASSERT: overflow and underflow are active at the same time.");

endinterface

`endif