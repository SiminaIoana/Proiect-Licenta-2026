`ifndef FIFO_SCOREBOARD_UVM
`define FIFO_SCOREBOARD_UVM

class scoreboard extends uvm_scoreboard;
   `uvm_component_utils(scoreboard)
   uvm_tlm_analysis_fifo#(transaction) mon2scor;
   coverage_container cov_handler;

   bit [31:0] wmem_q[$];       
   bit [31:0] pending_data_q[$]; 

   function new(string name="scoreboard", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor = new("mon2scor", this);
      if(!uvm_config_db#(coverage_container)::get(this, "", "cov_handler", cov_handler))
         `uvm_warning("COV", "Coverage handler not found or does not exist!")
      
   endfunction

   task run_phase(uvm_phase phase);
      transaction trans;
      forever begin
         mon2scor.get(trans);
         
         if(pending_data_q.size() > 0) begin
            bit [31:0] expected_val = pending_data_q.pop_front();
            if(expected_val == trans.data_out) begin
               `uvm_info("SCORE_MATCH", $sformatf("Match! Expected: %0h, Actual: %0h", expected_val, trans.data_out), UVM_LOW)
            end else begin
               `uvm_error("SCORE_MISMATCH", $sformatf("Mismatch! Expected: %0h, Actual: %0h", expected_val, trans.data_out))
            end
         end

         if(trans.we &&!trans.full) begin
            wmem_q.push_back(trans.data_in);
         end
         
         if(trans.re &&!trans.empty) begin
            if(wmem_q.size() > 0) begin
                pending_data_q.push_back(wmem_q.pop_front());
            end else begin
                `uvm_error("SCOR_EMPTY_READ", "Eroare: S-a detectat citire din FIFO gol!");
            end
         end
      end
   endtask
endclass
`endif