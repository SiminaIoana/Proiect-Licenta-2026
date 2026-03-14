import os
from dotenv import load_dotenv
from llama_index.llms.groq import Groq
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings

VIVADO_BIN_PATH = r"C:\Xilinx\2025.2\Vivado\bin\xvlog.bat" 

# function for llm initializaton
def initialize_llm():
    # load environment variables
    load_dotenv()

    # initialize LLM
    llm = Groq(model="llama-3.3-70b-versatile")
    # initialize the embedding
    embed_model=HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # global settings
    Settings.llm=llm
    Settings.embed_model=embed_model

    return llm