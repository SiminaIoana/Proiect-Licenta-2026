`ifndef FIFO_INCLUDE_UVM
`define FIFO_INCLUDE_UVM

import uvm_pkg::*;
`include "uvm_macros.svh"

`include "defines.sv"
`include "interface.sv"
`include "transaction.sv"
`include "sequencer.sv"
`include "driver.sv"
`include "monitor.sv"
`include "output_monitor.sv"
`include "agent.sv"
`include "output_agent.sv"
`include "scoreboard.sv"
`include "cmd_subscriber.sv"
`include "out_subscriber.sv"
`include "environment.sv"
`include "sequence.sv"
`include "test.sv"

`endif