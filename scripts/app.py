import os
import sys
import traceback
import streamlit as st

# ------------------------------------------------------------
# Make project root importable
# ------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.utils_files.phases import Phase
from scripts.utils_files.status import Status


# ============================================================
# ---------------- PAGE CONFIG -------------------------------
# ============================================================
st.set_page_config(
    page_title="VerifCopilot",
    layout="wide"
)


# ============================================================
# ---------------- SESSION STATE INIT -------------------------
# ============================================================
def get_initial_state():
    return {
        "holes_list": [],
        "current_hole": {},
        "root_cause_hole": "",
        "ui_message": "",
        "ui_input": "",
        "fcov_report_path": "",
        "simulation_log_path": "",
        "dut_specs": "",
        "uvm_rules": "",
        "action_plan": "",
        "generated_code": "",
        "target_file": "",
        "iterations": 0,
        "rollback_files": {},
        "compilation_error": "",
        "coverage_holes": "",
        "iteration_tokens": 0,
        "user_command": "",
        "user_feedback": "",
        "coverage_value": 0.0,
        "previous_coverage": 0.0,
        "phase": Phase.INIT,
        "status": Status.PROCESSING,
    }


if "state" not in st.session_state:
    st.session_state.state = get_initial_state()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "Press **Start Analysis** to begin."
        }
    ]

if "run_graph" not in st.session_state:
    st.session_state.run_graph = False


# ============================================================
# ---------------- CHAT HELPERS -------------------------------
# ============================================================
def append_chat_message(role: str, content: str):
    """
    Adds a message to chat history, avoiding consecutive duplicates.
    """
    if not content:
        return

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    history = st.session_state.chat_history

    if history:
        last_msg = history[-1]
        if last_msg.get("role") == role and last_msg.get("content") == content:
            return

    history.append({
        "role": role,
        "content": content
    })


def reset_workflow_state(final_message: str = ""):
    """
    Resets internal graph state.
    Does not automatically reset chat history unless caller does it.
    """
    st.session_state.state = get_initial_state()

    if final_message:
        st.session_state.state["ui_message"] = final_message

    st.session_state.run_graph = False


def handle_session_done():
    """
    On quit / done:
    - clear full conversation;
    - reset internal workflow state;
    - keep only one final assistant message.
    """
    final_msg = "Session ended. Press **Start Analysis** to begin again."

    reset_workflow_state()

    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": final_msg
        }
    ]

    st.session_state.run_graph = False
    st.rerun()


