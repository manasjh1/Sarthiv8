# app/auth/manager.py
import os
import random
import string
import logging
from typing import Optional
from dataclasses import dataclass
from jinja2 import Template
from sqlalchemy.orm import Session
from app.auth.providers.email import EmailProvider
from app.auth.providers.whatsapp import WhatsAppProvider
from app.auth.storage import AuthStorage
from app.auth.utils import AuthUtils
from app.models import InviteCode, User

@dataclass
class AuthResult:
    success: bool
    message: str
    contact_type: Optional[str] = None
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    is_new_user: Optional[bool] = None
    error_code: Optional[str] = None


class AuthManager:
    """Central auth manager - handles all authentication messaging with async support"""
    
    def __init__(self):
        self.email_provider = EmailProvider()
        self.whatsapp_provider = WhatsAppProvider()
        self.storage = AuthStorage()
        self.utils = AuthUtils()
        self.templates_path = os.path.join(os.path.dirname(__file__), "templates")
    
    async def send_otp(self, contact: str, invite_token: str = None, db: Session = None) -> AuthResult:
        """Send OTP with corrected logic for existing vs. new users."""
        try:
            channel = self.utils.detect_channel(contact)
            normalized_contact = self.utils.normalize_contact(contact, channel)
            
            if not self._validate_contact(normalized_contact, channel):
                return AuthResult(success=False, message="Invalid contact format")
            
            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            if user:
                otp = self._generate_otp()
                if not self.storage.store_for_existing_user(user.user_id, otp, db):
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")
                
                result = await self._send_otp_via_channel(channel, normalized_contact, otp, user.name)
                if not result.success:
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)
            
            elif invite_token:
                otp = self._generate_otp()
                if not self.storage.store_for_new_user(normalized_contact, otp):
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")

                result = await self._send_otp_via_channel(channel, normalized_contact, otp)
                if not result.success:
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)
            
            else:
                return AuthResult(success=False, message="This contact is not registered. An invite token is required to sign up.")

        except Exception as e:
            logging.error(f"Error in send_otp: {str(e)}")
            return AuthResult(success=False, message="Failed to send OTP")

    # --- CORRECTED FUNCTION SIGNATURE ---
    def verify_otp(self, contact: str, otp: str, invite_token: str = None, db: Session = None) -> AuthResult:
        """Verify OTP with corrected arguments and improved logic."""
        try:
            normalized_contact = self.utils.normalize_contact_auto(contact)
            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            if user:
                # ===== EXISTING USER VERIFICATION =====
                status, message = self.storage.verify_for_existing_user(user.user_id, otp, db)
                
                if status == "SUCCESS":
                    return AuthResult(success=True, message=message, user_id=str(user.user_id), is_new_user=False)
                elif status == "NOT_FOUND":
                    return AuthResult(success=False, message="Verification failed. Please try logging in again or request a new OTP.")
                else:
                    return AuthResult(success=False, message=message)
            else:
                # ===== NEW USER VERIFICATION =====
                if not invite_token:
                    return AuthResult(success=False, message="New user registration requires a valid invite token.")
                
                success, message = self.storage.verify_for_new_user(normalized_contact, otp)
                if not success:
                    return AuthResult(success=False, message=message)
                
                return AuthResult(success=True, message="OTP verified. Proceeding with registration.", is_new_user=True)
                
        except Exception as e:
            logging.error(f"Unexpected error in verify_otp: {str(e)}", exc_info=True)
            return AuthResult(success=False, message="An unexpected error occurred during verification.")
            
    async def _send_otp_via_channel(self, channel: str, recipient: str, otp: str, name: Optional[str] = "User"):
        if channel == "email":
            template_data = {"otp": otp, "name": name or "User"}
            content = self._load_template("otp_email.html", template_data)
            metadata = {"subject": f"Your Sarthi verification code: {otp}", "recipient_name": name}
            return await self.email_provider.send(recipient, content, metadata)
        elif channel == "whatsapp":
            return await self.whatsapp_provider.send(recipient, otp)
        return AuthResult(success=False, message="Unsupported channel")

    def _generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))

    def _load_template(self, template_file: str, data: dict) -> str:
        template_path = os.path.join(self.templates_path, template_file)
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        template = Template(template_content)
        return template.render(**data)

    def _validate_contact(self, contact: str, channel: str) -> bool:
        if channel == "email":
            return self.email_provider.validate_recipient(contact)
        elif channel == "whatsapp":
            return self.whatsapp_provider.validate_recipient(contact)
        return False