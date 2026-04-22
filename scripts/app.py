import sys
import os
import streamlit as st
import traceback

# ==========================================
# ------- PAGE CONFIGURATION & SETUP -------
# ==========================================
st.set_page_config(page_title="UVM Copilot", layout="wide")

# ======================================================
# -------- PATH CONFIGURATION FOR MODULE IMPORTS -------
# ======================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# ==========================================
# -------- INIT SESSION STATE VARIABLES ----
# ==========================================
if "state" not in st.session_state:
    st.session_state.state = {
        "status": "IDLE",
        "ui_message": "Hello! I am your FCOV Assistant . Press the start button and let's work together!",
        "coverage_value": 0.0,
        "holes_list": [],
        "ui_input": "",
        "iterations": 0
    }

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": st.session_state.state["ui_message"]}
    ]

# ==========================================
# --------- SIDEBAR (DASHBOARD) --------
# ==========================================
with st.sidebar:
    st.title("Dashboard")
    
    if st.button("Start Analysis"):
        st.session_state.state["status"] = "STARTING" 
        st.session_state.state["ui_input"] = "start_trigger"
        
    st.metric(label="Functional Coverage", value=f"{st.session_state.state.get('coverage_value', 0)}%")
    
    st.subheader("Target Holes")
    holes = st.session_state.state.get("holes_list", [])
    if holes:
        st.caption(f"Found {len(holes)} areas to improve:")
        for h in holes:
            with st.expander(f"ID {h['id']} - Needs Fix", expanded=False):
                clean_desc = h['description'].lstrip('- *').strip()
                clean_desc = clean_desc.replace('*', '\*')
                st.markdown(f"*{clean_desc}*")
    else:
        st.success("No holes detected!")

# ==========================================
# -------- MAIN CHAT INTERFACE --------
# ==========================================
st.title("VerifCopilot")

# ---------DISPLAY CHAT HISTORY---------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# ----- USER INPUT & AI RESPONSE HANDLING --
# ==========================================
user_input = st.chat_input("Type 1, 2, ID or q and press Enter...")

current_input = user_input if user_input else st.session_state.state.get("ui_input")

if current_input:
    if user_input: 
        st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    st.session_state.state["ui_input"] = current_input

    with st.chat_message("assistant"):
        with st.status("AI Orchestrator Execution...", expanded=True) as status:
            try:
                from scripts.orchestrator import app_graph
                
                # Folosim .stream în loc de .invoke pentru a vedea pașii în timp real
                # stream_mode="updates" ne dă exact ce returnează fiecare nod
                for step in app_graph.stream(st.session_state.state, stream_mode="updates"):
                    for node_name, output in step.items():
                        # Afișăm în interfață ce nod se execută acum
                        if node_name == "rag_builder":
                            st.write(" Reading documentation and building RAG context...")
                        elif node_name == "checker":
                            st.write(" Running Vivado Simulation & Coverage extraction...")
                        elif node_name == "analyzer":
                            st.write(" Analyzing coverage logs and identifying holes...")
                        elif node_name == "generator":
                            st.write(" AI Generator is writing SystemVerilog code...")
                        elif node_name == "human_interaction":
                            st.write(" Reached decision point. Waiting for user...")
                        
                        st.session_state.state.update(output)

                status.update(label="Analysis Complete!", state="complete", expanded=False)
                
                st.session_state.state["ui_input"] = ""

                ai_msg = st.session_state.state.get("ui_message", "No message received from AI.")
                st.markdown(ai_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_msg})
                
                st.rerun()
                
            except Exception as e:
                status.update(label="Error detected!", state="error")
                
                # --- ASTA O SĂ VEZI ÎN TERMINAL (CMD) ---
                print("\n" + "="*60)
                print("DETALII EROARE PENTRU TERMINAL:")
                print(traceback.format_exc()) 
                print("="*60 + "\n")
                # ---------------------------------------

                st.error(f"⚠️ **Eroare Orchestrator:** {str(e)}")
                
                with st.expander("📂 Vezi detalii eroare (Traceback)", expanded=True):
                    st.code(traceback.format_exc(), language="python")
                
                st.stop()