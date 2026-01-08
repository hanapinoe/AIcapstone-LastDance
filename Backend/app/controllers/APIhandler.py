from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Any, Dict, Optional, Callable, cast
import os
import time
import threading
import multiprocessing
from multiprocessing.queues import Queue as MPQueue
from dotenv import load_dotenv

from Backend.app.repositories.AIcapstoneDB import InteractDB

load_dotenv()

app = FastAPI()  # FastAPI instance

# Stop/cancel state
app.state.stop_event = threading.Event()
app.state._worker_lock = threading.Lock()
app.state._worker_process = None
app.state._worker_queue = None

# Configuration from environment variables
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
MAX_TRY = int(os.getenv("RAG_MAX_TRY", "10"))
SEED = os.getenv("RAG_SEED")
try:
    SEED = int(SEED) if SEED not in (None, "") else None
except (ValueError, TypeError):
    SEED = None


class UserInfo(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


class RecommendRequest(BaseModel):
    user_id: Optional[int] = None
    user: Optional[UserInfo] = None
    query: str


class RecommendResponse(BaseModel):
    request_id: Optional[int]
    recommendation_id: Optional[int]
    extracted_fields: Dict[str, Any]
    chosen: Optional[Dict[str, Any]]
    recommended_options: Dict[str, Any]
    reason: Optional[str] = None


class HistoryRequest(BaseModel):
    user_id: int


def validate_query(q: str):
    if not isinstance(q, str) or not q.strip():
        raise HTTPException(status_code=400, detail="You must enter a query!")
    if app.state.stop_event.is_set():
        raise HTTPException(
            status_code=503, detail="The system is currently stopped. Please try again later.")


def _recommend_pipeline(req_payload: Dict[str, Any], out_q: MPQueue) -> None:
    """Run the heavy recommend pipeline in a separate process.

    This makes it possible for /stop to terminate the in-flight work.
    The result is posted back to the parent via `out_q`.
    """

    try:
        # Import inside the child process to avoid pickling issues.
        from Backend.app.repositories.AIcapstoneDB import InteractDB
        from Backend.app.services.system_running import infoAgentService, rcmAgentService
        from fastapi import HTTPException

        vector_db_path = os.getenv("VECTOR_DB_PATH")
        max_try = int(os.getenv("RAG_MAX_TRY", "10"))
        seed_raw = os.getenv("RAG_SEED")

        seed_value = None
        if seed_raw not in (None, ""):
            try:
                seed_value = int(seed_raw)
            except (ValueError, TypeError):
                seed_value = None

        query = req_payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(
                status_code=400, detail="You must enter a query!")
        if not vector_db_path:
            raise HTTPException(
                status_code=500, detail="VECTOR_DB_PATH is not set")

        db = InteractDB()

        # Resolve user_id
        user_id = req_payload.get("user_id")
        if user_id is not None:
            if not db.user_exists(user_id):
                raise HTTPException(
                    status_code=400, detail="user_id does not exist in users table")
        else:
            user = req_payload.get("user")
            if not isinstance(user, dict) or not user.get("username") or not user.get("email"):
                raise HTTPException(
                    status_code=400, detail="user_id or user{username,email} required")
            user_id = db.get_or_create_user(user["username"], user["email"])
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="Username or Email already exists but does not match the same account",
                )

        agent = infoAgentService(userQuery=query, vectorDB_path=vector_db_path)
        filtered, fields = agent.query_with_llm_and_rag()

        picker = cast(Optional[Callable[..., Any]], getattr(
            agent, "pick_random_node_that_llm_can_choose", None))
        if not callable(picker):
            raise HTTPException(
                status_code=500,
                detail="infoAgentService does not implement pick_random_node_that_llm_can_choose",
            )

        hit, option_result = picker(
            filtered_nodes=filtered,
            fields=fields,
            max_try=max_try,
            seed=seed_value,
        )

        # 1) insert requests
        request_id = db.insert_data(
            "requests",
            {
                "user_id": user_id,
                "original_query": query,
                "extracted_fields": fields,
            },
        )
        if request_id is False:
            raise HTTPException(
                status_code=500, detail="Insert requests failed")

        # 2) insert recommendations (real mode)
        recommendation_id: Optional[int] = None
        chosen_payload: Optional[Dict[str, Any]] = None
        rec_opts: Dict[str, Any] = {}
        reason: Optional[str] = None

        if hit is not None:
            meta = agent._get_metadata(hit)
            score = agent._get_score(hit)
            option_dict = agent._parse_option_json(meta.get("option_json"))

            dish_name = meta.get("name")
            if not isinstance(dish_name, str) or not dish_name.strip():
                raise HTTPException(
                    status_code=500, detail="Recommended item missing name")

            dish_type = meta.get("type")
            if not isinstance(dish_type, str) or not dish_type.strip():
                raise HTTPException(
                    status_code=500, detail="Recommended item missing type")

            if isinstance(option_result, dict):
                maybe_opts = option_result.get("recommended_options")
                if isinstance(maybe_opts, dict):
                    rec_opts = maybe_opts
                else:
                    rec_opts = option_result if all(isinstance(
                        k, str) for k in option_result.keys()) else {}

            chosen_payload = {
                "name": dish_name,
                "type": meta.get("type"),
                "ingredient": meta.get("ingredient"),
                "description": meta.get("description"),
                "health_profile": meta.get("health_profile"),
                "context_suitability": meta.get("context_suitability"),
                "option_json": option_dict,
                "score": score,
            }

            if isinstance(rec_opts, dict) and len(rec_opts) > 0:
                # Generate explanation via rcmAgent (LoRA) using the real user query.
                try:
                    reason = rcmAgentService().explain_recommendation(
                        query, dish_name, dish_type, rec_opts)
                except Exception:
                    reason = None

                recommendation_id = db.insert_data(
                    "recommendations",
                    {
                        "request_id": request_id,
                        "dish_name": dish_name,
                        "dish_type": meta.get("type"),
                        "ingredient": meta.get("ingredient"),
                        "option_json": option_dict,
                        "recommended_options": rec_opts,
                        "score": score,
                        "explaination": reason,
                    },
                )
                if recommendation_id is False:
                    raise HTTPException(
                        status_code=500, detail="Insert recommendations failed")

        out_q.put(
            {
                "ok": True,
                "data": {
                    "request_id": request_id,
                    "recommendation_id": recommendation_id,
                    "extracted_fields": fields,
                    "chosen": chosen_payload,
                    "recommended_options": rec_opts,
                    "reason": reason,
                },
            }
        )
    except Exception as exc:
        status_code = 500
        detail: Any = str(exc)
        try:
            # If it's a FastAPI HTTPException, preserve its status/detail.
            if hasattr(exc, "status_code") and hasattr(exc, "detail"):
                status_code = int(getattr(exc, "status_code"))
                detail = getattr(exc, "detail")
        except Exception:
            pass

        out_q.put({"ok": False, "error": {
                  "status_code": status_code, "detail": detail}})


