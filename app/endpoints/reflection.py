# app/endpoints/reflection.py - SIMPLIFIED VERSION

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.utils import get_current_user
from app.models import User, Reflection, Chat, Message
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/reflection", tags=["reflection-history"])

@router.get("/inbox")
async def inbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gets reflections received by the current user - ONLY SUMMARY."""
    try:
        # Get reflections received by this user
        received_reflections = db.query(Reflection).filter(
            Reflection.receiver_user_id == current_user.user_id,
            Reflection.is_delivered == 1  # Only delivered reflections
        ).order_by(Reflection.created_at.desc()).all()
        
        data = []
        for reflection in received_reflections:
            # Get the sender information
            sender_chat = db.query(Chat).filter(Chat.chat_id == reflection.chat_id).first()
            sender_user = db.query(User).filter(User.user_id == sender_chat.user_id).first() if sender_chat else None
            
            # Determine sender name
            if reflection.is_anonymous:
                sender_display_name = "Anonymous"
            elif reflection.sender_name:
                sender_display_name = reflection.sender_name
            elif sender_user and sender_user.name:
                sender_display_name = sender_user.name
            else:
                sender_display_name = "Anonymous"
            
            data.append({
                "reflection_id": str(reflection.reflection_id),
                "summary": reflection.summary or "No summary available",  # ONLY SUMMARY
                "from": sender_display_name,
                "created_at": reflection.created_at.isoformat() if reflection.created_at else None
            })
        
        return {
            "success": True, 
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch inbox: {str(e)}")

@router.get("/outbox")
async def outbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gets reflections sent by the current user."""
    try:
        # Get reflections sent by this user
        sent_reflections = db.query(Reflection).join(Chat).filter(
            Chat.user_id == current_user.user_id
        ).order_by(Reflection.created_at.desc()).all()
        
        status_map = {0: "In Progress", 1: "Delivered", 2: "Blocked", 3: "Completed"}
        
        data = []
        for reflection in sent_reflections:
            data.append({
                "reflection_id": str(reflection.reflection_id),
                "summary": reflection.summary or "No summary available",
                "to": reflection.receiver_name or "Unknown",
                "status": status_map.get(reflection.is_delivered, "Unknown"),
                "created_at": reflection.created_at.isoformat() if reflection.created_at else None
            })
        
        return {
            "success": True,
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch outbox: {str(e)}")

@router.get("/history")
async def history(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(2, ge=1, le=10)  # Default 2 reflections per page, max 10
):
    """
    Gets history of ONLY sent reflections with FULL CHAT HISTORY.
    Shows your conversations with Sarthi - user messages AND system messages.
    Does NOT include reflections received from others.
    Pagination: loads 2 reflections by default, scroll to load more.
    """
    try:
        offset = (page - 1) * limit
        
        # Get ONLY sent reflections by this user (NOT received ones)
        sent_reflections = db.query(Reflection).join(Chat).filter(
            Chat.user_id == current_user.user_id
        ).order_by(Reflection.created_at.desc()).all()
        
        # Process sent reflections - INCLUDE FULL CHAT HISTORY
        all_reflections = []
        for reflection in sent_reflections:
            # Get ALL messages for this reflection (user + system)
            chat_messages = db.query(Message).filter(
                Message.reflection_id == reflection.reflection_id
            ).order_by(Message.created_at.asc()).all()
            
            # Convert messages to proper format
            chat_history = []
            for msg in chat_messages:
                chat_history.append({
                    "sender": "user" if msg.sender == 0 else "sarthi",
                    "message": msg.message,
                    "stage": msg.current_stage,
                    "is_distress": msg.is_distress,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                })
            
            reflection_data = {
                "reflection_id": str(reflection.reflection_id),
                "summary": reflection.summary or "No summary available",
                "to": reflection.receiver_name or "Unknown",
                "from": current_user.name or "You",
                "type": "sent",
                "status": {0: "In Progress", 1: "Delivered", 2: "Blocked", 3: "Completed"}.get(reflection.is_delivered, "Unknown"),
                "created_at": reflection.created_at.isoformat() if reflection.created_at else None,
                "chat_history": chat_history  # FULL CHAT INCLUDED
            }
            all_reflections.append(reflection_data)
        
        # Apply pagination
        paginated_reflections = all_reflections[offset:offset + limit]
        
        return {
            "success": True,
            "total": len(all_reflections),
            "page": page,
            "limit": limit,
            "has_more": (offset + limit) < len(all_reflections),  # For frontend scroll detection
            "data": paginated_reflections
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")