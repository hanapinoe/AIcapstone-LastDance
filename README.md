# AIcapstone-LastDance

## Overview
AIcapstone-LastDance is a recommendation system for food suggestions built with FastAPI (backend) and simple Python frontend utilities. It combines RAG (retrieval-augmented generation), a vector store, and PEFT LoRA adapters for model fine-tuning.

## Project Layout
```
Backend/
    app/
        controllers/       # FastAPI handlers
        services/          # Orchestration, infoAgent, rcmAgent
        utils/             # model loader, embeddings helper
        repositories/      # DB access
        models/            # optional local model/adapters
        data/              # vector DB persistence
        test/
Frontend/
    mainFE.py
    input_query.py
```

## Quick start (Local / Docker)

1. Clone the repo
```bash
git clone https://github.com/hanapinoe/AIcapstone-LastDance.git
cd AIcapstone-LastDance
```

2. Use Docker (recommended)
 - Create a local `.env.docker` (this file is gitignored) and set at least DB + model settings.
 - Build and run (starts MySQL + API):
```bash
docker-compose up --build
```

Notes for the current Docker flow:
- MySQL is exposed on host port `3307` (container `3306`).
- The API is exposed on `http://localhost:8000`.
- Compose mounts:
    - `./Backend/app/data/UserPreference_chroma_db_E5_base` -> `/data/chroma` (VECTOR DB persistence)
    - `./docker_data/hf_cache` -> `/models` (Hugging Face cache)
- Local docker volumes/cache live under `docker_data/` and should not be committed.

LLM execution flow (local vs Modal GPU):
- The backend uses `Backend/app/utils/llm_gateway.py`.
- If `MODAL_LLM_URL` is set, the backend will call the remote Modal gateway for both task types (`parsing` and `rcm`).
- If `MODAL_LLM_URL` is NOT set, the backend will run the models locally inside the container.
- This repo's Docker image is CPU-oriented by default (see `requirements.docker.cpu.txt`), so Modal is the recommended way to run GPU inference.

3. Run locally (without Docker)
 - Create a virtualenv and install dependencies:
```bash
python -m venv venv
venv/Scripts/activate    # Windows
pip install -r requirements.txt
```
 - Set environment variables (example shown in `.env.docker.example`) and run:
```bash
uvicorn Backend.app.controllers.APIhandler:app --host 0.0.0.0 --port 8000 --reload
```

API endpoints live in `Backend/app/controllers/APIhandler.py` (e.g., `/recommend`, `/register`, `/login`).

### Recommend request shape (current pipeline)
The `/recommend` endpoint supports either:
- `user_id` (existing user), or
- `user: {"username", "email"}` to auto-create/resolve a user.

Example:
```bash
curl -X POST http://localhost:8000/recommend \
    -H "Content-Type: application/json" \
    -d '{"user":{"username":"demo","email":"demo@example.com"},"query":"Tôi muốn món ăn ít dầu mỡ"}'
```

## Models & PEFT LoRA
- LoRA adapters should be stored as folders (not zipped) under `Backend/app/models/` or a mounted HF cache directory.
- The app uses `peft.PeftConfig` to detect `base_model_name_or_path`, loads the base model, and attaches the adapter with `PeftModel.from_pretrained`.
- Ensure `peft` is present in your Docker/requirements files when using adapters.

Docker caveat:
- The Docker build context ignores `Backend/app/models/**` via `.dockerignore`, so local adapters in that folder will NOT be copied into the image.
- For Docker runs, prefer setting `MODEL_NAME` to Hugging Face repo IDs, or mount your adapter directory into the container and point `MODEL_NAME` at the mounted path.

## Modal GPU gateway (optional, recommended for GPU)
This repo includes a small Modal ASGI app that exposes `/generate` and runs on GPU.

1. Install and login to Modal on your machine:
```bash
pip install modal
modal setup
```

2. Create a Modal secret (example name used in code: `capstone-secret`) that contains env vars like `MODEL_NAME` (and any HF tokens if needed).

3. Deploy the gateway:
```bash
modal deploy Backend/app/utils/modal_llm_setup.py
```

4. Take the deployed URL and set it in `.env.docker`:
- `MODAL_LLM_URL=.../generate` (must end with `/generate`)

When `MODAL_LLM_URL` is set, the backend container will automatically offload LLM calls to Modal GPU.

## Environment variables
Put these in `.env.docker` (or your environment). Minimal example:
```env
DB_HOST=db
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=AIcapstone

VECTOR_DB_PATH=/data/chroma
HF_CACHE_DIR=/models

# JSON mapping per task
MODEL_NAME={"parsing":"Qwen/Qwen3-1.7B","rcm":"Qwen/Qwen3-1.7B"}
EMBED_MODEL_NAME=intfloat/multilingual-e5-base

RAG_TOP_K=5
RAG_MAX_TRY=10
RAG_SEED=42
```

Full set used by the current services:
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `MODEL_NAME` — JSON mapping per task (example):
    `{"parsing":"Qwen/Qwen3-1.7B","rcm":"Backend/app/models/Qwen3-8B-LoRA"}`
- `HF_CACHE_DIR`, `VECTOR_DB_PATH`, `EMBED_MODEL_NAME`, `DEVICE`, `RAG_TOP_K`
- Optional (if using Modal gateway): `MODAL_LLM_URL` (must end with `/generate`)

## CI / Secrets guidance
- Do not commit secrets to the repository. Keep `.env.docker` local (already gitignored).
- Use your CI provider's secrets store (GitHub Actions Secrets, GitLab CI variables, etc.) and inject secrets at runtime.

## Developer notes
- Key files:
    - `Backend/app/utils/model_utils.py` — model & tokenizer loader (PEFT-aware)
    - `Backend/app/services/rcmAgent/explain.py` — explanation generation
    - `Backend/app/controllers/APIhandler.py` — API and worker pipeline
    - `Backend/app/services/system_running.py` — orchestration
- The recommend pipeline persists `reason` / `explaination` with recommendations in the DB.

## Troubleshooting
- If model loading fails, confirm adapter folder is present and `PeftConfig` includes `base_model_name_or_path`.
- If docker build fails due to missing packages, ensure `peft` is listed in `requirements.docker.*.txt`.

## Contributing
- Create a feature branch, run linters/tests, and open a PR. Example:
```bash
git checkout -b feature/rcm-explain
```

---
If you want, I can also add a `.env.docker.example` (no secrets) to the repo.