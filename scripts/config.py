import os
import json
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

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
    elif provider == "gemini":
        llm = OpenAILike(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
            is_chat_model=True,
            temperature=0.2,
            max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "8192")),
            context_window=int(os.getenv("GEMINI_CONTEXT_WINDOW", "1048576")),
            timeout=float(os.getenv("GEMINI_TIMEOUT", "300")),
            max_retries=1,
        )
    elif provider == "mistral":
        mistral_api_key = os.getenv("MISTRAL_API_KEY")

        if not mistral_api_key:
            raise ValueError("Missing MISTRAL_API_KEY in .env")

        llm = OpenAILike(
            model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
            api_key=mistral_api_key,
            api_base="https://api.mistral.ai/v1",
            is_chat_model=True,
            temperature=0.2,
            max_tokens=int(os.getenv("MISTRAL_MAX_TOKENS", "8192")),
            context_window=int(os.getenv("MISTRAL_CONTEXT_WINDOW", "262144")),
            timeout=float(os.getenv("MISTRAL_TIMEOUT", "300")),
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

    if provider == "gemini":
        print(f"[CONFIG] Gemini model: {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}")
        print(f"[CONFIG] Gemini context_window: {os.getenv('GEMINI_CONTEXT_WINDOW', '1048576')}")
        print(f"[CONFIG] Gemini max_tokens: {os.getenv('GEMINI_MAX_TOKENS', '8192')}")

    if provider == "mistral":
        print(f"[CONFIG] Mistral model: {os.getenv('MISTRAL_MODEL', 'mistral-small-latest')}")
        print(f"[CONFIG] Mistral context_window: {os.getenv('MISTRAL_CONTEXT_WINDOW', '262144')}")
        print(f"[CONFIG] Mistral max_tokens: {os.getenv('MISTRAL_MAX_TOKENS', '8192')}")
        
    return llm