`ifndef FIFO_DRIVER_UVM
`define FIFO_DRIVER_UVM

`include "include.sv"

`define cmd_vintf vif.driver_cb

class driver extends uvm_driver#(transaction);
   `uvm_component_utils(driver)

   virtual fifo_cmd_intf vif;

   int unsigned driven_count = 0;

   function new(string name = "driver", uvm_component parent = null);
      super.new(name, parent);
   endfunction


   function void build_phase(uvm_phase phase);
      super.build_phase(phase);

      if (!uvm_config_db#(virtual fifo_cmd_intf)::get(this, "", "cmd_vintf", vif)) begin
         `uvm_fatal("DRIVER_CONNECTION_NOT_ESTABLISHED",
                    "Could not get fifo_cmd_intf from uvm_config_db")
      end
      else begin
         `uvm_info("DRIVER_CONNECTION_ESTABLISHED",
                   "Driver connected to fifo_cmd_intf",
                   UVM_NONE)
      end
   endfunction


   task run_phase(uvm_phase phase);
      transaction trans;

      reset_outputs();

      forever begin
         wait_reset_inactive();

         seq_item_port.get_next_item(trans);

         driver_logic(trans);

         seq_item_port.item_done();

         driven_count++;

         `uvm_info("DRIVER_TRANSACTION",
            $sformatf("[PKT#%0d] Driven command: q_addr=%0d wr_en=%0b rd_en=%0b flush=%0b data_in=0x%08h state=%s",
                      trans.packet_id,
                      trans.q_addr,
                      trans.wr_en,
                      trans.rd_en,
                      trans.flush,
                      trans.data_in,
                      trans.get_state_str()),
            UVM_NONE)
      end
   endtask


   task wait_reset_inactive();
      while (vif.reset == 0) begin
         reset_outputs();
         @(posedge vif.clk);
      end
   endtask


   task reset_outputs();
      `cmd_vintf.wr_en   <= 1'b0;
      `cmd_vintf.rd_en   <= 1'b0;
      `cmd_vintf.flush   <= 1'b0;
      `cmd_vintf.q_addr  <= 1'b0;
      `cmd_vintf.data_in <= '0;
   endtask


   task driver_logic(transaction trans);

      trans.update_cmd_state();

      @(posedge vif.clk);

      `cmd_vintf.wr_en  <= trans.wr_en;
      `cmd_vintf.rd_en  <= trans.rd_en;
      `cmd_vintf.flush  <= trans.flush;
      `cmd_vintf.q_addr <= trans.q_addr;

      if (trans.wr_en == 1'b1)
         `cmd_vintf.data_in <= trans.data_in;
      else
         `cmd_vintf.data_in <= 32'hxxxx_xxxx;

      // Ținem comanda un singur ciclu, apoi revenim la idle.
      @(posedge vif.clk);

      `cmd_vintf.wr_en   <= 1'b0;
      `cmd_vintf.rd_en   <= 1'b0;
      `cmd_vintf.flush   <= 1'b0;
      `cmd_vintf.data_in <= 32'hxxxx_xxxx;

      // q_addr îl putem păstra stabil. Ajută la waveform.
      `cmd_vintf.q_addr <= trans.q_addr;

   endtask


   function void report_phase(uvm_phase phase);
      `uvm_info("DRIVER_SUMMARY",
         $sformatf("Total driven transactions: %0d", driven_count),
         UVM_NONE)
   endfunction

endclass

`endif