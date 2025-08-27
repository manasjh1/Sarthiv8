import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Reflection, User, Chat
from app.auth.providers.email import EmailProvider
from app.auth.providers.whatsapp import WhatsAppProvider
from app.auth.manager import AuthManager
from app.handlers.database import get_user_by_chat_id
from fastapi import HTTPException

class DeliveryService:
    """
    Delivery service for handling reflection delivery
    Updated for v8 - uses proper database functions and column names
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
        Main delivery method - updated for v8 database structure
        Called when Stage 19 completes
        
        Returns dict with success, message, and data for frontend
        """
        try:
            self.logger.info(f"Starting delivery for reflection {reflection_id}")
            
            # Get reflection and validate
            reflection = self._get_reflection(reflection_id, db)
            
            # Get sender user using chat_id (v8 structure)
            sender_user = get_user_by_chat_id(db, reflection.chat_id)
            if not sender_user:
                raise HTTPException(
                    status_code=404, 
                    detail="Sender user not found"
                )
            
            # Get summary from database
            summary = self._get_reflection_summary(reflection)
            if not summary:
                raise HTTPException(
                    status_code=400, 
                    detail="No summary available for delivery"
                )

            # Check if identity reveal is handled
            if not self._is_identity_decided(reflection):
                return self._handle_identity_reveal_request(reflection_id, reflection, sender_user, summary)
            
            # Check delivery mode
            if not hasattr(reflection, 'delivery_mode') or reflection.delivery_mode is None:
                return self._show_delivery_options(reflection_id, reflection, summary)
            
            # Handle delivery based on mode
            return await self._execute_delivery(reflection, sender_user, summary, db)

        except Exception as e:
            self.logger.error(f"Delivery failed for reflection {reflection_id}: {str(e)}")
            raise

    def _is_identity_decided(self, reflection: Reflection) -> bool:
        """Check if identity reveal has been decided"""
        return reflection.is_anonymous is not None

    def _handle_identity_reveal_request(
        self, 
        reflection_id: uuid.UUID, 
        reflection: Reflection, 
        user: User, 
        summary: str
    ) -> Dict[str, Any]:
        """Handle identity reveal request - adapted for v8"""
        return {
            "success": True,
            "reflection_id": str(reflection_id),
            "sarthi_message": "Here's your reflection summary. Would you like to reveal your name in this message, or send it anonymously?",
            "current_stage": 100,  # For compatibility
            "next_stage": 100,
            "data": [{
                "summary": summary,
                "next_step": "identity_reveal",
                "options": [
                    {"reveal_name": True, "label": "Reveal my name"},
                    {"reveal_name": False, "label": "Send anonymously"}
                ]
            }]
        }

    def _show_delivery_options(
        self, 
        reflection_id: uuid.UUID, 
        reflection: Reflection, 
        summary: str
    ) -> Dict[str, Any]:
        """Show delivery mode options - adapted for v8"""
        return {
            "success": True,
            "reflection_id": str(reflection_id),
            "sarthi_message": "Perfect! How would you like to deliver your message? Please provide the recipient's contact details.",
            "current_stage": 100,
            "next_stage": 100,
            "data": [{
                "summary": summary,
                "delivery_options": [
                    {
                        "mode": 0, 
                        "name": "Email", 
                        "description": "Send via email",
                        "input_required": {
                            "recipient_email": {
                                "type": "email",
                                "placeholder": "Enter recipient's email address",
                                "label": "Recipient's Email",
                                "required": True
                            }
                        }
                    },
                    {
                        "mode": 1, 
                        "name": "WhatsApp", 
                        "description": "Send via WhatsApp",
                        "input_required": {
                            "recipient_phone": {
                                "type": "tel",
                                "placeholder": "Enter recipient's phone number (e.g., +1234567890)",
                                "label": "Recipient's Phone Number",
                                "required": True
                            }
                        }
                    },
                    {
                        "mode": 2, 
                        "name": "Both", 
                        "description": "Send via both email and WhatsApp",
                        "input_required": {
                            "recipient_email": {
                                "type": "email",
                                "placeholder": "Enter recipient's email address",
                                "label": "Recipient's Email",
                                "required": True
                            },
                            "recipient_phone": {
                                "type": "tel",
                                "placeholder": "Enter recipient's phone number (e.g., +1234567890)",
                                "label": "Recipient's Phone Number",
                                "required": True
                            }
                        }
                    },
                    {
                        "mode": 3, 
                        "name": "Private", 
                        "description": "Keep it private (no delivery)"
                    }
                ],
                "third_party_option": {
                    "description": "Or send to someone else's email",
                    "instruction": "Provide email in data like: {'email': 'recipient@example.com'}"
                },
                "identity_status": {
                    "is_anonymous": reflection.is_anonymous,
                    "sender_name": reflection.sender_name
                },
                "note": "Make sure you have permission to send messages to the recipient."
            }]
        }

    async def process_identity_choice(
        self,
        reflection_id: uuid.UUID,
        reveal_choice: bool,
        provided_name: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Process identity reveal choice - adapted for v8"""
        try:
            reflection = self._get_reflection(reflection_id, db)
            user = get_user_by_chat_id(db, reflection.chat_id)
            summary = self._get_reflection_summary(reflection)
            
            if reveal_choice is False:
                # User chose anonymous
                reflection.is_anonymous = True
                reflection.sender_name = None
                db.commit()
                
                return self._show_delivery_options(reflection_id, reflection, summary)
                
            elif reveal_choice is True:
                if provided_name:
                    # User provided name
                    reflection.is_anonymous = False
                    reflection.sender_name = provided_name.strip()
                    db.commit()
                    
                    return self._show_delivery_options(reflection_id, reflection, summary)
                else:
                    # Ask for name input
                    default_name = user.name if user.name else ""
                    
                    return {
                        "success": True,
                        "reflection_id": str(reflection_id),
                        "sarthi_message": "Please enter your name to include it in your reflection.",
                        "current_stage": 100,
                        "next_stage": 100,
                        "data": [{
                            "summary": summary,
                            "input": {
                                "name": "name", 
                                "placeholder": "Enter your name",
                                "default_value": default_name
                            }
                        }]
                    }
            
        except Exception as e:
            self.logger.error(f"Error processing identity choice: {str(e)}")
            raise

    async def process_delivery_choice(
        self,
        reflection_id: uuid.UUID,
        delivery_mode: int,
        recipient_contact: Dict[str, str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Process delivery mode choice - adapted for v8
        recipient_contact format: {"recipient_email": "...", "recipient_phone": "..."}
        """
        try:
            reflection = self._get_reflection(reflection_id, db)
            
            # Validate delivery mode
            if delivery_mode not in [0, 1, 2, 3]:
                raise HTTPException(status_code=400, detail="Invalid delivery mode")
            
            # Store delivery mode
            reflection.delivery_mode = delivery_mode
            db.commit()
            
            # Execute delivery with recipient contact info
            sender_user = get_user_by_chat_id(db, reflection.chat_id)
            summary = self._get_reflection_summary(reflection)
            
            return await self._execute_delivery_with_contact(
                reflection, sender_user, summary, recipient_contact, db
            )
            
        except Exception as e:
            self.logger.error(f"Error processing delivery choice: {str(e)}")
            raise

    async def process_third_party_email(
        self,
        reflection_id: uuid.UUID,
        third_party_email: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """Handle third-party email delivery - adapted for v8"""
        try:
            reflection = self._get_reflection(reflection_id, db)
            sender_user = get_user_by_chat_id(db, reflection.chat_id)
            summary = self._get_reflection_summary(reflection)
            
            # Validate email
            if not self._is_valid_email(third_party_email):
                raise HTTPException(status_code=400, detail="Invalid email address format")
            
            # Create recipient user with chat (v8 structure)
            await self._create_or_update_recipient_user(
                contact=third_party_email,
                reflection=reflection,
                db=db
            )
            
            # Send email
            sender_name = self._get_sender_name(reflection, sender_user)
            result = await self.auth_manager.send_feedback_email(
                sender_name=sender_name,
                receiver_name=reflection.receiver_name or "Recipient",
                receiver_email=third_party_email,
                feedback_summary=summary
            )
            
            if not result.success:
                raise HTTPException(status_code=500, detail=result.message)
            
            # Mark as delivered with third-party flag
            reflection.delivery_mode = 4  # Special mode for third-party email
            reflection.is_delivered = 1
            db.commit()
            
            return {
                "success": True,
                "reflection_id": str(reflection_id),
                "sarthi_message": f"Your reflection has been sent to {third_party_email} successfully! 📧 Now, how are you feeling after completing this reflection?",
                "current_stage": 100,
                "next_stage": 100,
                "data": [{
                    "summary": summary,
                    "third_party_email_sent": True,
                    "recipient": third_party_email,
                    "sender": sender_name,
                    "about": reflection.receiver_name
                }]
            }
            
        except Exception as e:
            self.logger.error(f"Third-party email delivery failed: {str(e)}")
            raise

    async def _execute_delivery(
        self, 
        reflection: Reflection, 
        sender_user: User, 
        summary: str,
        db: Session
    ) -> Dict[str, Any]:
        """Execute delivery - only for modes that don't need recipient contact"""
        if reflection.delivery_mode == 3:  # Private mode
            return self._handle_private_mode(reflection, db)
        else:
            # Other modes need recipient contact - should not reach here
            raise HTTPException(
                status_code=400, 
                detail="Delivery requires recipient contact information"
            )

    async def _execute_delivery_with_contact(
        self, 
        reflection: Reflection, 
        sender_user: User, 
        summary: str,
        recipient_contact: Dict[str, str],
        db: Session
    ) -> Dict[str, Any]:
        """Execute delivery with recipient contact info - adapted for v8"""
        delivery_mode = reflection.delivery_mode or 0
        delivery_status = []
        
        if delivery_mode == 3:  # Private mode
            return self._handle_private_mode(reflection, db)
        
        try:
            recipient_email = recipient_contact.get("recipient_email") if recipient_contact else None
            recipient_phone = recipient_contact.get("recipient_phone") if recipient_contact else None
            
            if delivery_mode == 0:  # Email only
                if not recipient_email:
                    raise HTTPException(status_code=400, detail="Email delivery requires recipient email")
                
                await self._deliver_via_email(
                    sender_user, summary, reflection, recipient_email, delivery_status, db
                )
                message = f"Your message has been sent via email to {recipient_email} successfully! 📧"
                
            elif delivery_mode == 1:  # WhatsApp only
                if not recipient_phone:
                    raise HTTPException(status_code=400, detail="WhatsApp delivery requires recipient phone")
                
                await self._deliver_via_whatsapp(
                    sender_user, summary, reflection, recipient_phone, delivery_status, db
                )
                message = f"Your message has been sent via WhatsApp to {recipient_phone} successfully! 📱"
                
            elif delivery_mode == 2:  # Both
                sent_methods = []
                
                if recipient_email:
                    try:
                        await self._deliver_via_email(
                            sender_user, summary, reflection, recipient_email, [], db
                        )
                        delivery_status.append("email_sent")
                        sent_methods.append("email")
                    except Exception as e:
                        self.logger.warning(f"Email delivery failed: {str(e)}")
                
                if recipient_phone:
                    try:
                        await self._deliver_via_whatsapp(
                            sender_user, summary, reflection, recipient_phone, [], db
                        )
                        delivery_status.append("whatsapp_sent")
                        sent_methods.append("WhatsApp")
                    except Exception as e:
                        self.logger.warning(f"WhatsApp delivery failed: {str(e)}")
                
                if not sent_methods:
                    raise HTTPException(status_code=400, detail="All delivery methods failed")
                
                message = f"Your message has been sent via {' and '.join(sent_methods)} successfully! 📧📱"
            
            # Update reflection as delivered
            reflection.is_delivered = 1
            db.commit()
            
            self.logger.info(f"Delivery completed - Status: {delivery_status}")
            
            return {
                "success": True,
                "reflection_id": str(reflection.reflection_id),
                "sarthi_message": f"{message} Now, how are you feeling after completing this reflection?",
                "current_stage": 100,
                "next_stage": 100,
                "data": [{
                    "summary": summary,
                    "delivery_status": delivery_status,
                    "delivery_complete": True,
                    "feedback_required": True
                }]
            }
            
        except Exception as e:
            self.logger.error(f"Delivery execution failed: {str(e)}")
            raise

    def _handle_private_mode(self, reflection: Reflection, db: Session) -> Dict[str, Any]:
        """Handle private delivery mode"""
        reflection.is_delivered = 1  # Mark as delivered
        db.commit()
        
        self.logger.info(f"Private mode selected for reflection {reflection.reflection_id}")
        
        return {
            "success": True,
            "reflection_id": str(reflection.reflection_id),
            "sarthi_message": "Your message has been saved privately. No delivery was made. 🔒 Now, how are you feeling after completing this reflection?",
            "current_stage": 100,
            "next_stage": 100,
            "data": [{
                "summary": self._get_reflection_summary(reflection),
                "status": ["private"],
                "delivery_complete": True,
                "feedback_required": True
            }]
        }

    async def _deliver_via_email(
        self, 
        sender_user: User,
        summary: str, 
        reflection: Reflection,
        recipient_email: str,
        delivery_status: list,
        db: Session
    ):
        """Deliver message via email to recipient"""
        self.logger.info(f"Attempting email delivery to: {recipient_email}")

        # Create recipient user and chat (v8 structure)
        await self._create_or_update_recipient_user(
            contact=recipient_email, 
            reflection=reflection,
            db=db
        )
        
        # Get sender name for email
        sender_name = self._get_sender_name(reflection, sender_user)
        
        # Send reflection via email using auth manager
        result = await self.auth_manager.send_feedback_email(
            sender_name=sender_name,
            receiver_name=reflection.receiver_name or "Recipient",
            receiver_email=recipient_email,
            feedback_summary=summary
        )
        
        if not result.success:
            raise HTTPException(
                status_code=500, 
                detail=f"Email sending failed: {result.message}"
            )
            
        delivery_status.append("email_sent")
        self.logger.info(f"✅ Email sent successfully to: {recipient_email}")

    async def _deliver_via_whatsapp(
        self, 
        sender_user: User, 
        summary: str, 
        reflection: Reflection,
        recipient_phone: str,
        delivery_status: list,
        db: Session
    ):
        """Deliver reflection summary via WhatsApp to recipient"""
        self.logger.info(f"Attempting WhatsApp delivery to: {recipient_phone}")

        # Create recipient user and chat (v8 structure)
        await self._create_or_update_recipient_user(
            contact=recipient_phone, 
            reflection=reflection,
            db=db
        )
        
        # Generate reflection link
        reflection_link = f"https://app.sarthi.me/reflection/{reflection.reflection_id}"
        
        # Get sender name for WhatsApp
        sender_name = self._get_sender_name(reflection, sender_user)
        
        # Send via WhatsApp template
        result = await self.whatsapp_provider.send_reflection_summary(
            recipient=recipient_phone,
            sender_name=sender_name,
            reflection_link=reflection_link
        )
        
        if not result.success:
            raise HTTPException(
                status_code=500, 
                detail=f"WhatsApp delivery failed: {result.error}"
            )
            
        delivery_status.append("whatsapp_sent")
        self.logger.info(f"✅ WhatsApp sent successfully to: {recipient_phone}")

    async def _create_or_update_recipient_user(
        self, 
        contact: str,
        reflection: Reflection,
        db: Session
    ) -> User:
        """
        Create or update recipient user AND create their chat (v8 structure)
        CRITICAL: Creates both user_id AND chat_id as required in v8
        """
        try:
            # Use auth utils to detect and normalize contact
            contact_type = self.auth_manager.utils.detect_channel(contact)
            normalized_contact = self.auth_manager.utils.normalize_contact(contact, contact_type)
            
            self.logger.info(f"Creating/updating recipient user - Contact: {contact}, Type: {contact_type}")
            
            # Find if user already exists
            existing_user = self.auth_manager.utils.find_user_by_contact(normalized_contact, db)
            
            if not existing_user:
                # Create new user for the recipient
                new_user_id = uuid.uuid4()
                
                new_recipient_user = User(
                    user_id=new_user_id,
                    email=normalized_contact if contact_type == "email" else None,
                    phone_number=int(normalized_contact) if contact_type == "whatsapp" and normalized_contact.isdigit() else None,
                    name=reflection.receiver_name if reflection.receiver_name else None,
                    user_type='user',
                    is_verified=False,
                    status=1
                )
                
                db.add(new_recipient_user)
                db.commit()
                db.refresh(new_recipient_user)
                
                # *** CRITICAL: Create chat for the new user (v8 structure) ***
                new_chat = Chat(user_id=new_recipient_user.user_id)
                db.add(new_chat)
                db.commit()
                db.refresh(new_chat)
                
                self.logger.info(f"✅ Created new user: {new_user_id} and chat: {new_chat.chat_id}")
                
                # Link reflection to this new user as receiver
                reflection.receiver_user_id = new_recipient_user.user_id
                db.commit()
                
                return new_recipient_user
                
            else:
                # User already exists - ensure they have a chat
                if not existing_user.chat:
                    # Create chat for existing user if they don't have one
                    new_chat = Chat(user_id=existing_user.user_id)
                    db.add(new_chat)
                    db.commit()
                    db.refresh(new_chat)
                    
                    self.logger.info(f"✅ Created chat {new_chat.chat_id} for existing user: {existing_user.user_id}")
                
                # Link reflection to this existing user
                reflection.receiver_user_id = existing_user.user_id
                db.commit()
                
                self.logger.info(f"📌 Linked reflection to existing user: {existing_user.user_id}")
                
                return existing_user
                
        except Exception as e:
            self.logger.error(f"Error creating/updating recipient user for {contact}: {str(e)}")
            db.rollback()
            raise

    def _get_reflection(self, reflection_id: uuid.UUID, db: Session) -> Reflection:
        """Get and validate reflection from database"""
        reflection = db.query(Reflection).filter(
            Reflection.reflection_id == reflection_id
        ).first()

        if not reflection:
            raise HTTPException(status_code=404, detail="Reflection not found")
        
        return reflection

    def _get_reflection_summary(self, reflection: Reflection) -> str:
        """Get reflection summary from database"""
        if reflection and reflection.summary and reflection.summary.strip():
            return reflection.summary
        return None

    def _get_sender_name(self, reflection: Reflection, user: User) -> str:
        """Get appropriate sender name based on anonymity settings"""
        if reflection.is_anonymous:
            return "Anonymous"
        elif reflection.sender_name:
            return reflection.sender_name
        elif user.name:
            return user.name
        else:
            return "Anonymous"

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format"""
        import re
        if not email:
            return False
        
        email_str = str(email).strip()
        if not email_str:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email_str) is not None