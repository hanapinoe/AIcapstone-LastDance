import os
import sys
import modal
import json
import ast

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

app = modal.App("capstone-llm-gateway")

hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

image = (
    modal.Image.from_registry(
        "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime",
        add_python="3.11",
    )
    .pip_install("fastapi", "pydantic", "transformers", "peft", "accelerate")
    .add_local_dir(
        "Backend",
        remote_path="/root/Backend",
        # Don't upload huge local HF cache snapshots; keep small adapter folders like Qwen3-8B-LoRA.
        ignore=["app/models/models--*/**", "**/__pycache__/**"]
    )
)


class Req(BaseModel):
    task_type: str
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    max_new_tokens: int = 256
    temperature: float = 0.0
    do_sample: bool = False


@app.cls(
    gpu="H100",
    image=image,
    timeout=60 * 10,
    volumes={"/models": hf_cache},
    secrets=[modal.Secret.from_name("capstone-secret")],
)
class Worker:
    @modal.enter()
    def warmup(self):
        os.environ["DEVICE"] = "cuda"
        # Must be set BEFORE importing model_utils (it reads env at import time)
        os.environ.setdefault("HF_CACHE_DIR", "/models")
        sys.path.insert(0, "/root")  # để import Backend...

        # Import sau khi sys.path ok
        from Backend.app.utils.model_utils import llmInitialize

        # Normalize MODEL_NAME mapping for Modal runtime.
        # Your local .env uses paths like "Backend/app/models/..." but inside Modal we mount to /root/Backend.
        raw = os.getenv("MODEL_NAME")
        mapping: Dict[str, Any] = {}
        if isinstance(raw, str) and raw.strip():
            try:
                obj = json.loads(raw)
                mapping = obj if isinstance(obj, dict) else {}
            except Exception:
                try:
                    obj = ast.literal_eval(raw)
                    mapping = obj if isinstance(obj, dict) else {}
                except Exception:
                    mapping = {}

        if mapping and os.path.isdir("/root/Backend"):
            updated = dict(mapping)
            for k, v in mapping.items():
                if isinstance(v, str) and v.startswith("Backend/"):
                    candidate = "/root/" + v
                    if os.path.exists(candidate):
                        updated[k] = candidate
            if updated != mapping:
                os.environ["MODEL_NAME"] = json.dumps(
                    updated, ensure_ascii=False)
                raw = os.environ["MODEL_NAME"]

        # Ensure loader uses the (possibly normalized) mapping from env/secret
        llmInitialize.configure(raw)

    @modal.method()
    def generate(self, req_dict: Dict[str, Any]) -> str:
        from Backend.app.utils.llm_gateway import generate_text
        return generate_text(
            task_type=req_dict["task_type"],
            prompt=req_dict.get("prompt"),
            messages=req_dict.get("messages"),
            max_new_tokens=int(req_dict.get("max_new_tokens", 256)),
            temperature=float(req_dict.get("temperature", 0.0)),
            do_sample=bool(req_dict.get("do_sample", False)),
            # Prevent recursion if MODAL_LLM_URL is set in the Modal environment.
            allow_remote=False,
        )


@app.function(image=image)
@modal.asgi_app()
def api():
    web = FastAPI()
    worker = Worker()

    @web.post("/generate")
    async def generate(req: Req):
        text = worker.generate.remote(req.model_dump())
        return {"text": text}

    return web