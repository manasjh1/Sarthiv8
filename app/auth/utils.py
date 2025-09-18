import logging
import re
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import User
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db
import uuid
from config import AppConfig
import logging

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
        "chat_id": str(chat_id),  
        "exp": expire,
        "iat": datetime.utcnow()
    }
    if invite_id:
        to_encode["invite_id"] = invite_id
    
    return jwt.encode(to_encode, config.llm.jwt_secret_key, algorithm=config.llm.jwt_algorithm)

def should_refresh_token(exp_timestamp: int, threshold_hours: int = None) -> bool:
    """Check if token should be refreshed based on remaining time.
    """
    if threshold_hours is None:
        threshold_hours = config.llm.jwt_expiration_hours // 2
    
    current_time = datetime.utcnow()
    exp_time = datetime.utcfromtimestamp(exp_timestamp)
    time_remaining = exp_time - current_time
    
    return time_remaining < timedelta(hours=threshold_hours) 

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return a dictionary with user_id and chat_id"""
    try:
        payload = jwt.decode(
            credentials.credentials, 
            config.llm.jwt_secret_key, 
            algorithms=[config.llm.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        chat_id: str = payload.get("chat_id")
        exp_timestamp: int = payload.get("exp")

        if user_id is None or chat_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: missing user or chat ID"
            )
            
        try:
            user_uuid = uuid.UUID(user_id)
            chat_uuid = uuid.UUID(chat_id)
        except (ValueError, TypeError) as e:
            logging.error(f"UUID parsing failed - user_id: '{user_id}', chat_id: '{chat_id}', error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: malformed user or chat ID"
            )
            
        token_data = {"user_id": user_uuid, "chat_id": chat_uuid}
        
        if exp_timestamp and should_refresh_token(exp_timestamp):
            token_data["_should_refresh"] = True
            token_data["_invite_id"] = payload.get("invite_id")
    
        return token_data
    
    except JWTError as e:
        logging.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except (ValueError, TypeError):
        raise 
    except Exception as e:
        logging.error(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed")

def get_current_user(
    token_data: dict = Depends(verify_token),
    response: Response = None,
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database and auto-refresh token if needed"""
    user = db.query(User).filter(User.user_id == token_data["user_id"], User.status == 1).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    if token_data.get("_should_refresh") and response: 
        chat = user.chat
        if chat:
           new_token = create_access_token(
               str(user.user_id),
               str(chat.chat_id),
               token_data.get("_invite_id")
           )
           response.headers["X-New-Token"] = new_token
           logging.info(f"JWT token auto-refreshed for user {user.user_id}")
    
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