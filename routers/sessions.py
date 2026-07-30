from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, Session as DBSession
from schemas import SessionSummary, SessionDetail
from auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[SessionSummary])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = (
        db.query(DBSession)
        .filter(DBSession.user_id == user.id)
        .order_by(DBSession.id.desc())
        .limit(50)
        .all()
    )
    return [
        SessionSummary(
            session_id=s.session_id,
            goal=s.goal,
            success=s.success,
            steps=s.steps,
            time=s.time,
            timestamp=s.timestamp,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(DBSession)
        .filter(
            DBSession.session_id == session_id,
            DBSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(
        session_id=session.session_id,
        goal=session.goal,
        success=session.success,
        steps=session.steps,
        time=session.time,
        timestamp=session.timestamp,
        final_answer=session.final_answer,
        log=session.log,
    )


@router.delete("/{session_id}")
def delete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(DBSession)
        .filter(
            DBSession.session_id == session_id,
            DBSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"detail": "Session deleted"}


@router.delete("")
def clear_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(DBSession).filter(DBSession.user_id == user.id).delete()
    db.commit()
    return {"detail": "All sessions cleared"}
