import os
import json
from dotenv import load_dotenv

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings


try:
    with open("project_config.json", "r") as f:
        PROJECT_CONFIG = json.load(f)
except FileNotFoundError:
    print("WARNING: JSON PROJECT not found!")
    PROJECT_CONFIG = {}


VIVADO_BIN_PATH = r"C:\Xilinx\2025.2\Vivado\bin\xvlog.bat"


def initialize_llm():
    load_dotenv()

    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()

    if provider == "deepseek":
        llm = OpenAILike(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            api_base="https://api.deepseek.com",
            is_chat_model=True,
            temperature=0.2,
            max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "8000")),
            context_window=int(os.getenv("DEEPSEEK_CONTEXT_WINDOW", "64000")),
            timeout=float(os.getenv("DEEPSEEK_TIMEOUT", "300")),
            max_retries=1,
        )
    elif provider == "huggingface":
            llm = OpenAILike(
            model=os.getenv("HF_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct"),
            api_key=os.getenv("HF_TOKEN"),
            api_base="https://router.huggingface.co/v1",
            is_chat_model=True,
            temperature=0.2,
            max_tokens=int(os.getenv("HF_MAX_TOKENS", "4000")),
            context_window=int(os.getenv("HF_CONTEXT_WINDOW", "32768")),
            timeout=float(os.getenv("HF_TIMEOUT", "300")),
            max_retries=1,
        )
    elif provider == "ollama":
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")

        llm = OpenAILike(
            model=ollama_model,
            api_key="ollama",
            api_base="http://localhost:11434/v1",
            is_chat_model=True,
            temperature=0.2,
            max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "1000")),
            context_window=int(os.getenv("OLLAMA_CONTEXT_WINDOW", "4096")),

            # Timeout mai mare pentru că Ollama local răspunde mai greu.
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "300")),
            max_retries=1,
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")

    embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5"
    )

    Settings.llm = llm
    Settings.embed_model = embed_model

    print(f"[CONFIG] Loaded LLM provider: {provider}")

    if provider == "ollama":
        print(f"[CONFIG] Ollama model: {os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:3b')}")
        print(f"[CONFIG] Ollama context_window: {os.getenv('OLLAMA_CONTEXT_WINDOW', '4096')}")
        print(f"[CONFIG] Ollama max_tokens: {os.getenv('OLLAMA_MAX_TOKENS', '1000')}")

    return llm