# ============================================================
# ---------------- SIDEBAR -----------------------------------
# ============================================================
with st.sidebar:
    st.title("VerifCopilot Controls")

    if st.button("Start Analysis", use_container_width=True):
        reset_workflow_state("Starting analysis...")

        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Starting analysis..."
            }
        ]

        st.session_state.run_graph = True
        st.rerun()

    if st.button("Clear Chat", use_container_width=True):
        # Clear only the conversation.
        # Keep current coverage, holes, current phase and analysis state.
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Chat cleared. Current analysis state was preserved."
            }
        ]
        st.rerun()

    st.divider()

    # ============================================================
    # ---------------- DASHBOARD SUMMARY -------------------------
    # ============================================================
    st.subheader("Dashboard")

    coverage = st.session_state.state.get("coverage_value", 0.0)
    

    st.metric("Coverage", f"{coverage}%")


    # ============================================================
    # ---------------- CURRENT TARGET HOLE -----------------------
    # ============================================================
    current_hole = st.session_state.state.get("current_hole", {})

    if current_hole:
        st.divider()
        st.subheader("Current Target Hole")
        st.markdown(
            f"""
            <div style="
                padding: 8px 10px;
                margin-bottom: 6px;
                border-radius: 8px;
                border: 1px solid rgba(180,180,180,0.3);
                background-color: rgba(128,128,128,0.08);
            ">
                <span style="font-size: 0.85rem;">{current_hole.get("description", "")}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # ============================================================
    # ---------------- COVERAGE HOLES RAW VIEW -------------------
    # ============================================================
    coverage_holes = st.session_state.state.get("coverage_holes", "")

    st.divider()
    st.subheader("Coverage Holes")

    if coverage_holes:
        st.markdown("**Raw analyzer extraction:**")
        st.code(coverage_holes, language="text")
    else:
        st.caption("No coverage holes extracted yet.")

    # ============================================================
    # ---------------- CURRENT HOLES LIST ------------------------
    # ============================================================
    holes_list = st.session_state.state.get("holes_list", [])

    st.divider()
    st.subheader("Current Holes by ID")

    if holes_list:
        for hole in holes_list:
            hole_id = hole.get("id", "?")
            desc = hole.get("description", "")

            st.markdown(
                f"""
                <div style="
                    padding: 8px 10px;
                    margin-bottom: 6px;
                    border-radius: 8px;
                    border: 1px solid rgba(180,180,180,0.3);
                    background-color: rgba(128,128,128,0.08);
                ">
                    <b>ID {hole_id}</b><br>
                    <span style="font-size: 0.85rem;">{desc}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.caption("No current coverage holes available.")

    # ============================================================
    # ---------------- LAST RESULT SUMMARY -----------------------
    # ============================================================
    root_cause_result = st.session_state.state.get("root_cause_hole", "")

    if root_cause_result:
        st.divider()
        st.subheader("Last Analysis / Result")
        with st.expander("View details", expanded=False):
            st.markdown(root_cause_result)


# ============================================================
# ---------------- MAIN CHAT UI -------------------------------
# ============================================================
st.title("VerifCopilot")

# Display existing chat history first
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ============================================================
# ---------------- USER INPUT --------------------------------
# ============================================================
user_input = st.chat_input(
    "Type a message, choose an option, or write feedback..."
)

should_run = user_input is not None or st.session_state.get("run_graph", False)


# ============================================================
# ---------------- GRAPH EXECUTION ----------------------------
# ============================================================
if should_run:
    # ------------------------------------------------------------
    # 1. Store and display user input immediately
    # ------------------------------------------------------------
    if user_input is not None:
        append_chat_message("user", user_input)
        st.session_state.state["ui_input"] = user_input

        # Display immediately in current run,
        # because the chat history was already rendered above.
        with st.chat_message("user"):
            st.markdown(user_input)
    else:
        st.session_state.state["ui_input"] = ""

    # ------------------------------------------------------------
    # 2. Run graph
    # ------------------------------------------------------------
    with st.chat_message("assistant"):
        with st.status("AI Orchestrator Execution...", expanded=True) as status_box:
            try:
                from scripts.orchestrator import app_graph

                for step in app_graph.stream(
                    st.session_state.state,
                    stream_mode="updates"
                ):
                    for node_name, output in step.items():
                        # ---------------- node progress ----------------
                        if node_name == "rag_builder":
                            st.write("Reading documentation and retrieving RAG context...")

                        elif node_name == "checker":
                            st.write("Running Vivado simulation and collecting reports...")

                        elif node_name == "analyzer":
                            st.write("Analyzing coverage holes, logs, RTL, and testbench...")

                        elif node_name == "generator":
                            st.write("Generating SystemVerilog / MakeSVfile changes...")

                        elif node_name == "human_interaction":
                            st.write("Reached a decision point. Waiting for user input...")

                        elif node_name == "rollback":
                            st.write("Restoring previous code version...")

                        elif node_name == "phase_controller":
                            st.write("Updating workflow phase...")

                        # ---------------- update state ----------------
                        if output:
                            st.session_state.state.update(output)

                status_box.update(
                    label="Execution complete.",
                    state="complete",
                    expanded=False
                )

                # Clean temporary input
                st.session_state.state["ui_input"] = ""
                st.session_state.run_graph = False

                # ------------------------------------------------------------
                # 3. Handle DONE / quit branch
                # ------------------------------------------------------------
                if st.session_state.state.get("phase") == Phase.DONE:
                    handle_session_done()

                # ------------------------------------------------------------
                # 4. Normal assistant response
                # ------------------------------------------------------------
                ai_msg = st.session_state.state.get("ui_message", "")

                if not ai_msg:
                    ai_msg = (
                        "Processing completed. Please continue with the next available action."
                    )

                st.markdown(ai_msg)
                append_chat_message("assistant", ai_msg)

                st.rerun()

            except Exception as e:
                status_box.update(
                    label="Error detected!",
                    state="error",
                    expanded=True
                )

                error_trace = traceback.format_exc()

                print("\n" + "=" * 60)
                print("DETALII EROARE PENTRU TERMINAL:")
                print(error_trace)
                print("=" * 60 + "\n")

                st.error(f"**Eroare Orchestrator:** {str(e)}")

                with st.expander("Vezi detalii eroare / traceback", expanded=True):
                    st.code(error_trace, language="python")

                st.stop()