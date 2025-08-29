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
        logging.info("✅ AuthManager initialized")
    
    async def send_otp(self, contact: str, invite_token: str = None, db: Session = None, current_user: User = None) -> AuthResult:
        """Send OTP for login, registration, or profile updates."""
        try:
            channel = self.utils.detect_channel(contact)
            normalized_contact = self.utils.normalize_contact(contact, channel)
            
            logging.info(f"🔍 Send OTP - Channel: {channel}, Normalized: {normalized_contact}")

            # --- NEW LOGIC: Handle profile updates for a logged-in user ---
            if current_user:
                logging.info(f"✅ Profile Update OTP Flow for user: {current_user.user_id}")
                otp = self._generate_otp()
                
                # Store OTP against the currently logged-in user's ID
                if not self.storage.store_for_existing_user(current_user.user_id, otp, db):
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")
                
                # Send the OTP to the NEW contact address/number
                result = await self._send_otp_via_channel(channel, normalized_contact, otp, current_user.name)
                if not result.success:
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)
            # --- END NEW LOGIC ---

            # --- Existing logic for LOGIN or NEW USER REGISTRATION ---
            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            if user:
                # Existing user login flow
                logging.info(f"🔍 Sending OTP to existing user: {user.user_id}")
                otp = self._generate_otp()
                if not self.storage.store_for_existing_user(user.user_id, otp, db):
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")
                result = await self._send_otp_via_channel(channel, normalized_contact, otp, user.name)
                if not result.success:
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)
            else:
                # New user registration flow
                if not invite_token:
                    logging.warning(f"🔍 Unregistered user attempted OTP without invite: {normalized_contact}")
                    return AuthResult(success=False, message="This contact is not registered. Please use a valid invite code.", error_code="USER_NOT_FOUND_NO_INVITE")
                
                from app.auth.utils import verify_invite_token
                invite_data = verify_invite_token(invite_token)
                invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_data["invite_id"]).first()
                if not invite or invite.is_used:
                    return AuthResult(success=False, message="Invite code is invalid or already used.", error_code="INVALID_INVITE")

                logging.info(f"🔍 Sending OTP to new user with valid invite token")
                otp = self._generate_otp()
                if not self.storage.store_for_new_user(normalized_contact, otp, db):
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")
                result = await self._send_otp_via_channel(channel, normalized_contact, otp)
                if not result.success:
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)

        except Exception as e:
            logging.error(f"Error in send_otp: {str(e)}", exc_info=True)
            return AuthResult(success=False, message="Failed to send OTP")

    def verify_otp(self, contact: str, otp: str, invite_token: str = None, db: Session = None) -> AuthResult:
        # This method's logic does not need to change for the fix.
        # It correctly handles new vs existing users based on database lookup.
        try:
            normalized_contact = self.utils.normalize_contact_auto(contact)
            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            if user:
                status, message = self.storage.verify_for_existing_user(user.user_id, otp, db)
                if status == "SUCCESS":
                    return AuthResult(success=True, message=message, user_id=str(user.user_id), is_new_user=False)
                else:
                    return AuthResult(success=False, message=message)
            else:
                if not invite_token:
                    return AuthResult(success=False, message="New user registration requires a valid invite token.")
                
                success, message = self.storage.verify_for_new_user(normalized_contact, otp, db)
                if not success:
                    return AuthResult(success=False, message=message)
                return AuthResult(success=True, message="OTP verified. Proceeding with registration.", is_new_user=True)
                
        except Exception as e:
            logging.error(f"Unexpected error in verify_otp: {str(e)}", exc_info=True)
            return AuthResult(success=False, message="An unexpected error occurred during verification.")
            
    async def _send_otp_via_channel(self, channel: str, recipient: str, otp: str, name: Optional[str] = "User"):
        try:
            if channel == "email":
                template_data = {"otp": otp, "name": name or "User"}
                content = self._load_template("otp_email.html", template_data)
                metadata = {"subject": f"Your Sarthi verification code: {otp}", "recipient_name": name}
                return await self.email_provider.send(recipient, content, metadata)
            elif channel == "whatsapp":
                return await self.whatsapp_provider.send(recipient, otp)
            else:
                return AuthResult(success=False, message="Unsupported channel")
        except Exception as e:
            logging.error(f"Error sending OTP via {channel}: {e}", exc_info=True)
            return AuthResult(success=False, message=f"Failed to send OTP via {channel}")
    
    def _generate_otp(self) -> str:
        return ''.join(random.choices(string.digits, k=6))

    def _load_template(self, template_file: str, data: dict) -> str:
        template_path = os.path.join(self.templates_path, template_file)
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        return Template(template_content).render(**data)