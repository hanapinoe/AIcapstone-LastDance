from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os
import json
from dotenv import load_dotenv

from Backend.app.services.system_running import infoAgentService
from Backend.app.repositories.AIcapstoneDB import InteractDB

load_dotenv()

app = FastAPI()  # FastAPI instance

# Configuration from environment variables
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
TOP_K = int(os.getenv("RAG_TOP_K", "5"))
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


class HistoryRequest(BaseModel):
    user_id: int


def validate_query(q: str):
    if not isinstance(q, str) or not q.strip():
        raise HTTPException(status_code=400, detail="You must enter a query!")


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

    agent = infoAgentService(userQuery=req.query, vectorDB_path=VECTOR_DB_PATH)
    filtered, fields = agent.query_with_llm_and_rag(top_k=TOP_K)

    seed_value = None
    if isinstance(SEED, int):
        seed_value = SEED
    elif isinstance(SEED, str) and SEED.strip() != "":
        try:
            seed_value = int(SEED)
        except ValueError:
            seed_value = None

    hit, option_result = agent.pick_random_node_that_llm_can_choose(
        filtered_nodes=filtered,
        fields=fields,
        max_try=MAX_TRY,
        seed=seed_value,
    )

    # 1) insert requests
    request_id = db.insert_data("requests", {
        "user_id": user_id,
        "original_query": req.query,
        "extracted_fields": fields,
    })
    if request_id is False:
        raise HTTPException(status_code=500, detail="Insert requests failed")
    

    # 2) insert recommendations (real mode)
    recommendation_id: Optional[int] = None
    chosen_payload: Optional[Dict[str, Any]] = None
    rec_opts: Dict[str, Any] = {}

    if hit is not None:
        meta = agent._get_metadata(hit)
        score = agent._get_score(hit)
        option_dict = agent._parse_option_json(meta.get("option_json"))

        # Normalize LLM output
        if isinstance(option_result, dict):
            maybe_opts = option_result.get("recommended_options")
            if isinstance(maybe_opts, dict):
                rec_opts = maybe_opts
            else:
                rec_opts = option_result if all(isinstance(
                    k, str) for k in option_result.keys()) else {}

        chosen_payload = {
            "name": meta.get("name"),
            "type": meta.get("type"),
            "ingredient": meta.get("ingredient"),
            "description": meta.get("description"),
            "health_profile": meta.get("health_profile"),
            "context_suitability": meta.get("context_suitability"),
            "option_json": option_dict,
            "score": score,
        }

        # Only persist a recommendation if we actually got some recommended options.
        if isinstance(rec_opts, dict) and len(rec_opts) > 0:
            recommendation_id = db.insert_data(
                "recommendations",
                {
                    "request_id": request_id,
                    "dish_name": meta.get("name"),
                    "dish_type": meta.get("type"),
                    "ingredient": meta.get("ingredient"),
                    "option_json": option_dict,
                    "recommended_options": rec_opts,
                    "score": score,
                    "explaination": option_result.get("explaination") if isinstance(option_result, dict) else None,
                },
            )
            if recommendation_id is False:
                raise HTTPException(
                    status_code=500, detail="Insert recommendations failed")
            
    return RecommendResponse(
        request_id=request_id,
        recommendation_id=recommendation_id,
        extracted_fields=fields,
        chosen=chosen_payload,
        recommended_options=rec_opts,
    )


@app.post("/history_user")
def history_user(req: HistoryRequest):
    db = InteractDB()
    if not db.user_exists(req.user_id):
        raise HTTPException(
            status_code=400, detail="user_id does not exist in users table")
    return {"data": db.get_user_history(req.user_id)}
