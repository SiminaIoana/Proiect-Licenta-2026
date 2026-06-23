`include "fifo_core.sv"
//---------------------------------------------------------------------------//
//---------------------------- DUAL FIFO ROUTER -----------------------------//
//---------------------------------------------------------------------------//

module dual_fifo_router (
    clk,
    reset,

    wr_en,
    rd_en,
    flush,
    q_addr,

    data_in,

    data_out_q0,
    data_out_q1,

    full_q0,
    full_q1,
    empty_q0,
    empty_q1,

    almost_full_q0,
    almost_full_q1,
    almost_empty_q0,
    almost_empty_q1,

    overflow_q0,
    overflow_q1,
    underflow_q0,
    underflow_q1,

    valid_q0,
    valid_q1
);

input clk;
input reset;          // reset activ pe 0

input wr_en;
input rd_en;
input flush;
input q_addr;         // 0 = FIFO 0, 1 = FIFO 1

input [31:0] data_in;

output [31:0] data_out_q0;
output [31:0] data_out_q1;

output full_q0;
output full_q1;
output empty_q0;
output empty_q1;

output almost_full_q0;
output almost_full_q1;
output almost_empty_q0;
output almost_empty_q1;

output overflow_q0;
output overflow_q1;
output underflow_q0;
output underflow_q1;

output valid_q0;
output valid_q1;


// Semnale interne pentru rutarea comenzilor
wire fifo0_wr_en;
wire fifo1_wr_en;

wire fifo0_rd_en;
wire fifo1_rd_en;

wire fifo0_flush;
wire fifo1_flush;


// q_addr selecteaza FIFO-ul asupra caruia se aplica operatia
assign fifo0_wr_en = wr_en & (q_addr == 1'b0);
assign fifo1_wr_en = wr_en & (q_addr == 1'b1);

assign fifo0_rd_en = rd_en & (q_addr == 1'b0);
assign fifo1_rd_en = rd_en & (q_addr == 1'b1);

assign fifo0_flush = flush & (q_addr == 1'b0);
assign fifo1_flush = flush & (q_addr == 1'b1);


// Instanta FIFO 0
fifo_core fifo0 (
    .clk(clk),
    .reset(reset),

    .wr_en(fifo0_wr_en),
    .rd_en(fifo0_rd_en),
    .flush(fifo0_flush),

    .data_in(data_in),
    .data_out(data_out_q0),

    .full(full_q0),
    .empty(empty_q0),
    .almost_full(almost_full_q0),
    .almost_empty(almost_empty_q0),

    .overflow(overflow_q0),
    .underflow(underflow_q0),
    .valid(valid_q0)
);


// Instanta FIFO 1
fifo_core fifo1 (
    .clk(clk),
    .reset(reset),

    .wr_en(fifo1_wr_en),
    .rd_en(fifo1_rd_en),
    .flush(fifo1_flush),

    .data_in(data_in),
    .data_out(data_out_q1),

    .full(full_q1),
    .empty(empty_q1),
    .almost_full(almost_full_q1),
    .almost_empty(almost_empty_q1),

    .overflow(overflow_q1),
    .underflow(underflow_q1),
    .valid(valid_q1)
);

endmodule