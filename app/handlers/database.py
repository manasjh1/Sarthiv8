# app/handlers/database.py (FIXED)
from sqlalchemy.orm import Session
from app.models import Reflection, Message, Chat, User
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging


def get_user_by_chat_id(db: Session, chat_id: uuid.UUID) -> Optional[User]:
    return db.query(User).join(Chat).filter(Chat.chat_id == chat_id).first()

def get_reflection_by_id(db: Session, reflection_id: uuid.UUID) -> Optional[Reflection]:
    return db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()

def get_latest_reflection_by_chat_id(db: Session, chat_id: uuid.UUID) -> Optional[Reflection]:
    return db.query(Reflection).filter(Reflection.chat_id == chat_id).order_by(Reflection.created_at.desc()).first()

def create_new_reflection(db: Session, chat_id: uuid.UUID) -> uuid.UUID:
    new_reflection = Reflection(chat_id=chat_id)
    db.add(new_reflection)
    db.commit()
    db.refresh(new_reflection)
    return new_reflection.reflection_id

def update_reflection_stage(db: Session, reflection_id: uuid.UUID, next_stage: int):
    """FIXED: Add validation to prevent NULL stage updates"""
    if next_stage is None:
        # Log the error but don't update - keep current stage
        import logging
        logging.error(f"Attempted to update reflection {reflection_id} with NULL stage")
        return
    
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.current_stage = next_stage
        db.commit()

def save_message(db: Session, reflection_id: uuid.UUID, message: str, sender: int, stage_no: int, is_distress: bool = False):
    """FIXED: Add validation to prevent NULL stage_no in messages"""
    # If stage_no is None, use the current reflection stage or default to 0
    if stage_no is None:
        reflection = get_reflection_by_id(db, reflection_id)
        stage_no = reflection.current_stage if reflection and reflection.current_stage is not None else 0
    
    message_record = Message(reflection_id=reflection_id, message=message, sender=sender, current_stage=stage_no, is_distress=is_distress)
    db.add(message_record)
    db.commit()

def get_last_user_message(db: Session, reflection_id: uuid.UUID) -> Optional[Message]:
    return db.query(Message).filter(Message.reflection_id == reflection_id, Message.sender == 0).order_by(Message.created_at.desc()).first()

def get_all_messages(db: Session, reflection_id: uuid.UUID) -> list[Message]:
    return db.query(Message).filter(Message.reflection_id == reflection_id).order_by(Message.created_at.asc()).all()

def update_reflection_status(db: Session, reflection_id: uuid.UUID, status: int):
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.is_delivered = status
        db.commit()

def update_reflection_flow_type(db: Session, reflection_id: uuid.UUID, flow_type: Optional[str]):
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.flow_type = flow_type
        db.commit()

def update_reflection_recipient(db: Session, reflection_id: uuid.UUID, name: str):
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.receiver_name = name
        db.commit()

def update_reflection_summary(db: Session, reflection_id: uuid.UUID, summary: str):
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.summary = summary
        db.commit()

def get_previous_stage(db: Session, reflection_id: uuid.UUID, steps: int) -> int:
    message = db.query(Message.current_stage).filter(Message.reflection_id == reflection_id).order_by(Message.created_at.desc()).offset(steps).first()
    return message.current_stage if message else 0


def save_user_choice_message(db: Session, reflection_id: uuid.UUID, choice_data: dict, stage_no: int):
    """
    Save user choice as a readable message - ONLY for specific flows
    
    Args:
        db: Database session
        reflection_id: Current reflection ID
        choice_data: The choice data from request.data[0]
        stage_no: Current stage number
    """
    try:
        # Convert choice data to readable message
        readable_message = format_choice_as_message(choice_data)
        
        if readable_message:
            message_record = Message(
                reflection_id=reflection_id, 
                message=readable_message, 
                sender=0,  # User message
                current_stage=stage_no,
                is_distress=False
            )
            db.add(message_record)
            db.commit()
            logging.info(f"✅ Saved user choice message: {readable_message}")
    except Exception as e:
        logging.error(f"Failed to save user choice message: {e}")

def format_choice_as_message(choice_data: dict) -> str:
    """
    Convert choice data to human-readable message - LIMITED SCOPE
    Only handles: initial flow, global intent, and venting sanctuary choices
    
    Args:
        choice_data: Choice data from request
        
    Returns:
        Human-readable message string
    """
    if not choice_data:
        return ""
    
    # Handle initial flow choices (continue/new reflection)
    if "choice" in choice_data and choice_data.get("choice") in ["0", "1"]:
        if "label" in choice_data:
            return f"Selected: {choice_data['label']}"
        else:
            # Add default labels for initial flow
            if choice_data["choice"] == "1":
                return "Selected: Continue previous conversation"
            elif choice_data["choice"] == "0":
                return "Selected: Start new conversation"
    
    # Handle global intent choices (stages 25, 26)
    if "choice" in choice_data:
        choice_value = choice_data["choice"]
        
        # Stage 25 (venting stop)
        if choice_value == "0" and "quit" in str(choice_data).lower():
            return "Selected: I want to quit for now"
        elif choice_value == "1" and "continue" in str(choice_data).lower():
            return "Selected: I want to continue"
        
        # Stage 26 (global intent options)
        elif choice_value == "1" and "feeling" in str(choice_data).lower():
            return "Selected: Let's talk about this new feeling"
        elif choice_value == "2" and "approach" in str(choice_data).lower():
            return "Selected: Let's try a different approach"
        elif choice_value == "3" and "back" in str(choice_data).lower():
            return "Selected: Can we go back?"
        
        # Generic choice with label
        if "label" in choice_data:
            return f"Selected: {choice_data['label']}"
    
    # Handle simple form inputs (names, etc.) - ONLY for initial/global flows
    if "name" in choice_data and len(choice_data) == 1:
        return f"My name is: {choice_data['name']}"
    
    # Exclude delivery-related choices
    if any(key in choice_data for key in ["delivery_mode", "reveal_name", "recipient_email", "recipient_phone"]):
        return ""  # Don't store delivery-related choices
    
    # Generic fallback for other choices
    return f"Made a selection: {choice_data.get('choice', 'unknown')}"
