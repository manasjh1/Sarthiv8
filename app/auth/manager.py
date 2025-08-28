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
    
    async def send_otp(self, contact: str, invite_token: str = None, db: Session = None) -> AuthResult:
        """Send OTP with user existence check to prevent unnecessary API calls."""
        try:
            channel = self.utils.detect_channel(contact)
            normalized_contact = self.utils.normalize_contact(contact, channel)
            
            logging.info(f"🔍 Send OTP - Channel: {channel}, Normalized: {normalized_contact}")
            
            if not self._validate_contact(normalized_contact, channel):
                logging.warning(f"🔍 Invalid contact format: {contact}")
                return AuthResult(success=False, message="User not registered")

            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            if user:
                # === EXISTING USER ===
                logging.info(f"🔍 Sending OTP to existing user: {user.user_id}")
                
                otp = self._generate_otp()
                logging.info(f"🔍 Generated OTP: {otp}")
                
                if not self.storage.store_for_existing_user(user.user_id, otp, db):
                    logging.warning(f"🔍 Rate limit hit for existing user: {user.user_id}")
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")
                
                result = await self._send_otp_via_channel(channel, normalized_contact, otp, user.name)
                if not result.success:
                    logging.error(f"🔍 Failed to send OTP to existing user: {result.error}")
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                
                logging.info(f"✅ OTP sent successfully to existing user")
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)
            
            else:
                # === NEW USER LOGIC ===
                if not invite_token:
                    # FIXED: Reject immediately without sending OTP
                    logging.warning(f"🔍 Unregistered user attempted OTP without invite: {normalized_contact}")
                    return AuthResult(
                        success=False, 
                        message="This contact is not registered. Please use a valid invite code to create an account.",
                        error_code="USER_NOT_FOUND_NO_INVITE"
                    )
                
                # ADDITIONAL CHECK: Validate invite token before sending OTP
                try:
                    from app.auth.utils import verify_invite_token
                    invite_data = verify_invite_token(invite_token)
                    
                    # Check if invite exists and is unused
                    invite = db.query(InviteCode).filter(InviteCode.invite_id == invite_data["invite_id"]).first()
                    if not invite:
                        logging.warning(f"🔍 Invalid invite ID: {invite_data['invite_id']}")
                        return AuthResult(success=False, message="Invalid invite code.", error_code="INVALID_INVITE")
                    
                    if invite.is_used:
                        logging.warning(f"🔍 Invite already used: {invite_data['invite_id']}")
                        return AuthResult(success=False, message="This invite code has already been used.", error_code="INVITE_ALREADY_USED")
                    
                except Exception as invite_error:
                    logging.error(f"🔍 Invite validation failed: {invite_error}")
                    return AuthResult(success=False, message="User is not registered.", error_code="INVALID_INVITE_TOKEN")

                # NOW send OTP for valid new user with valid invite
                logging.info(f"🔍 Sending OTP to new user with valid invite token")
                
                otp = self._generate_otp()
                logging.info(f"🔍 Generated OTP: {otp}")
                
                if not self.storage.store_for_new_user(normalized_contact, otp, db):
                    logging.warning(f"🔍 Rate limit hit for new user: {normalized_contact}")
                    return AuthResult(success=False, message="Please wait 60 seconds before requesting a new OTP")

                result = await self._send_otp_via_channel(channel, normalized_contact, otp)
                if not result.success:
                    logging.error(f"🔍 Failed to send OTP to new user: {result.error}")
                    return AuthResult(success=False, message=f"Failed to send OTP: {result.error}")
                
                logging.info(f"✅ OTP sent successfully to new user with valid invite")
                return AuthResult(success=True, message="OTP sent successfully.", contact_type=channel)

        except Exception as e:
            logging.error(f"Error in send_otp: {str(e)}", exc_info=True)
            return AuthResult(success=False, message="Failed to send OTP")

    def verify_otp(self, contact: str, otp: str, invite_token: str = None, db: Session = None) -> AuthResult:
        """Verify OTP with enhanced logging and error handling."""
        try:
            normalized_contact = self.utils.normalize_contact_auto(contact)
            user = self.utils.find_user_by_contact(normalized_contact, db)
            
            logging.info(f"🔍 Verifying OTP - Contact: {contact} (normalized: {normalized_contact})")
            logging.info(f"🔍 User found: {user is not None}")
            
            if user:
                # ===== EXISTING USER VERIFICATION =====
                logging.info(f"🔍 Verifying OTP for existing user: {user.user_id}")
                status, message = self.storage.verify_for_existing_user(user.user_id, otp, db)
                
                logging.info(f"🔍 Existing user verification status: {status}")
                
                if status == "SUCCESS":
                    logging.info(f"✅ OTP verification successful for existing user: {user.user_id}")
                    return AuthResult(success=True, message=message, user_id=str(user.user_id), is_new_user=False)
                elif status == "NOT_FOUND":
                    logging.warning(f"🔍 OTP not found for existing user: {user.user_id}")
                    return AuthResult(success=False, message="Verification failed. Please try logging in again or request a new OTP.")
                else:
                    logging.warning(f"🔍 OTP verification failed for existing user: {message}")
                    return AuthResult(success=False, message=message)
            else:
                # ===== NEW USER VERIFICATION =====
                logging.info(f"🔍 Verifying OTP for new user: {normalized_contact}")
                
                if not invite_token:
                    logging.warning(f"🔍 New user verification attempted without invite token")
                    return AuthResult(success=False, message="New user registration requires a valid invite token.")
                
                success, message = self.storage.verify_for_new_user(normalized_contact, otp, db)
                logging.info(f"🔍 New user OTP verification result: {success} - {message}")
                
                if not success:
                    return AuthResult(success=False, message=message)
                
                logging.info(f"✅ OTP verification successful for new user")
                return AuthResult(success=True, message="OTP verified. Proceeding with registration.", is_new_user=True)
                
        except Exception as e:
            logging.error(f"Unexpected error in verify_otp: {str(e)}", exc_info=True)
            return AuthResult(success=False, message="An unexpected error occurred during verification.")
            
    async def _send_otp_via_channel(self, channel: str, recipient: str, otp: str, name: Optional[str] = "User"):
        """Send OTP via the appropriate channel with enhanced logging."""
        try:
            logging.info(f"🔍 Sending OTP via {channel} to {recipient}")
            
            if channel == "email":
                template_data = {"otp": otp, "name": name or "User"}
                content = self._load_template("otp_email.html", template_data)
                metadata = {"subject": f"Your Sarthi verification code: {otp}", "recipient_name": name}
                result = await self.email_provider.send(recipient, content, metadata)
                
                if result.success:
                    logging.info(f"✅ Email OTP sent successfully to {recipient}")
                else:
                    logging.error(f"❌ Email OTP failed to {recipient}: {result.error}")
                    
                return result
                
            elif channel == "whatsapp":
                result = await self.whatsapp_provider.send(recipient, otp)
                
                if result.success:
                    logging.info(f"✅ WhatsApp OTP sent successfully to {recipient}")
                else:
                    logging.error(f"❌ WhatsApp OTP failed to {recipient}: {result.error}")
                    
                return result
                
            else:
                logging.error(f"❌ Unsupported channel: {channel}")
                return AuthResult(success=False, message="Unsupported channel")
                
        except Exception as e:
            logging.error(f"Error sending OTP via {channel}: {str(e)}", exc_info=True)
            return AuthResult(success=False, message=f"Failed to send OTP via {channel}")

    
    async def send_feedback_email(self, sender_name: str, receiver_name: str, receiver_email: str, feedback_summary: str) -> AuthResult:
        """Send feedback email with 20%-80% split - ASYNC"""
        try:
            logging.info(f"Sending feedback email to: {receiver_email}")
            
            # Simple 20%-80% split
            split_point = int(len(feedback_summary) * 0.2)
            feedback_preview = feedback_summary[:split_point]
            feedback_remaining = feedback_summary[split_point:]
            
            # Template data
            template_data = {
                "sender_name": sender_name,
                "receiver_name": receiver_name,
                "feedback_preview": feedback_preview,
                "feedback_remaining": feedback_remaining
            }
            
            # Load template and send email - ASYNC
            content = self._load_template("feedback_email.html", template_data)
            metadata = {
                "subject": f"You have feedback from {sender_name}",
                "recipient_name": receiver_name
            }
            
            result = await self.email_provider.send(receiver_email, content, metadata)
            
            if result.success:
                return AuthResult(success=True, message=f"Feedback email sent successfully to {receiver_email}")
            else:
                logging.error(f"Email send failed: {result.error}")
                return AuthResult(success=False, message=f"Failed to send feedback email: {result.error}")
                
        except Exception as e:
            logging.error(f"Exception in send_feedback_email: {str(e)}")
            return AuthResult(success=False, message=f"Failed to send feedback email: {str(e)}")
    
    
    def _generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        otp = ''.join(random.choices(string.digits, k=6))
        logging.info(f"🔍 Generated OTP: {otp}")
        return otp

    def _load_template(self, template_file: str, data: dict) -> str:
        """Load and render email template with enhanced error handling."""
        try:
            template_path = os.path.join(self.templates_path, template_file)
            logging.info(f"🔍 Loading template: {template_path}")
            
            if not os.path.exists(template_path):
                logging.error(f"❌ Template file not found: {template_path}")
                # Return a simple fallback template
                return f"Your verification code is: {data.get('otp', 'N/A')}"
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = Template(template_content)
            rendered = template.render(**data)
            
            logging.info(f"✅ Template rendered successfully")
            return rendered
            
        except Exception as e:
            logging.error(f"Error loading template {template_file}: {str(e)}", exc_info=True)
            # Return a simple fallback
            return f"Your verification code is: {data.get('otp', 'N/A')}"

    def _validate_contact(self, contact: str, channel: str) -> bool:
        """Validate contact format with enhanced logging."""
        try:
            logging.info(f"🔍 Validating contact: {contact} for channel: {channel}")
            
            if channel == "email":
                is_valid = self.email_provider.validate_recipient(contact)
                logging.info(f"🔍 Email validation result: {is_valid}")
                return is_valid
            elif channel == "whatsapp":
                is_valid = self.whatsapp_provider.validate_recipient(contact)
                logging.info(f"🔍 WhatsApp validation result: {is_valid}")
                return is_valid
            else:
                logging.warning(f"🔍 Unknown channel for validation: {channel}")
                return False
                
        except Exception as e:
            logging.error(f"Error validating contact {contact}: {str(e)}", exc_info=True)
            return False