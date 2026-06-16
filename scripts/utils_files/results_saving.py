import os
import csv
import datetime
from state import AgentState
from utils_files.status import Status
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage
    )


def save_to_csv(data_row, path, header=None):
    """
    Appends one row to a CSV file.

    If the file does not exist and a header is provided, 
    the header is written first.
    """
    file_exists = os.path.exists(path)

    with open(path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists and header is not None:
            writer.writerow(header)
        writer.writerow(data_row)


def save_to_file(content, path):
    """
    Appends content to a text file using visual separators for clarity.
    """
    with open(path, "a", encoding="utf-8") as file:
        file.write(content + "\n" + "="*50 + "\n\n")


def save_agent_metrics(
    agent_name: str,
    phase: str,
    hole_description: str = "",
    prompt_tokens: int = 0,
    response_tokens: int = 0,
    total_tokens: int = 0,
    duration_seconds: float = 0.0,
    status: str = "",
    notes: str = ""
):
    """
    Save experimental metrics for LLM-based agents.
    The recorded data includes agent name, phase, hole description,
    token usage, execution time, status, and additional notes.
    """
    results_dir = os.path.join("..", "results")
    os.makedirs(results_dir, exist_ok=True)

    csv_path = os.path.join(results_dir, "agent_metrics.csv")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = [
        timestamp,
        agent_name,
        phase,
        hole_description,
        prompt_tokens,
        response_tokens,
        total_tokens,
        duration_seconds,
        status,
        notes
    ]

    header = [
        "timestamp",
        "agent_name",
        "phase",
        "hole_description",
        "prompt_tokens",
        "response_tokens",
        "total_tokens",
        "duration_seconds",
        "status",
        "notes"
    ]

    save_to_csv(row, csv_path, header=header)


def get_index(data_dir: str, storage_dir: str, index_name: str):
    """
    Loads an existing index or creates a new one from a document folder.
    The persisted index is reused when available. The same vector store does
    not have to be rebuilt at every application run.
    """
    if not os.path.exists(data_dir) or not os.listdir(data_dir):
        print(f"[INDEXER INFO]: Source folder for '{index_name}' is empty or missing.")
        return None
    
    try:
        if os.path.exists(storage_dir) and os.listdir(storage_dir):
            storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
            index = load_index_from_storage(storage_context)
            return index
    except Exception as e:
        print(f"[INDEXER WARNING]: Failed to load '{index_name}' cache: {e}")

    try:
        documents = SimpleDirectoryReader(input_dir=data_dir).load_data()
        index = VectorStoreIndex.from_documents(documents)

        # The new index is persisted so it can be reused in later runs.
        os.makedirs(storage_dir, exist_ok=True)
        index.storage_context.persist(persist_dir=storage_dir)

        return index
    
    except Exception as e:
        print(f"[INDEXER ERROR]: Critical failure creating '{index_name}': {e}")
        return None
    

def save_checker_metrics(
    state: AgentState,
    status: Status,
    exec_time: float,
    coverage_val: str,
    error_summary: str,
    raw_errors: str
):
    """
    Saves experimental metrics produced by the checker node.
    These metrics describe the Vivado/XSim run, the extracted coverage value 
    and the detected error type.
    """

    results_dir = os.path.join("..", "results")
    os.makedirs(results_dir, exist_ok=True)

    raport_path = os.path.join(results_dir, "raport_experimental.txt")
    csv_path = os.path.join(results_dir, "experimental_metrics_FIFO3.csv")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generated_solutions = state.get("iterations", 0)
    tokens = state.get("iteration_tokens", 0)

    # Save to TXT
    content_txt = (
        f"[{timestamp}] "
        f"GeneratedSolutions: {generated_solutions} | "
        f"Status: {status.value} | "
        f"Coverage: {coverage_val} | "
        f"Vivado_exec_time: {exec_time}s\n"
    )

    if status == Status.FAILED:
        content_txt += f"Errors:\n{raw_errors}\n"

    save_to_file(content_txt, raport_path)

    # Save to CSV
    checker_header = [
        "Timestamp",
        "GeneratedSolutions",
        "Status",
        "Vivado_Execution_sec",
        "Coverage",
        "Error_type",
        "Tokens_Used"
    ]

    content_csv = [
        timestamp,
        generated_solutions,
        status.value,
        exec_time,
        coverage_val,
        error_summary,
        tokens
    ]

    save_to_csv(content_csv, csv_path, header=checker_header)
