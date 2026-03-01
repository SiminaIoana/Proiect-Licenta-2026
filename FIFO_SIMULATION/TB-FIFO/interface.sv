`ifndef FIFO_INTERFACE_UVM
`define FIFO_INTERFACE_UVM

`include "include.sv"
interface fifo_intf(input logic clk,reset);

   logic re;
   logic we;
   logic [`DATA_WIDTH-1:0]data_in;
   logic [`DATA_WIDTH-1:0]data_out;
   logic full;
   logic empty;

   clocking driver_cb@(posedge clk);
      input data_out;
      input full;
      input empty;
      output re;
      output we;
      output data_in;
   endclocking
   modport driver_mp(clocking driver_cb,input clk,reset, input full, empty);

   clocking monitor_cb@(posedge clk);
      input data_out;
      input full;
      input empty;
      input re;
      input we;
      input data_in;
   endclocking
   modport monitor_mp(clocking monitor_cb,input clk,reset);

endinterface

`endif