import os
import re
import json
import ast
from typing import Any, Dict
import threading
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    # Optional dependency. In some runtimes (e.g., Modal), we rely on real env vars/secrets.
    pass

CACHE_DIR = os.getenv("HF_CACHE_DIR")
MODEL_NAME = os.getenv("MODEL_NAME")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME")
DEVICE = (os.getenv("DEVICE") or "cpu").strip().lower()


def _has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _pick_devices():
    want_gpu = DEVICE in ("gpu", "cuda", "cuda:0", "auto")
    has_cuda = _has_cuda()
    if want_gpu and has_cuda:
        return "cuda:0", "cuda:0"
    return None, "cpu"  # LLM device_map=None => run by CPU


def _load_LoRA_adapters(lora_path: str):
    # Prefer PEFT config so we always load the correct base model.
    peft_cfg = PeftConfig.from_pretrained(lora_path)
    base_model_name = peft_cfg.base_model_name_or_path
    if not isinstance(base_model_name, str) or not base_model_name.strip():
        # Fallback: infer from folder name if config is missing.
        lora_name = os.path.basename(lora_path)
        base_model_name = re.sub(
            r"[-_]?lora(?:.*)$", "", lora_name, flags=re.IGNORECASE)

    device_map = "auto" if _has_cuda() else None

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        trust_remote_code=True,
        cache_dir=CACHE_DIR,
        device_map=device_map,
        dtype="auto",
    )
    model = PeftModel.from_pretrained(
        base_model,
        lora_path,
        device_map=device_map,
    )
    return model, base_model_name


def _parse_model_ref(value: str) -> Dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    s = value.strip()
    # Try JSON first (recommended), then fall back to python-literal for legacy values.
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    try:
        obj = ast.literal_eval(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


class llmInitialize:
    _modelName_ref = MODEL_NAME
    _cached_by_task: Dict[str, tuple] = {}
    _lock = threading.Lock()

    @classmethod
    def configure(cls, _modelName_ref):
        cls._modelName_ref = _modelName_ref

    @classmethod
    def initialize_LLM(cls, task_type: str) -> tuple:
        """
        Initializes and returns the LLM model and tokenizer.
        Args:
            task_type (str): The type of task for which the model is being initialized.
        Returns:
            tuple: A tuple containing the model and tokenizer.
        """
        mapping = _parse_model_ref(
            cls._modelName_ref) if cls._modelName_ref else {}
        model_path = mapping.get(task_type)

        if task_type == "parsing":
            is_lora = False
        elif task_type == "rcm":
            is_lora = True
        else:
            return None, None

        if not isinstance(model_path, str) or not model_path.strip():
            return None, None

        cached = cls._cached_by_task.get(task_type)
        if isinstance(cached, tuple) and len(cached) == 2:
            return cached

        with cls._lock:
            cached = cls._cached_by_task.get(task_type)
            if isinstance(cached, tuple) and len(cached) == 2:
                return cached

            llm_device_map, _ = _pick_devices()

            if is_lora:
                # For LoRA adapters, the adapter folder usually does NOT include a tokenizer.
                # Load tokenizer from the base model referenced by the PEFT config.
                peft_cfg = PeftConfig.from_pretrained(model_path)
                base_model_name = peft_cfg.base_model_name_or_path
                tokenizer = AutoTokenizer.from_pretrained(
                    base_model_name,
                    trust_remote_code=True,
                    cache_dir=CACHE_DIR,
                )
                model, _ = _load_LoRA_adapters(model_path)
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    trust_remote_code=True,
                    cache_dir=CACHE_DIR,
                )
                kwargs = dict(
                    trust_remote_code=True,
                    cache_dir=CACHE_DIR,
                    dtype="auto",
                )
                if llm_device_map is not None:
                    kwargs["device_map"] = llm_device_map
                model = AutoModelForCausalLM.from_pretrained(
                    model_path, **kwargs)

            cls._cached_by_task[task_type] = (model, tokenizer)
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

        # Lazy import so LLM-only deployments (e.g., Modal GPU gateway) don't require llama_index.
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        _, embed_device = _pick_devices()

        embed_model = HuggingFaceEmbedding(
            model_name=cls._embedModelName,
            cache_folder=cls._cacheFolder,
            device=embed_device,
        )
        return embed_model
