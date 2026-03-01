`ifndef FIFO_SCOREBOARD_UVM
`define FIFO_SCOREBOARD_UVM
/*
class scoreboard extends uvm_scoreboard;
   `uvm_component_utils(scoreboard)

   uvm_tlm_analysis_fifo#(transaction) mon2scor;

   bit [`DATA_WIDTH-1:0] wmem[$]; 
   bit [`DATA_WIDTH-1:0] data_exp;
   bit read_active = 0; // Flag pentru a indica o citire în curs
   bit expected_from_last_read;

   function new(string name="scoreboard", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor = new("mon2scor", this);
   endfunction


   task run_phase(uvm_phase phase);
      transaction trans;
      forever begin
         mon2scor.get(trans);
         
         if(trans.we==1 && !trans.full) begin
            wmem.push_back(trans.data_in);
         end
         
         if(trans.re == 1 && !trans.empty) begin
            if(wmem.size() > 0) begin
                data_exp = wmem.pop_front(); 
                
                if(data_exp == trans.data_out) begin
                   `uvm_info("SCOREBOARD_PASSED", $sformatf("Match! Expected: %0h, Actual: %0h", data_exp, trans.data_out), UVM_LOW);
                end
                else begin
                   `uvm_error("SCOREBOARD_FAILED", $sformatf("Mismatch! Expected: %0h, Actual: %0h", data_exp, trans.data_out));
                end
            end
            else begin
                `uvm_error("SCOR_EMPTY_READ", "Incercare de citire dintr-un model ideal gol!");
            end
         end
      end
   endtask
   
endclass
*/
class scoreboard extends uvm_scoreboard;
   `uvm_component_utils(scoreboard)
   uvm_tlm_analysis_fifo#(transaction) mon2scor;

   bit [31:0] wmem_q[$];         // Modelul memoriei interne (32 biți)
   bit [31:0] pending_data_q[$]; // Pipeline-ul pentru data_out (32 biți)

   function new(string name="scoreboard", uvm_component parent=null);
      super.new(name, parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor = new("mon2scor", this);
   endfunction

   task run_phase(uvm_phase phase);
      transaction trans;
      forever begin
         mon2scor.get(trans);
         
         // 1. VERIFICARE: Dacă există o citire declanșată anterior, verificăm rezultatul ACUM
         if(pending_data_q.size() > 0) begin
            bit [31:0] expected_val = pending_data_q.pop_front();
            if(expected_val == trans.data_out) begin
               `uvm_info("SCORE_MATCH", $sformatf("Match! Expected: %0h, Actual: %0h", expected_val, trans.data_out), UVM_LOW)
            end else begin
               `uvm_error("SCORE_MISMATCH", $sformatf("Mismatch! Expected: %0h, Actual: %0h", expected_val, trans.data_out))
            end
         end

         // 2. MODELARE SCRIERE: Dacă avem write și FIFO nu e plin
         if(trans.we &&!trans.full) begin
            wmem_q.push_back(trans.data_in);
         end
         
         // 3. MODELARE CITIRE: Dacă avem read și FIFO nu e gol
         if(trans.re &&!trans.empty) begin
            if(wmem_q.size() > 0) begin
                // Punem valoarea în pipeline; ea va fi verificată la pachetul următor
                pending_data_q.push_back(wmem_q.pop_front());
            end else begin
                `uvm_error("SCOR_EMPTY_READ", "Eroare: S-a detectat citire din FIFO gol!");
            end
         end
      end
   endtask
endclass
`endif