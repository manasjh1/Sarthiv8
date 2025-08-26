# app/models.py
import uuid
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, BigInteger, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserTypeEnum(enum.Enum):
    user = 'user'
    admin = 'admin'

class User(Base):
    __tablename__ = 'users'
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(256))
    email = Column(String(256), unique=True)
    phone_number = Column(BigInteger)
    user_type = Column(Enum(UserTypeEnum), default=UserTypeEnum.user)
    proficiency_score = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(Integer, default=1)
    is_verified = Column(Boolean, default=False)
    is_anonymous = Column(Boolean)
    chat = relationship("Chat", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Chat(Base):
    __tablename__ = 'chat'
    chat_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="chat")
    reflections = relationship("Reflection", back_populates="chat", cascade="all, delete-orphan")

class PromptTable(Base):
    __tablename__ = 'prompt_table'
    prompt_id = Column(Integer, primary_key=True)
    flow_type = Column(String(100))
    stage_id = Column(Integer, unique=True, nullable=False)
    is_static = Column(Boolean, default=True)
    prompt_type = Column(Integer)
    prompt_name = Column(String(256), nullable=False)
    prompt = Column(Text)
    next_stage = Column(Integer, ForeignKey('prompt_table.stage_id', ondelete='SET NULL'))
    status = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Reflection(Base):
    __tablename__ = 'reflections'
    reflection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey('chat.chat_id', ondelete='CASCADE'), nullable=False)
    flow_type = Column(String(100))
    current_stage = Column(Integer, ForeignKey('prompt_table.stage_id', ondelete='SET NULL'), default=0, nullable=False)
    summary = Column(Text)
    receiver_user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='SET NULL'))
    receiver_name = Column(String(256))
    receiver_relationship = Column(String(256))
    context_summary = Column(Text)
    emotion = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_delivered = Column(Integer, default=0, nullable=False)
    chat = relationship("Chat", back_populates="reflections")
    messages = relationship("Message", back_populates="reflection", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = 'messages'
    msg_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    is_distress = Column(Boolean, default=False)
    reflection_id = Column(UUID(as_uuid=True), ForeignKey('reflections.reflection_id', ondelete='CASCADE'), nullable=False)
    current_stage = Column(Integer, ForeignKey('prompt_table.stage_id', ondelete='SET NULL'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reflection = relationship("Reflection", back_populates="messages")

class Feedback(Base):
    __tablename__ = 'feedback'
    feedback_no = Column(Integer, primary_key=True)
    feedback_name = Column(String(256), nullable=False)
    status = Column(Integer, default=1)

class InviteCode(Base):
    __tablename__ = "invite_codes"

    invite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invite_code = Column(String(64), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), unique=True, nullable=True)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('invite_code', name='uq_invite_code'),
        UniqueConstraint('user_id', name='uq_invite_user_id'),  
    )

class OTPToken(Base):
    __tablename__ = "otp_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    otp = Column(String(6), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())