import datetime
import os
import csv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage


# function for saving metrics in csv
def save_to_csv(data_row, path, header=None):
    """
    Save one row to a CSV file.
    If the file does not exist and a header is provided, write the header first.
    """
    file_exists = os.path.exists(path)

    with open(path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists and header is not None:
            writer.writerow(header)

        writer.writerow(data_row)

#function for saving error status in txt
def save_to_file(content, path):
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
    Save per-agent experimental metrics.
    This replaces the old idea of relying only on iteration-based metrics.
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

#create or load index
def get_index(data_dir: str, storage_dir: str, index_name: str):
    """
    Verify the directories, read documents and create the index. If the index exist, it will be loaded
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

        # Save index for future runs
        os.makedirs(storage_dir, exist_ok=True)
        index.storage_context.persist(persist_dir=storage_dir)
        return index
    except Exception as e:
        print(f"[INDEXER ERROR]: Critical failure creating '{index_name}': {e}")
        return None