def _terminate_worker_if_running() -> None:
    with app.state._worker_lock:
        proc = app.state._worker_process
        if proc is not None and proc.is_alive():
            try:
                proc.terminate()
                proc.join(timeout=2)
            except Exception:
                pass
        app.state._worker_process = None
        app.state._worker_queue = None


def resolve_user_id_or_400(db: InteractDB, req: RecommendRequest) -> int:
    # Case 1: user_id passed directly
    if req.user_id is not None:
        if not db.user_exists(req.user_id):
            raise HTTPException(
                status_code=400, detail="user_id does not exist in users table")
        return req.user_id

    # Case 2: pass user {username,email} => get_or_create
    if req.user is not None:
        if not req.user.username or not req.user.email:
            raise HTTPException(
                status_code=400, detail="user.username and user.email are required")
        user_id = db.get_or_create_user(req.user.username, req.user.email)
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Username or Email already exists but does not match the same account",
            )
        return user_id

    # Case 3: nothing provided => incorrect login->request->recommend flow
    raise HTTPException(
        status_code=400, detail="user_id or user{username,email} required")


@app.post("/register")
def register(user: UserInfo):
    if not user.username or not user.email:
        raise HTTPException(
            status_code=400, detail="username and email are required")
    if "@" not in user.email or "." not in user.email:
        raise HTTPException(status_code=400, detail="invalid email")
    db = InteractDB()

    if db.get_user_id_by_username(user.username):
        raise HTTPException(
            status_code=400, detail="Username already exists, please choose a different username")

    if db.get_user_id_by_email(user.email):
        raise HTTPException(
            status_code=400, detail="Email already exists, please choose a different email")

    # Check if user already exists
    if db.get_user_id(user.username, user.email):
        raise HTTPException(
            status_code=400, detail="Account already exists, please provide different information")
    user_id = db.get_or_create_user(user.username, user.email)
    if not user_id:
        raise HTTPException(status_code=500, detail="Insert users failed")
    return {"user_id": user_id}


