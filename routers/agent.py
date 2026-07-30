import uuid
import time
import os
from pathlib import Path

import groq
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, Session as DBSession
from schemas import RunRequest, RunResponse, FollowUpRequest, FollowUpResponse
from auth import get_current_user
from src.agent import Agent
from src.memory import ConversationMemory
from src.session_store import SessionStore

router = APIRouter()

active_agents: dict[str, Agent] = {}
active_memories: dict[str, ConversationMemory] = {}


@router.post("/run", response_model=RunResponse)
def run_agent(req: RunRequest, user: User = Depends(get_current_user)):
    model = req.model or None
    agent = Agent(model=model, user_id=user.id)
    session_id = str(uuid.uuid4())

    start = time.time()
    try:
        result = agent.run(req.goal, max_steps=req.max_steps)
    except groq.RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit",
                "model": model or "default",
                "message": str(e),
            },
        )
    elapsed = round(time.time() - start, 2)

    result["time"] = elapsed
    result["goal"] = req.goal
    result["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

    db = next(get_db())
    db_session = DBSession(
        session_id=session_id,
        user_id=user.id,
        goal=req.goal,
        success=result["success"],
        steps=result["steps"],
        time=elapsed,
        timestamp=result["timestamp"],
        final_answer=result["final_answer"],
        log=result["log"],
    )
    db.add(db_session)
    db.commit()
    db.close()

    try:
        store = SessionStore()
        store.add_session({
            "goal": req.goal,
            "success": result["success"],
            "steps": result["steps"],
            "time": elapsed,
            "timestamp": result["timestamp"],
            "final_answer": result["final_answer"],
            "log": result["log"],
        }, user=user.username)
    except Exception:
        pass

    active_agents[session_id] = agent
    memory = getattr(agent, "_last_memory", None)
    if memory:
        active_memories[session_id] = memory

    return RunResponse(
        session_id=session_id,
        success=result["success"],
        final_answer=result["final_answer"],
        steps=result["steps"],
        time=elapsed,
        log=result["log"],
    )


@router.post("/followup", response_model=FollowUpResponse)
def follow_up(req: FollowUpRequest, user: User = Depends(get_current_user)):
    if req.session_id not in active_agents or req.session_id not in active_memories:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    agent = active_agents[req.session_id]
    memory = active_memories[req.session_id]

    try:
        result = agent.continue_run(memory, req.message, max_steps=req.max_steps)
    except groq.RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit",
                "model": "default",
                "message": str(e),
            },
        )

    db = next(get_db())
    db_session = (
        db.query(DBSession)
        .filter(DBSession.session_id == req.session_id)
        .first()
    )
    if db_session:
        db_session.final_answer = result["final_answer"]
        db_session.log = result["log"]
        db_session.steps = result["steps"]
        db.commit()
    db.close()

    try:
        store = SessionStore()
        session_data = {
            "goal": f"Follow-up: {req.message}",
            "success": result["success"],
            "steps": result["steps"],
            "time": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "final_answer": result["final_answer"],
            "log": result["log"],
        }
        store.add_session(session_data, user=user.username)
    except Exception:
        pass

    return FollowUpResponse(
        success=result["success"],
        final_answer=result["final_answer"],
        steps=result["steps"],
        log=result["log"],
    )
