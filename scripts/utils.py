import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

#create or load index
def get_index(data_dir: str, storage_dir: str, index_name: str):
    """
    Verify the directories, read documents and create the index. If the index exist, it will be loaded
    """
    try:
        print(f"Loading existing {index_name} from '{storage_dir}.'")
        storage_context=StorageContext.from_defaults(persist_dir=storage_dir)
        index=load_index_from_storage(storage_context)
        print(f"Successfully loaded {index_name}!")
        return index
    
    except(FileNotFoundError, ValueError):
        #storage_dir does not exists
        print(f"Storage not found. Creating {index_name} from '{storage_dir}'")

        try:
            #read documents
            documents = SimpleDirectoryReader(input_dir=data_dir).load_data()

            # transform documents in indexes
            index = VectorStoreIndex.from_documents(documents)

            #save the index
            index.storage_context.persist(persist_dir=storage_dir)
            print(f"{index_name} created and saved in '{storage_dir}'")
            return index
        
        except ValueError as e:
            #directory does not exists or is empty
            print(f"Error: The '{data_dir}' folder does not exists or is empty!")
            print(f"Detailed LlamIndex error : {e}")
            return None

        except Exception as e:
            #any other error catched
            print(f"An unexpected error occurred while created {index_name}: {e}")
            return None

