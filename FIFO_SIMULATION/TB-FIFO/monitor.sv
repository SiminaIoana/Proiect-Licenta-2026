`ifndef FIFO_MONITOR_UVM
`define FIFO_MONITOR_UVM
`include "include.sv"

//`define vintf_h vif.monitor_mp.monitor_cb
`define vintf_h vif.monitor_cb
class monitor extends uvm_monitor;
   `uvm_component_utils(monitor)

   //virtual fifo_intf vif;
   virtual fifo_intf.monitor_mp vif;
   transaction trans;

   uvm_analysis_port#(transaction) mon2scor;

   function new(string name="monitor",uvm_component parent=null);
      super.new(name,parent);
   endfunction

   function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      mon2scor=new("mon2scor",this);
       if(!uvm_config_db#(virtual fifo_intf)::get(this,"","vintf",vif)) begin
         `uvm_fatal("MONITOR_CONNECTION_NOT_ESTABLISHED","");
      end
      else begin
         `uvm_info("MONITOR_CONNECTION_ESTABLISHED","",UVM_NONE);
      end
   endfunction
/*
   task run_phase(uvm_phase phase);
      forever begin
         if(vif.reset==1) begin
            trans=transaction::type_id::create("trans",this);
            trans.we       = `vintf_h.we;        
            trans.re       = `vintf_h.re;
            trans.full     = `vintf_h.full;
            trans.empty    = `vintf_h.empty;
            trans.data_in  = `vintf_h.data_in;
            trans.data_out = `vintf_h.data_out;
            @(posedge vif.clk);
            mon2scor.write(trans);
            `uvm_info("MONITOR_TO_SCOREBOARD_SENT","",UVM_NONE);
         end
         else @(posedge vif.clk);
      end
   endtask
   
   task run_phase(uvm_phase phase);
      forever begin
         @(vif.monitor_cb); // Așteptăm frontul de ceas gestionat de clocking block

         if(vif.reset == 1) begin
            // Detectăm dacă a existat o comandă în acest ciclu
            if (`vintf_h.we | `vintf_h.re) begin
               trans = transaction::type_id::create("trans", this);
               trans.we = `vintf_h.we;
               trans.re = `vintf_h.re;
               trans.data_in = `vintf_h.data_in;

               // FIX SINCRONIZARE: Dacă a fost o citire, data_out apare pe magistrală 
               // abia în ciclul următor conform RTL-ului tău (reg data_out).
               if (trans.re &&!`vintf_h.empty) begin
                  @(vif.monitor_cb); 
               end

               trans.data_out = `vintf_h.data_out;
               trans.full     = `vintf_h.full;
               trans.empty    = `vintf_h.empty;

               mon2scor.write(trans);
            end
         end
      end
   endtask

*/
task run_phase(uvm_phase phase);
   forever begin
      @(vif.monitor_cb); // Se sincronizează pe frontul de ceas
      
      if(vif.reset == 1) begin
         trans = transaction::type_id::create("trans", this);
         
         // Citim semnalele în ciclul curent
         trans.we       = `vintf_h.we;
         trans.re       = `vintf_h.re;
         trans.data_in  = `vintf_h.data_in;
         // data_out eșantionat acum este rezultatul citirii cerute la ceasul anterior
         trans.data_out = `vintf_h.data_out; 
         trans.full     = `vintf_h.full;
         trans.empty    = `vintf_h.empty;

         // Trimitem pachetul la FIECARE ceas pentru a asigura sincronizarea pipeline-ului
         mon2scor.write(trans);
      end
   end
endtask
endclass
`endif
