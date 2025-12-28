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
 - Copy the example env and fill secrets locally or via CI secrets (see notes below): create a `.env.docker` from `.env.docker.example` and set `DB_PASSWORD`, `MODEL_NAME`, `HF_CACHE_DIR`, etc.
 - Build and run:
```bash
docker-compose up --build
```

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

## Models & PEFT LoRA
- LoRA adapters should be stored as folders (not zipped) under `Backend/app/models/` or a mounted HF cache directory.
- The app uses `peft.PeftConfig` to detect `base_model_name_or_path`, loads the base model, and attaches the adapter with `PeftModel.from_pretrained`.
- Ensure `peft` is present in your Docker/requirements files when using adapters.

## Environment variables
Put these in `.env.docker` (or your environment):
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `MODEL_NAME` — JSON mapping per task (example):
    `{"parsing":"Qwen/Qwen3-1.7B","rcm":"Backend/app/models/Qwen3-8B-LoRA"}`
- `HF_CACHE_DIR`, `VECTOR_DB_PATH`, `EMBED_MODEL_NAME`, `DEVICE`, `RAG_TOP_K`

## CI / Secrets guidance
- Do not commit secrets to the repository. Add a `.env.docker.example` with placeholders and add `.env.docker` to `.gitignore`.
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
If you want, I can also add `.env.docker.example` and update `.gitignore` to ignore `.env.docker`.