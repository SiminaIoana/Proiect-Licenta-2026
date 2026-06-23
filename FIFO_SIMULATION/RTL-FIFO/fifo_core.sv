//---------------------------------------------------------------------------//
//------------------------------- FIFO CORE ---------------------------------//
//---------------------------------------------------------------------------//

module fifo_core (
    clk,
    reset,
    wr_en,
    rd_en,
    flush,
    data_in,
    data_out,
    full,
    empty,
    almost_full,
    almost_empty,
    overflow,
    underflow,
    valid
);

input clk;
input reset;          // reset activ pe 0
input wr_en;
input rd_en;
input flush;
input [31:0] data_in;

output reg [31:0] data_out;
output full;
output empty;
output almost_full;
output almost_empty;
output reg overflow;
output reg underflow;
output reg valid;

reg [31:0] mem [0:7];
reg [2:0] waddr;
reg [2:0] raddr;
reg [3:0] count_reg;

integer i;

wire read_ok;
wire write_ok;

assign empty = (count_reg == 4'd0);
assign full  = (count_reg == 4'd8);

assign almost_empty = (count_reg == 4'd1);
  assign almost_full  = (count_reg == 4'd7);

assign read_ok = rd_en && !empty;

// Scrierea este permisa si cand FIFO-ul este full,
// daca in acelasi ciclu exista o citire valida.
assign write_ok = wr_en && (!full || read_ok);

always @(posedge clk or negedge reset) begin
    if (reset == 1'b0) begin
        waddr <= 3'd0;
        raddr <= 3'd0;
        count_reg <= 4'd0;
        data_out <= 32'd0;

        overflow <= 1'b0;
        underflow <= 1'b0;
        valid <= 1'b0;

        for (i = 0; i < 8; i = i + 1) begin
            mem[i] <= 32'd0;
        end
    end
    else begin
        // overflow, underflow si valid sunt semnale de tip puls
        overflow <= 1'b0;
        underflow <= 1'b0;
        valid <= 1'b0;

        // flush are prioritate peste read/write
        if (flush == 1'b1) begin
            waddr <= 3'd0;
            raddr <= 3'd0;
            count_reg <= 4'd0;
            data_out <= 32'd0;
            valid <= 1'b0;
        end
        else begin

            // Citire
            if (rd_en == 1'b1) begin
                if (read_ok == 1'b1) begin
                    data_out <= mem[raddr];
                    raddr <= raddr + 1'b1;
                    valid <= 1'b1;
                end
                else begin
                    underflow <= 1'b1;
                    valid <= 1'b0;
                end
            end

            // Scriere
            if (wr_en == 1'b1) begin
                if (write_ok == 1'b1) begin
                    mem[waddr] <= data_in;
                    waddr <= waddr + 1'b1;
                end
                else begin
                    overflow <= 1'b1;
                end
            end

            // Actualizare contor intern
            case ({write_ok, read_ok})
                2'b10: count_reg <= count_reg + 1'b1; // doar scriere valida
                2'b01: count_reg <= count_reg - 1'b1; // doar citire valida
                2'b11: count_reg <= count_reg;        // read/write simultan
                default: count_reg <= count_reg;
            endcase
        end
    end
end

endmodule