# app/auth/storage.py - COMPLETE FIXED VERSION
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import OTPToken, InviteCode
import uuid

# DEPRECATED: This will be phased out in favor of database storage
new_user_otps: Dict[str, Dict] = {}

class AuthStorage:
    """Handles OTP storage for both existing and new users with enhanced logging and error handling"""
    
    def __init__(self):
        logging.info("✅ AuthStorage initialized")
    
    def store_for_existing_user(self, user_id: uuid.UUID, otp: str, db: Session) -> bool:
        """Store OTP for existing user in database with enhanced error handling."""
        try:
            logging.info(f"🔍 Storing OTP for existing user: {user_id}")
            
            # Check for existing OTP and rate limiting
            existing_otp = db.query(OTPToken).filter(OTPToken.user_id == user_id).first()
            if existing_otp:
                time_since_creation = datetime.utcnow() - existing_otp.created_at
                if time_since_creation < timedelta(minutes=1):
                    logging.warning(f"🔍 Rate limit hit for user {user_id}: {time_since_creation.total_seconds()} seconds ago")
                    return False
                
                logging.info(f"🔍 Deleting existing OTP for user {user_id}")
                db.delete(existing_otp)
                db.flush()
            
            # Create new OTP token
            otp_token = OTPToken(
                user_id=user_id, 
                otp=otp, 
                created_at=datetime.utcnow()
            )
            db.add(otp_token)
            db.commit()
            
            logging.info(f"✅ OTP stored successfully in database for existing user {user_id}")
            return True
            
        except SQLAlchemyError as e:
            db.rollback()
            logging.error(f"Database error storing OTP for user {user_id}: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            db.rollback()
            logging.error(f"Unexpected error storing OTP for user {user_id}: {str(e)}", exc_info=True)
            return False
    
    def store_for_new_user(self, contact: str, otp: str, db: Session = None) -> bool:
        """Store OTP for new user with enhanced error handling."""
        try:
            normalized_contact = self._normalize_contact(contact)
            logging.info(f"🔍 Storing OTP for new user: {normalized_contact}")
            
            # For now, still use memory storage but with better error handling
            # TODO: Move to database storage with TempOTP table
            if normalized_contact in new_user_otps:
                time_since_creation = datetime.utcnow() - new_user_otps[normalized_contact]['created_at']
                if time_since_creation < timedelta(minutes=1):
                    logging.warning(f"🔍 Rate limit hit for new user {normalized_contact}: {time_since_creation.total_seconds()} seconds ago")
                    return False
            
            new_user_otps[normalized_contact] = {
                'otp': otp, 
                'created_at': datetime.utcnow()
            }
            logging.info(f"✅ OTP stored successfully in memory for new user {normalized_contact}")
            return True
            
        except Exception as e:
            logging.error(f"Error storing OTP in memory for {contact}: {str(e)}", exc_info=True)
            return False

    def verify_for_existing_user(self, user_id: uuid.UUID, otp: str, db: Session) -> Tuple[str, str]:
        """
        Verify OTP for existing user with enhanced logging.
        Returns a status string: 'SUCCESS', 'INVALID', 'EXPIRED', or 'NOT_FOUND'.
        """
        try:
            otp = otp.strip()
            logging.info(f"🔍 Verifying OTP for existing user: {user_id}")
            
            otp_token = db.query(OTPToken).filter(OTPToken.user_id == user_id).first()
            
            if not otp_token:
                logging.warning(f"🔍 No OTP found for existing user: {user_id}")
                return "NOT_FOUND", "No OTP found for this user. Please request one."
            
            # Check if OTP has expired (3 minutes)
            time_since_creation = datetime.utcnow() - otp_token.created_at
            if time_since_creation > timedelta(minutes=3):
                logging.warning(f"🔍 OTP expired for user {user_id}: {time_since_creation.total_seconds()} seconds old")
                try:
                    db.delete(otp_token)
                    db.commit()
                    logging.info(f"🔍 Deleted expired OTP for user {user_id}")
                except Exception as cleanup_error:
                    logging.error(f"Failed to cleanup expired OTP: {cleanup_error}")
                return "EXPIRED", "OTP has expired. Please request a new one."
            
            # Check if OTP matches
            if otp_token.otp == otp:
                try:
                    db.delete(otp_token)
                    db.commit()
                    logging.info(f"✅ OTP verified and deleted successfully for existing user {user_id}")
                    return "SUCCESS", "OTP verified successfully."
                except SQLAlchemyError as e:
                    db.rollback()
                    logging.error(f"Failed to delete OTP for user {user_id}: {str(e)}", exc_info=True)
                    return "DB_ERROR", "Could not process OTP verification."
            else:
                logging.warning(f"🔍 Invalid OTP provided for user {user_id}. Expected: {otp_token.otp}, Got: {otp}")
                return "INVALID", "Invalid OTP provided."
                
        except Exception as e:
            logging.error(f"Error verifying OTP for user {user_id}: {str(e)}", exc_info=True)
            return "ERROR", "An unexpected error occurred during verification."

    def verify_for_new_user(self, contact: str, otp: str, db: Session = None) -> Tuple[bool, str]:
        """Verify OTP for new user with enhanced error handling and logging."""
        try:
            otp = otp.strip()
            normalized_contact = self._normalize_contact(contact)
            logging.info(f"🔍 Verifying OTP for new user: {normalized_contact}")
            
            if normalized_contact not in new_user_otps:
                logging.warning(f"🔍 No OTP found for new user: {normalized_contact}")
                return False, "No OTP found for this contact"
            
            stored_otp_data = new_user_otps[normalized_contact]
            
            # Check if OTP has expired (3 minutes)
            time_since_creation = datetime.utcnow() - stored_otp_data['created_at']
            if time_since_creation > timedelta(minutes=3):
                logging.warning(f"🔍 OTP expired for new user {normalized_contact}: {time_since_creation.total_seconds()} seconds old")
                # Clean up expired OTP
                try:
                    del new_user_otps[normalized_contact]
                    logging.info(f"🔍 Cleaned up expired OTP for new user: {normalized_contact}")
                except KeyError:
                    pass
                return False, "OTP has expired. Please request a new one"
            
            # Check if OTP matches
            if stored_otp_data['otp'] == otp:
                logging.info(f"✅ OTP verified successfully for new user: {normalized_contact}")
                return True, "OTP verified successfully"
            else:
                logging.warning(f"🔍 Invalid OTP provided for new user {normalized_contact}. Expected: {stored_otp_data['otp']}, Got: {otp}")
                return False, "Invalid OTP"
                
        except Exception as e:
            logging.error(f"Error verifying OTP for new user {contact}: {str(e)}", exc_info=True)
            return False, "Verification failed"
    
    def transfer_to_database(self, contact: str, user_id: uuid.UUID, invite_id: str, db: Session) -> Tuple[bool, str]:
        """Transfer new user data to database and cleanup temporary storage."""
        try:
            normalized_contact = self._normalize_contact(contact)
            logging.info(f"🔍 Transferring data to database for new user: {normalized_contact}")
            
            if normalized_contact not in new_user_otps:
                logging.warning(f"🔍 No OTP data found for transfer: {normalized_contact}")
                return False, "No OTP found for this contact"
            
            stored_otp_data = new_user_otps[normalized_contact]

            try:
                # Create OTP token record for the new user
                otp_token = OTPToken(
                    user_id=user_id, 
                    otp=stored_otp_data['otp'], 
                    created_at=stored_otp_data['created_at']
                )
                db.add(otp_token)
                db.flush()
                logging.info(f"🔍 Created OTP token record for new user: {user_id}")

                # Mark invite as used
                invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_id).first()
                if invite:
                    invite.is_used = True
                    invite.user_id = user_id
                    invite.used_at = datetime.utcnow()
                    logging.info(f"🔍 Marked invite {invite_id} as used")

                # Clean up memory storage
                del new_user_otps[normalized_contact]
                logging.info(f"🔍 Cleaned up memory storage for: {normalized_contact}")
                
                # Commit all changes (this will be done by the calling function)
                # db.commit() - Don't commit here, let the caller handle it
                
                logging.info(f"✅ Data transfer completed successfully for user: {user_id}")
                return True, "OTP verified successfully"
                
            except SQLAlchemyError as db_error:
                # Don't rollback here, let the caller handle it
                logging.error(f"Database error during transfer: {str(db_error)}", exc_info=True)
                return False, "Failed to complete verification process"
                
        except Exception as e:
            # Don't rollback here, let the caller handle it
            logging.error(f"Error during data transfer: {str(e)}", exc_info=True)
            return False, "Verification Failed"

    def cleanup_expired_otps(self, db: Session) -> int:
        """Clean up expired OTP tokens from database and memory."""
        cleaned_count = 0
        
        try:
            # Clean up database OTPs (older than 5 minutes)
            expiry_time = datetime.utcnow() - timedelta(minutes=5)
            expired_db_count = db.query(OTPToken).filter(
                OTPToken.created_at < expiry_time
            ).delete()
            
            if expired_db_count > 0:
                db.commit()
                logging.info(f"🔍 Cleaned up {expired_db_count} expired database OTPs")
                cleaned_count += expired_db_count
            
            # Clean up memory OTPs (older than 5 minutes)
            expired_contacts = []
            for contact, otp_data in new_user_otps.items():
                if datetime.utcnow() - otp_data['created_at'] > timedelta(minutes=5):
                    expired_contacts.append(contact)
            
            for contact in expired_contacts:
                del new_user_otps[contact]
                cleaned_count += 1
            
            if expired_contacts:
                logging.info(f"🔍 Cleaned up {len(expired_contacts)} expired memory OTPs")
                
        except Exception as e:
            logging.error(f"Error during OTP cleanup: {str(e)}", exc_info=True)
            
        return cleaned_count

    def _normalize_contact(self, contact: str) -> str:
        """Normalize contact format consistently."""
        if not contact: 
            return ""
        contact = contact.strip()
        if "@" in contact:
            return contact.lower()
        else:
            return re.sub(r'\D', '', contact)