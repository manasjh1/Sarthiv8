# app/endpoints/reflection.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.utils import get_current_user
from app.models import User, Reflection, Chat

router = APIRouter(prefix="/reflection", tags=["reflection-history"])

@router.get("/inbox")
async def inbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gets reflections received by the current user."""
    reflections = db.query(Reflection).filter(
        Reflection.receiver_user_id == current_user.user_id,
        Reflection.is_delivered == 1
    ).order_by(Reflection.created_at.desc()).all()
    
    data = [{
        "reflection_id": str(r.reflection_id),
        "summary": r.summary,
        "from": r.sender_name if not r.is_anonymous else "Anonymous",
        "created_at": r.created_at.isoformat() if r.created_at else None
    } for r in reflections]
    
    return {"success": True, "data": data}

@router.get("/outbox")
async def outbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gets reflections sent by the current user."""
    reflections = db.query(Reflection).join(Chat).filter(
        Chat.user_id == current_user.user_id
    ).order_by(Reflection.created_at.desc()).all()
    
    status_map = {0: "In Progress", 1: "Delivered", 2: "Blocked"}
    data = [{
        "reflection_id": str(r.reflection_id),
        "summary": r.summary,
        "to": r.receiver_name,
        "status": status_map.get(r.is_delivered, "Unknown"),
        "created_at": r.created_at.isoformat() if r.created_at else None
    } for r in reflections]
    
    return {"success": True, "data": data}

@router.get("/history")
async def history(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(2, ge=1, le=100)
):
    """Gets a paginated history of reflection chats for the current user."""
    offset = (page - 1) * limit
    
    reflections = db.query(Reflection).join(Chat).filter(
        Chat.user_id == current_user.user_id
    ).order_by(Reflection.created_at.desc()).offset(offset).limit(limit).all()

    data = []
    status_map = {0: "In Progress", 1: "Delivered", 2: "Blocked"}
    for r in reflections:
        chat_history = [{
            "sender": msg.sender,
            "message": msg.message,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        } for msg in r.messages]

        data.append({
            "reflection_id": str(r.reflection_id),
            "summary": r.summary,
            "to": r.receiver_name,
            "status": status_map.get(r.is_delivered, "Unknown"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "chat_history": chat_history
        })

    return {"success": True, "data": data}