# app/auth/utils.py
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models import User
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db
import uuid
from config import AppConfig

config = AppConfig.from_env()
security = HTTPBearer()

class AuthUtils:
    """Utilities for authentication operations with consistent contact normalization"""
    
    def detect_channel(self, contact: str) -> str:
        """Detect channel based on contact format"""
        contact = contact.strip()
        
        if "@" in contact:
            return "email"
        else:
            return "whatsapp"
    
    def normalize_contact(self, contact: str, channel: str) -> str:
        """Normalize contact format CONSISTENTLY"""
        if not contact:
            return ""
        contact = contact.strip()
        if channel == "email":
            return contact.lower()
        elif channel == "whatsapp":
            clean_number = re.sub(r'\D', '', contact)
            return clean_number
        return contact.strip()
    
    def normalize_contact_auto(self, contact: str) -> str:
        """Auto-detect channel and normalize consistently"""
        channel = self.detect_channel(contact)
        return self.normalize_contact(contact, channel)
    
    def find_user_by_contact(self, contact: str, db: Session) -> Optional[User]:
        """Find user by email or phone with flexible matching"""
        normalized_contact = self.normalize_contact_auto(contact)
        user = None
        if "@" in normalized_contact:
            user = db.query(User).filter(User.email == normalized_contact, User.status == 1).first()
        else:
            if normalized_contact and normalized_contact.isdigit():
                try:
                    phone_number = int(normalized_contact)
                    user = db.query(User).filter(User.phone_number == phone_number, User.status == 1).first()
                except ValueError:
                    pass
        return user

def create_access_token(user_id: str, chat_id: str, invite_id: str = None) -> str:
    """Create JWT access token with user_id and chat_id"""
    expire = datetime.utcnow() + timedelta(hours=config.llm.jwt_expiration_hours)
    to_encode = {
        "sub": str(user_id),
        "chat_id": str(chat_id),  # <-- ADD chat_id to the token payload
        "exp": expire,
        "iat": datetime.utcnow()
    }
    if invite_id:
        to_encode["invite_id"] = invite_id
    
    return jwt.encode(to_encode, config.llm.jwt_secret_key, algorithm=config.llm.jwt_algorithm)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return a dictionary with user_id and chat_id"""
    try:
        payload = jwt.decode(
            credentials.credentials, 
            config.llm.jwt_secret_key, 
            algorithms=[config.llm.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        chat_id: str = payload.get("chat_id") # <-- EXTRACT chat_id from token

        if user_id is None or chat_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: missing user or chat ID"
            )
        # Return a dictionary containing both UUIDs
        return {"user_id": uuid.UUID(user_id), "chat_id": uuid.UUID(chat_id)}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID format in token")

def get_current_user(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database using the user_id from the verified token"""
    user = db.query(User).filter(User.user_id == token_data["user_id"], User.status == 1).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    return user

def create_invite_token(invite_id: str, invite_code: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode = {
        "invite_id": invite_id,
        "invite_code": invite_code,
        "type": "invite",
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(to_encode, config.llm.jwt_secret_key, algorithm=config.llm.jwt_algorithm)

def verify_invite_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, config.llm.jwt_secret_key, algorithms=[config.llm.jwt_algorithm])
        if payload.get("type") != "invite":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return {
            "invite_id": payload.get("invite_id"),
            "invite_code": payload.get("invite_code")
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired invite token")