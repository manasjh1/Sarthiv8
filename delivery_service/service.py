# delivery_service/service.py

import logging
import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models import Reflection, User, Chat
from app.auth.providers.email import EmailProvider
from app.auth.providers.whatsapp import WhatsAppProvider
from app.auth.manager import AuthManager
from app.handlers.database import get_user_by_chat_id
from fastapi import HTTPException
import re

class DeliveryService:
    """
    Delivery service for handling reflection delivery.
    This version is corrected to match the stateful logic of v7's Stage100.
    """

    def __init__(self):
        """Initialize delivery service with required providers"""
        self.email_provider = EmailProvider()
        self.whatsapp_provider = WhatsAppProvider()
        self.auth_manager = AuthManager()
        self.logger = logging.getLogger(__name__)

    async def send_reflection(
        self,
        reflection_id: uuid.UUID,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Main delivery method that orchestrates the entire delivery flow,
        matching the logic from sarthiv7's Stage100.
        """
        try:
            self.logger.info(f"Starting delivery process for reflection {reflection_id}")
            
            reflection = self._get_reflection(reflection_id, db)
            sender_user = get_user_by_chat_id(db, reflection.chat_id)
            if not sender_user:
                raise HTTPException(status_code=404, detail="Sender user not found")
            
            summary = self._get_reflection_summary(reflection)
            if not summary:
                raise HTTPException(status_code=400, detail="No summary available for delivery")

            # 1. Check if identity has been decided
            if not self._is_identity_decided(reflection):
                return self._handle_identity_reveal_request(reflection_id, reflection, sender_user, summary)
            
            # 2. Check if delivery mode has been chosen
            if not hasattr(reflection, 'delivery_mode') or reflection.delivery_mode is None:
                return self._show_delivery_options(reflection_id, reflection, summary)
            
            # 3. If everything is decided, execute delivery (this path is for retries or private mode)
            return await self._execute_delivery(reflection, sender_user, summary, db)

        except Exception as e:
            self.logger.error(f"Delivery failed for reflection {reflection_id}: {str(e)}", exc_info=True)
            raise

    async def process_identity_choice(
        self,
        reflection_id: uuid.UUID,
        reveal_choice: bool,
        provided_name: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Processes the user's choice to reveal their name or send anonymously."""
        reflection = self._get_reflection(reflection_id, db)
        user = get_user_by_chat_id(db, reflection.chat_id)
        summary = self._get_reflection_summary(reflection)
        
        if reveal_choice is False:
            reflection.is_anonymous = True
            reflection.sender_name = None
            db.commit()
            return self._show_delivery_options(reflection_id, reflection, summary)
            
        elif reveal_choice is True:
            if provided_name:
                reflection.is_anonymous = False
                reflection.sender_name = provided_name.strip()
                db.commit()
                return self._show_delivery_options(reflection_id, reflection, summary)
            else:
                default_name = user.name if user.name else ""
                return {
                    "success": True, "reflection_id": str(reflection_id),
                    "sarthi_message": "Please enter your name to include it in your reflection.",
                    "current_stage": 100, "next_stage": 100,
                    "data": [{"summary": summary, "input": {"name": "name", "placeholder": "Enter your name", "default_value": default_name}}]
                }
        return {} # Fallback

    async def process_delivery_choice(
        self,
        reflection_id: uuid.UUID,
        delivery_mode: int,
        recipient_contact: Dict[str, str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Processes the user's chosen delivery method and executes it."""
        reflection = self._get_reflection(reflection_id, db)
        
        if delivery_mode not in [0, 1, 2, 3]:
            raise HTTPException(status_code=400, detail="Invalid delivery mode")
        
        reflection.delivery_mode = delivery_mode
        db.commit()
        
        sender_user = get_user_by_chat_id(db, reflection.chat_id)
        summary = self._get_reflection_summary(reflection)
        
        return await self._execute_delivery_with_contact(
            reflection, sender_user, summary, recipient_contact, db
        )

    async def process_third_party_email(
        self,
        reflection_id: uuid.UUID,
        third_party_email: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """Handles sending a reflection to a third-party email address."""
        reflection = self._get_reflection(reflection_id, db)
        sender_user = get_user_by_chat_id(db, reflection.chat_id)
        summary = self._get_reflection_summary(reflection)
        
        if not self._is_valid_email(third_party_email):
            raise HTTPException(status_code=400, detail="Invalid email address format")
        
        await self._create_or_update_recipient_user(
            contact=third_party_email, reflection=reflection, db=db
        )
        
        sender_name = self._get_sender_name(reflection, sender_user)
        result = await self.auth_manager.send_feedback_email(
            sender_name=sender_name,
            receiver_name=reflection.receiver_name or "Recipient",
            receiver_email=third_party_email,
            feedback_summary=summary
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        
        reflection.delivery_mode = 4
        reflection.is_delivered = 1
        db.commit()
        
        return {
            "success": True, "reflection_id": str(reflection_id),
            "sarthi_message": f"Your reflection has been sent to {third_party_email} successfully! 📧 Now, how are you feeling?",
            "current_stage": 100, "next_stage": 100,
            "data": [{"summary": summary, "third_party_email_sent": True, "recipient": third_party_email, "sender": sender_name, "about": reflection.receiver_name}]
        }

    # Internal helper methods below...
    def _get_reflection(self, reflection_id: uuid.UUID, db: Session) -> Reflection:
        reflection = db.query(Reflection).filter(Reflection.reflection_id == reflection_id).first()
        if not reflection:
            raise HTTPException(status_code=404, detail="Reflection not found")
        return reflection

    def _get_reflection_summary(self, reflection: Reflection) -> str:
        return reflection.summary.strip() if reflection and reflection.summary and reflection.summary.strip() else None

    def _is_identity_decided(self, reflection: Reflection) -> bool:
        return reflection.is_anonymous is not None

    def _handle_identity_reveal_request(self, reflection_id: uuid.UUID, reflection: Reflection, user: User, summary: str) -> Dict[str, Any]:
        return {
            "success": True, "reflection_id": str(reflection_id),
            "sarthi_message": "Here's your reflection summary. Would you like to reveal your name or send it anonymously?",
            "current_stage": 100, "next_stage": 100,
            "data": [{"summary": summary, "next_step": "identity_reveal", "options": [
                {"reveal_name": True, "label": "Reveal my name"},
                {"reveal_name": False, "label": "Send anonymously"}
            ]}]
        }

    def _show_delivery_options(self, reflection_id: uuid.UUID, reflection: Reflection, summary: str) -> Dict[str, Any]:
        sender_name = getattr(reflection, 'sender_name', None)
        return {
            "success": True, "reflection_id": str(reflection_id),
            "sarthi_message": "Perfect! How would you like to deliver your message?",
            "current_stage": 100, "next_stage": 100,
            "data": [{"summary": summary, "delivery_options": [
                {"mode": 0, "name": "Email", "description": "Send via email", "input_required": {"recipient_email": {"type": "email", "placeholder": "Recipient's email", "label": "Recipient's Email", "required": True}}},
                {"mode": 1, "name": "WhatsApp", "description": "Send via WhatsApp", "input_required": {"recipient_phone": {"type": "tel", "placeholder": "Recipient's phone", "label": "Recipient's Phone", "required": True}}},
                {"mode": 2, "name": "Both", "description": "Send via both", "input_required": {"recipient_email": {"type": "email", "placeholder": "Recipient's email", "label": "Recipient's Email", "required": True}, "recipient_phone": {"type": "tel", "placeholder": "Recipient's phone", "label": "Recipient's Phone", "required": True}}},
                {"mode": 3, "name": "Private", "description": "Keep it private"}
            ], "identity_status": {"is_anonymous": reflection.is_anonymous, "sender_name": sender_name}}]
        }

    async def _execute_delivery_with_contact(self, reflection: Reflection, sender_user: User, summary: str, recipient_contact: Dict[str, str], db: Session) -> Dict[str, Any]:
        delivery_mode = reflection.delivery_mode
        delivery_status = []
        message = ""

        if delivery_mode == 3:
            return self._handle_private_mode(reflection, db)
        
        recipient_email = recipient_contact.get("recipient_email") if recipient_contact else None
        recipient_phone = recipient_contact.get("recipient_phone") if recipient_contact else None

        if delivery_mode in [0, 2] and recipient_email:
            try:
                await self._deliver_via_email(sender_user, summary, reflection, recipient_email, delivery_status, db)
                delivery_status.append("email_sent")
            except Exception as e:
                self.logger.warning(f"Email delivery failed: {e}")
        
        if delivery_mode in [1, 2] and recipient_phone:
            try:
                await self._deliver_via_whatsapp(sender_user, summary, reflection, recipient_phone, delivery_status, db)
                delivery_status.append("whatsapp_sent")
            except Exception as e:
                self.logger.warning(f"WhatsApp delivery failed: {e}")

        if not delivery_status:
            raise HTTPException(status_code=500, detail="All selected delivery methods failed.")
        
        if "email_sent" in delivery_status and "whatsapp_sent" in delivery_status:
            message = "Your message has been sent via email and WhatsApp! 📧📱"
        elif "email_sent" in delivery_status:
            message = f"Your message has been sent via email to {recipient_email} successfully! 📧"
        elif "whatsapp_sent" in delivery_status:
            message = f"Your message has been sent via WhatsApp to {recipient_phone} successfully! 📱"

        reflection.is_delivered = 1
        db.commit()
        
        return {
            "success": True, "reflection_id": str(reflection.reflection_id),
            "sarthi_message": f"{message} Now, how are you feeling?",
            "current_stage": 100, "next_stage": 100,
            "data": [{"summary": summary, "delivery_status": delivery_status, "delivery_complete": True, "feedback_required": True}]
        }

    def _handle_private_mode(self, reflection: Reflection, db: Session) -> Dict[str, Any]:
        reflection.is_delivered = 1
        db.commit()
        return {
            "success": True, "reflection_id": str(reflection.reflection_id),
            "sarthi_message": "Your message is saved privately.  How are you feeling?",
            "current_stage": 100, "next_stage": 100,
            "data": [{"summary": self._get_reflection_summary(reflection), "status": ["private"], "delivery_complete": True, "feedback_required": True}]
        }

    async def _deliver_via_email(self, sender_user, summary, reflection, recipient_email, delivery_status, db):
        await self._create_or_update_recipient_user(contact=recipient_email, reflection=reflection, db=db)
        sender_name = self._get_sender_name(reflection, sender_user)
        result = await self.auth_manager.send_feedback_email(
            sender_name=sender_name,
            receiver_name=reflection.receiver_name or "Recipient",
            receiver_email=recipient_email,
            feedback_summary=summary
        )
        if not result.success:
            raise Exception(f"Email sending failed: {result.message}")
        self.logger.info(f" Email sent to: {recipient_email}")

    async def _deliver_via_whatsapp(self, sender_user, summary, reflection, recipient_phone, delivery_status, db):
        await self._create_or_update_recipient_user(contact=recipient_phone, reflection=reflection, db=db)
        reflection_link = f"https://app.sarthi.me/reflection/{reflection.reflection_id}?type=inbox"
        sender_name = self._get_sender_name(reflection, sender_user)
        result = await self.whatsapp_provider.send_reflection_summary(
            recipient=recipient_phone,
            sender_name=sender_name,
            reflection_link=reflection_link
        )
        if not result.success:
            raise Exception(f"WhatsApp delivery failed: {result.error}")
        self.logger.info(f" WhatsApp sent to: {recipient_phone}")

    async def _create_or_update_recipient_user(self, contact, reflection, db) -> User:
        contact_type = self.auth_manager.utils.detect_channel(contact)
        normalized_contact = self.auth_manager.utils.normalize_contact(contact, contact_type)
        
        existing_user = self.auth_manager.utils.find_user_by_contact(normalized_contact, db)
        
        if not existing_user:
            new_user = User(
                email=(normalized_contact if contact_type == "email" else None),
                phone_number=(int(normalized_contact) if contact_type == "whatsapp" and normalized_contact.isdigit() else None),
                name=(reflection.receiver_name if reflection.receiver_name else None),
                is_verified=False
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            new_chat = Chat(user_id=new_user.user_id)
            db.add(new_chat)
            db.commit()
            
            self.logger.info(f" Created new recipient user: {new_user.user_id} and chat: {new_chat.chat_id}")
            reflection.receiver_user_id = new_user.user_id
            db.commit()
            return new_user
        else:
            if not existing_user.chat:
                new_chat = Chat(user_id=existing_user.user_id)
                db.add(new_chat)
                db.commit()
                self.logger.info(f" Created chat for existing recipient user: {existing_user.user_id}")
            
            reflection.receiver_user_id = existing_user.user_id
            db.commit()
            return existing_user

    def _get_sender_name(self, reflection: Reflection, user: User) -> str:
        if getattr(reflection, 'is_anonymous', False): return "Anonymous"
        if getattr(reflection, 'sender_name', None): return reflection.sender_name
        if user.name: return user.name
        return "Anonymous"

    def _is_valid_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, str(email).strip()) is not None