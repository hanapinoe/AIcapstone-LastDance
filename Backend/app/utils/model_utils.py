from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os
from dotenv import load_dotenv
import threading
from transformers import AutoModelForCausalLM, AutoTokenizer


load_dotenv()

CACHE_DIR = os.getenv("HF_CACHE_DIR")
MODEL_NAME = os.getenv("MODEL_NAME")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME")

class llmInitialize:
    _modelName = MODEL_NAME
    _cached_model = None
    _cached_tokenizer = None
    _lock = threading.Lock()

    @classmethod
    def configure(cls, _modelName):
        cls._modelName = _modelName

    @classmethod
    def initialize_LLM(cls) -> tuple:
        if cls._cached_model is not None and cls._cached_tokenizer is not None:
            return cls._cached_model, cls._cached_tokenizer

        if not cls._modelName:
            return None, None

        with cls._lock:
            if cls._cached_model is not None and cls._cached_tokenizer is not None:
                return cls._cached_model, cls._cached_tokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                cls._modelName,
                trust_remote_code=True,
                cache_dir=CACHE_DIR,
            )
            model = AutoModelForCausalLM.from_pretrained(
                cls._modelName,
                device_map="cuda:0",
                dtype="auto",
                trust_remote_code=True,
                cache_dir=CACHE_DIR,
            )
            cls._cached_model = model
            cls._cached_tokenizer = tokenizer
            return model, tokenizer


class embedInitialize:
    _embedModelName = EMBED_MODEL_NAME
    _cacheFolder = CACHE_DIR

    @classmethod
    def configure(cls, _embedModelName=None, _cacheFolder=None):
        if _embedModelName:
            cls._embedModelName = _embedModelName
        if _cacheFolder:
            cls._cacheFolder = _cacheFolder

    @classmethod
    def initialize_embedModel(cls):
        if not isinstance(cls._embedModelName, str) or not cls._embedModelName:
            raise ValueError("embedModelName must be a non-empty string")
        embed_model = HuggingFaceEmbedding(
            model_name=cls._embedModelName,
            cache_folder=cls._cacheFolder,
            device="cuda:0",
        )
        return embed_model