@app.post("/login")
def login(user: UserInfo):
    if not user.username or not user.email:
        raise HTTPException(
            status_code=400, detail="username và email là bắt buộc")
    db = InteractDB()

    verify_user_id = db.get_user_id(user.username, user.email)
    if not verify_user_id:
        raise HTTPException(
            status_code=400, detail="No user found with the given username and email")
    return {"user_id": verify_user_id}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    validate_query(req.query)

    if not VECTOR_DB_PATH:
        raise HTTPException(
            status_code=500, detail="VECTOR_DB_PATH is not set")

    db = InteractDB()
    user_id = resolve_user_id_or_400(db, req)

    # Run the heavy pipeline in a separate process so /stop can terminate it.
    with app.state._worker_lock:
        proc = app.state._worker_process
        if proc is not None and proc.is_alive():
            raise HTTPException(
                status_code=409, detail="Another recommendation is currently running")

        ctx = multiprocessing.get_context("spawn")
        out_q = ctx.Queue()
        req_payload: Dict[str, Any] = {
            "user_id": user_id,
            "user": req.user.model_dump() if req.user is not None else None,
            "query": req.query,
        }
        proc = ctx.Process(target=_recommend_pipeline,
                           args=(req_payload, out_q), daemon=True)
        app.state._worker_queue = out_q
        app.state._worker_process = proc
        proc.start()

    deadline = time.monotonic() + 300
    while True:
        if app.state.stop_event.is_set():
            _terminate_worker_if_running()
            raise HTTPException(status_code=503, detail="Stopped by user")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_worker_if_running()
            raise HTTPException(
                status_code=504, detail="Recommendation timed out")

        try:
            msg = app.state._worker_queue.get(timeout=min(0.25, remaining))
        except Exception:
            # keep polling so stop can be processed quickly
            continue

        # Finalize worker state
        _terminate_worker_if_running()

        if not isinstance(msg, dict) or msg.get("ok") is not True:
            err = (msg or {}).get("error") if isinstance(msg, dict) else None
            if isinstance(err, dict):
                raise HTTPException(status_code=int(
                    err.get("status_code", 500)), detail=err.get("detail"))
            raise HTTPException(
                status_code=500, detail="Unknown recommendation error")

        data = msg.get("data")
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=500, detail="Invalid recommendation result")

        return RecommendResponse(**data)


@app.post("/history_user")
def history_user(req: HistoryRequest):
    db = InteractDB()
    if not db.user_exists(req.user_id):
        raise HTTPException(
            status_code=400, detail="user_id does not exist in users table")
    return {"data": db.get_user_history(req.user_id)}


@app.post("/stop", status_code=204)
def stop():
    app.state.stop_event.set()
    _terminate_worker_if_running()
    return Response(status_code=204)


@app.post("/resume", status_code=204)
def resume():
    app.state.stop_event.clear()
    return Response(status_code=204)
