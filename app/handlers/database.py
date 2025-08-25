# app/handlers/database.py
from sqlalchemy.orm import Session
from app.models import Reflection, Message, Chat, User
import uuid
from typing import Optional

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
    reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
    if reflection:
        reflection.current_stage = next_stage
        db.commit()

def save_message(db: Session, reflection_id: uuid.UUID, message: str, sender: int, stage_no: int, is_distress: bool = False):
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

def get_previous_stage(db: Session, reflection_id: uuid.UUID, steps: int) -> int:
    message = db.query(Message.current_stage).filter(Message.reflection_id == reflection_id).order_by(Message.created_at.desc()).offset(steps).first()
    return message.current_stage if message else 0