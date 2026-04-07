import sys
import os
import streamlit as st

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
        "ui_message": "Hello! I am your FCOV Assistant . Insert the path to your testbench and RTL and press Start Analysis to begin.",
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
                # 1. Tăiem liniuța și steluța cu care începe aiurea log-ul
                clean_desc = h['description'].lstrip('- *').strip()
                
                # 2. "Anulăm" steluțele din interiorul log-ului ca să nu strice Markdown-ul
                clean_desc = clean_desc.replace('*', '\*')
                
                # 3. Acum punem textul înclinat, exact cum ai vrut
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

# Verificăm dacă avem input de la chat SAU dacă am apăsat butonul de Start
current_input = user_input if user_input else st.session_state.state.get("ui_input")

if current_input:
    if user_input: # Doar dacă e scris de om, îl punem în istoric
        st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    st.session_state.state["ui_input"] = current_input

    with st.chat_message("assistant"):
        # Creăm un container de status care arată profesional
        with st.status("AI Orchestrator Execution...", expanded=True) as status:
            try:
                from scripts.orchestrator import app_graph
                
                # Folosim .stream în loc de .invoke pentru a vedea pașii în timp real
                # stream_mode="updates" ne dă exact ce returnează fiecare nod
                for step in app_graph.stream(st.session_state.state, stream_mode="updates"):
                    for node_name, output in step.items():
                        # Afișăm în interfață ce nod se execută acum
                        if node_name == "rag_builder":
                            st.write("📖 Reading documentation and building RAG context...")
                        elif node_name == "checker":
                            st.write("⚙️ Running Vivado Simulation & Coverage extraction...")
                        elif node_name == "analyzer":
                            st.write("🔍 Analyzing coverage logs and identifying holes...")
                        elif node_name == "generator":
                            st.write("🛠️ AI Generator is writing SystemVerilog code...")
                        elif node_name == "human_interaction":
                            st.write("✅ Reached decision point. Waiting for user...")
                        
                        # Actualizăm starea internă cu ce a scos nodul respectiv
                        st.session_state.state.update(output)

                # Când bucla de stream se termină, marcăm statusul ca finalizat
                status.update(label="Analysis Complete!", state="complete", expanded=False)
                
                # REPARARE: Resetăm ui_input la gol pentru a preveni rularea automată
                st.session_state.state["ui_input"] = ""

                # Afișăm mesajul final în chat
                ai_msg = st.session_state.state.get("ui_message", "No message received from AI.")
                st.markdown(ai_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_msg})
                
                st.rerun()
                
            except Exception as e:
                status.update(label="Error detected!", state="error")
                st.error(f"Error connecting to AI Orchestrator: {str(e)}")
                st.info("Check your terminal for detailed traceback.")