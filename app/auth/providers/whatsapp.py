import aiohttp
import asyncio
import logging
import re
import json
from typing import Dict, Any
from config import AppConfig
from app.auth.providers.base import MessageProvider, SendResult

config = AppConfig.from_env()

class WhatsAppProvider(MessageProvider):
    """Async WhatsApp provider with detailed debugging"""
    
    def __init__(self):
        self.api_url = "https://crmapi.wa0.in/api/meta/v19.0"
        self.access_token = config.llm.whatsapp_access_token
        self.phone_number_id = config.llm.whatsapp_phone_number_id
        self.template_name = config.llm.whatsapp_template_name
        
        if not self.access_token or not self.phone_number_id:
            logging.warning("WhatsApp API credentials not configured")
    
    async def send(self, recipient: str, content: str, metadata: Dict[str, Any] = None) -> SendResult:
        """Send WhatsApp message asynchronously with detailed debugging"""
        try:
            if not self.access_token or not self.phone_number_id:
                return SendResult(success=False, error="WhatsApp service not configured")
            
            normalized_phone = self._normalize_phone_number(recipient)
            if not normalized_phone:
                return SendResult(success=False, error="Invalid phone number format")
            
            otp_code = self._extract_otp_from_content(content)
            if not otp_code:
                return SendResult(success=False, error="Could not extract OTP from content")
            
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "to": normalized_phone,
                "recipient_type": "individual",
                "type": "template",
                "template": {
                    "name": self.template_name,
                    "language": {
                        "code": "en",
                        "policy": "deterministic"
                    },
                    "components": [
                        { "type": "body", "parameters": [{"type": "text", "text": otp_code }] },
                        { "type": "button", "sub_type": "url", "index": 0, "parameters": [{"type": "text", "text": otp_code }] }
                    ]
                }
            }
            
            logging.info(f"🔍 WhatsApp Payload: {json.dumps(payload, indent=2)}")
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logging.info(f"📊 WhatsApp Raw Response: {response_text}")
                    
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        return SendResult(success=False, error=f"Invalid JSON response: {response_text}")
                    
                    if response.status == 200:
                        # *** FIX: PARSE THE CORRECT RESPONSE STRUCTURE ***
                        message_info = response_data.get("message", {})
                        if not isinstance(message_info, dict):
                             # Fallback for the old "messages" list structure just in case
                            message_info = response_data.get("messages", [{}])[0]

                        message_id = message_info.get("queue_id") or message_info.get("id", "no_id_found")
                        message_status = message_info.get("message_status", "no_status_found")
                        # *** END FIX ***
                        
                        logging.info(f"✅ OTP SUCCESS DETAILS: Message ID: {message_id}, Status: {message_status}")
                        return SendResult(success=True, message_id=message_id)
                    else:
                        logging.error(f"❌ OTP API ERROR: Status: {response.status}, Response: {response_text}")
                        if 'error' in response_data:
                            error_info = response_data['error']
                            error_msg = f"API Error {error_info.get('code', 'unknown')}: {error_info.get('message', 'unknown error')}"
                        else:
                            error_msg = f"HTTP {response.status}: {response_text}"
                        return SendResult(success=False, error=error_msg)
                        
        except asyncio.TimeoutError:
            return SendResult(success=False, error="Request timeout")
        except aiohttp.ClientError as e:
            return SendResult(success=False, error=f"HTTP client error: {str(e)}")
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_reflection_summary(self, recipient: str, sender_name: str, reflection_link: str) -> SendResult:
        """Send reflection summary using the 'delivered' template"""
        try:
            if not self.access_token or not self.phone_number_id:
                return SendResult(success=False, error="WhatsApp service not configured")
            
            # Normalize phone number
            normalized_phone = self._normalize_phone_number(recipient)
            if not normalized_phone:
                return SendResult(success=False, error="Invalid phone number format")
            
            # API endpoint
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Payload for 'delivered' template with 2 parameters
            payload = {
                "to": normalized_phone,
                "recipient_type": "individual",
                "type": "template",
                "template": {
                    "language": {
                        "policy": "deterministic",
                        "code": "en"
                    },
                    "name": "delivered",  # Your template name for reflection delivery
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": sender_name  # First variable: sender name
                                },
                                {
                                    "type": "text", 
                                    "text": reflection_link  # Second variable: link
                                }
                            ]
                        }
                    ]
                }
            }
            
            logging.info(f"🔍 Sending Reflection Payload: {json.dumps(payload, indent=2)}")

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if 200 <= response.status < 300:
                        logging.info("✅ Reflection sent successfully.")
                        return SendResult(success=True)
                    else:
                        response_text = await response.text()
                        logging.error(f"❌ Failed to send reflection: {response.status} {response_text}")
                        return SendResult(success=False, error=response_text)

        except Exception as e:
            logging.error(f"❌ Exception sending reflection: {e}")
            return SendResult(success=False, error=str(e))

    def validate_recipient(self, recipient: str) -> bool:
        clean_number = re.sub(r'\D', '', recipient)
        return 10 <= len(clean_number) <= 15
    
    def _normalize_phone_number(self, phone: str) -> str:
        clean_number = re.sub(r'\D', '', phone)
        if not clean_number: return ""
        if len(clean_number) == 10:
            clean_number = "91" + clean_number
        return clean_number
    
    def _extract_otp_from_content(self, content: str) -> str:
        otp_pattern = r'\b\d{6}\b'
        match = re.search(otp_pattern, content)
        if match:
            return match.group()
        return content.strip()