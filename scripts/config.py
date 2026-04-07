import os
from dotenv import load_dotenv
from llama_index.llms.groq import Groq
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings
import json

try:
    with open('project_config.json', 'r') as f:
        PROJECT_CONFIG = json.load(f)
except FileNotFoundError:
    print("WARNING: JSON PROJECT not found!")
    PROJECT_CONFIG = {}

VIVADO_BIN_PATH = r"C:\Xilinx\2025.2\Vivado\bin\xvlog.bat" 

# function for llm initializaton
def initialize_llm():
    # load environment variables
    load_dotenv()

    # initialize LLM
    #llm = Groq(model="llama-3.3-70b-versatile")
    llm = OpenAILike(
    model="deepseek-chat", 
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    api_base="https://api.deepseek.com",
    is_chat_model=True,
    temperature=0.2,
    max_tokens=8000,
    context_window=64000
)
    # initialize the embedding
    embed_model=HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # global settings
    Settings.llm=llm
    Settings.embed_model=embed_model

    return llm