from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, File
from auth import get_current_user

router = APIRouter()


@router.get("")
def list_files(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    files = (
        db.query(File)
        .filter(File.user_id == user.id)
        .order_by(File.filename)
        .all()
    )
    return [
        {"filename": f.filename, "size": len(f.content), "created_at": str(f.created_at or "")}
        for f in files
    ]


@router.get("/{filename:path}")
def get_file(filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = (
        db.query(File)
        .filter(File.filename == filename, File.user_id == user.id)
        .first()
    )
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": f.filename, "content": f.content, "size": len(f.content)}


@router.delete("/{filename:path}")
def delete_file(filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = (
        db.query(File)
        .filter(File.filename == filename, File.user_id == user.id)
        .first()
    )
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    db.delete(f)
    db.commit()
    return {"detail": "File deleted"}
