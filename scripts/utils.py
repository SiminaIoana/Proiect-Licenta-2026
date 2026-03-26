import os
import re
import csv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

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
            print(f"[INDEXER]: Loading existing '{index_name}' from storage...")
            storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
            index = load_index_from_storage(storage_context)
            print(f"[INDEXER]: '{index_name}' loaded successfully!")
            return index
    except Exception as e:
        print(f"[INDEXER WARNING]: Failed to load '{index_name}' cache: {e}")

    try:
        print(f"[INDEXER]: Building new index for '{index_name}' from '{data_dir}'...")
        documents = SimpleDirectoryReader(input_dir=data_dir).load_data()
        index = VectorStoreIndex.from_documents(documents)

        # Save index for future runs
        os.makedirs(storage_dir, exist_ok=True)
        index.storage_context.persist(persist_dir=storage_dir)
        print(f"[INDEXER]: '{index_name}' saved to storage.")
        return index
    except Exception as e:
        print(f"[INDEXER ERROR]: Critical failure creating '{index_name}': {e}")
        return None


# function for extract SV code
def extract_code(original_code: str) -> str:
    generated_text = re.search(r"```systemverilog\n(.*?)```", original_code, re.DOTALL)
    if generated_text:
        return generated_text.group(1)
    else:
        return original_code
    
# function for saving the code on disk
def save_code(original_code: str, file_path:str) ->str:
    with open(file_path, 'w') as file:
        file.write(original_code)
    print(f"\nSystemVerilog code saved in {file_path}\n")

# function for saving metrics in csv
def save_to_csv(data_row , path):
    file_exists = os.path.exists(path)
    with open(path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Iteration", "Status", "Time_Execution_sec", "Coverage", "Error_type", "Tokens_Used"])
        writer.writerow(data_row)

#function for saving error status in txt
def save_to_file(content, path):
    with open(path, "a", encoding="utf-8") as file:
        file.write(content + "\n" + "="*50 + "\n\n")