`ifndef FIFO_SCOREBOARD_UVM
`define FIFO_SCOREBOARD_UVM

class scoreboard extends uvm_scoreboard;
   `uvm_component_utils(scoreboard)
   uvm_tlm_analysis_fifo#(transaction) mon2scor;

   bit [31:0] wmem_q[$];       
   bit [31:0] pending_data_q[$]; 

   function new(string name="scoreboard", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor = new("mon2scor", this);      
   endfunction

   task run_phase(uvm_phase phase);
    transaction trans;
    bit [31:0] expected_val;
    bit check_needed = 0;

    forever begin
        mon2scor.get(trans);

        
        if(check_needed) begin
            if(expected_val === trans.data_out) begin
                `uvm_info("PASS", $sformatf("Match! Val: %0h", trans.data_out), UVM_LOW)
            end else begin
                `uvm_error("FAIL", $sformatf("Mismatch! Exp: %0h, Got: %0h", expected_val, trans.data_out))
            end
            check_needed = 0;
        end

        if(trans.we && !trans.full) begin
            wmem_q.push_back(trans.data_in);
        end

        if(trans.re && !trans.empty) begin
            if(wmem_q.size() > 0) begin
                expected_val = wmem_q.pop_front();
                check_needed = 1;
            end
        end
    end
endtask
endclass
`endif