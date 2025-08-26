# app/auth/storage.py
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import OTPToken, InviteCode
import uuid

# In-memory storage for new users (both email and WhatsApp)
new_user_otps: Dict[str, Dict] = {}

class AuthStorage:
    """Handles OTP storage for both existing and new users (email and WhatsApp)"""
    
    def store_for_existing_user(self, user_id: uuid.UUID, otp: str, db: Session) -> bool:
        # ... (this function remains the same)
        try:
            existing_otp = db.query(OTPToken).filter(OTPToken.user_id == user_id).first()
            if existing_otp:
                time_since_creation = datetime.utcnow() - existing_otp.created_at
                if time_since_creation < timedelta(minutes=1):
                    return False
                db.delete(existing_otp)
                db.flush()
            
            otp_token = OTPToken(user_id=user_id, otp=otp, created_at=datetime.utcnow())
            db.add(otp_token)
            db.commit()
            logging.info(f"OTP stored in database for existing user {user_id}")
            return True
        except Exception as e:
            logging.error(f"Unexpected error storing OTP for user {user_id}: {str(e)}")
            db.rollback()
            return False
    
    def store_for_new_user(self, contact: str, otp: str) -> bool:
        # ... (this function remains the same)
        try:
            normalized_contact = self._normalize_contact(contact)
            if normalized_contact in new_user_otps:
                time_since_creation = datetime.utcnow() - new_user_otps[normalized_contact]['created_at']
                if time_since_creation < timedelta(minutes=1):
                    return False
            new_user_otps[normalized_contact] = {'otp': otp, 'created_at': datetime.utcnow()}
            logging.info(f"✅ OTP stored in memory for new user {normalized_contact}")
            return True
        except Exception as e:
            logging.error(f"Error storing OTP in memory for {contact}: {str(e)}")
            return False

    def verify_for_existing_user(self, user_id: uuid.UUID, otp: str, db: Session) -> Tuple[str, str]:
        """
        Verify OTP for existing user.
        Returns a status string: 'SUCCESS', 'INVALID', 'EXPIRED', or 'NOT_FOUND'.
        """
        try:
            otp = otp.strip()
            otp_token = db.query(OTPToken).filter(OTPToken.user_id == user_id).first()
            
            if not otp_token:
                return "NOT_FOUND", "No OTP found for this user. Please request one."
            
            if (datetime.utcnow() - otp_token.created_at) > timedelta(minutes=3):
                return "EXPIRED", "OTP has expired. Please request a new one."
            
            if otp_token.otp == otp:
                try:
                    db.delete(otp_token)
                    db.commit()
                    logging.info(f"OTP verified and deleted for existing user {user_id}")
                    return "SUCCESS", "OTP verified successfully."
                except SQLAlchemyError as e:
                    db.rollback()
                    logging.error(f"Failed to delete OTP for user {user_id}: {str(e)}")
                    return "DB_ERROR", "Could not process OTP verification."
            else:
                return "INVALID", "Invalid OTP provided."
                
        except Exception as e:
            logging.error(f"Error verifying OTP for user {user_id}: {str(e)}")
            return "ERROR", "An unexpected error occurred during verification."

    def verify_for_new_user(self, contact: str, otp: str) -> Tuple[bool, str]:
        # ... (this function remains the same)
        try:
            otp = otp.strip()
            normalized_contact = self._normalize_contact(contact)
            if normalized_contact not in new_user_otps:
                return False, "No OTP found for this contact"
            
            stored_otp_data = new_user_otps[normalized_contact]
            if (datetime.utcnow() - stored_otp_data['created_at']) > timedelta(minutes=3):
                return False, "OTP has expired. Please request a new one"
            
            if stored_otp_data['otp'] == otp:
                return True, "OTP verified successfully"
            else:
                return False, "Invalid OTP"
        except Exception as e:
            logging.error(f"Error verifying OTP for new user {contact}: {str(e)}")
            return False, "Verification failed"
    
    def transfer_to_database(self, contact: str, user_id: uuid.UUID, invite_id: str, db: Session) -> Tuple[bool, str]:
        # ... (this function remains the same)
        try:
            normalized_contact = self._normalize_contact(contact)
            if normalized_contact not in new_user_otps:
                return False, "No OTP found for this contact"
            
            stored_otp_data = new_user_otps[normalized_contact]

            try:
                otp_token = OTPToken(user_id=user_id, otp=stored_otp_data['otp'], created_at=stored_otp_data['created_at'])
                db.add(otp_token)
                db.flush()

                invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_id).first()
                if invite:
                    invite.is_used = True
                    invite.user_id = user_id
                    invite.used_at = datetime.utcnow()

                del new_user_otps[normalized_contact]
                db.commit()
                return True, "OTP verified successfully"
            except SQLAlchemyError as db_error:
                db.rollback()
                return False, "Failed to complete verification process"
        except Exception as e:
            db.rollback()
            return False, "Verification Failed"

    def _normalize_contact(self, contact: str) -> str:
        if not contact: return ""
        contact = contact.strip()
        if "@" in contact:
            return contact.lower()
        else:
            return re.sub(r'\D', '', contact)