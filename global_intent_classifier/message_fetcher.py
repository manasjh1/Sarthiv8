import logging
from typing import Optional
from .models import MessageData
from .exceptions import IntentClassifierError, MessageNotFoundError


class MessageFetcher:
    """Service to fetch messages by reflection_id"""
    
    def __init__(self, message_service=None):
        """
        Initialize message fetcher
        
        Args:
            message_service: Your message service/database to fetch messages
        """
        self.message_service = message_service
        self.logger = logging.getLogger(__name__)
    
    async def fetch_message_by_reflection_id(self, reflection_id: str) -> MessageData:
        """
        Fetch message data by reflection_id
        
        Args:
            reflection_id: Unique reflection ID
            
        Returns:
            MessageData with user message and metadata
            
        Raises:
            MessageNotFoundError: If message not found
            IntentClassifierError: If fetch fails
        """
        try:
            self.logger.info(f"Fetching message for reflection_id: {reflection_id}")
            
            if self.message_service:
                # Call your actual message service
                message_data = await self.message_service.get_message_by_reflection_id(reflection_id)
                
                if not message_data:
                    raise MessageNotFoundError(f"No message found for reflection_id: {reflection_id}")
                
                return MessageData(
                    reflection_id=reflection_id,
                    user_message=message_data.get("message", ""),
                    timestamp=message_data.get("timestamp"),
                    metadata=message_data.get("metadata")
                )
            else:
                # Mock implementation for demonstration
                mock_messages = {
                    "test_001": "I want to stop this conversation",
                    "test_002": "Let's restart from the beginning", 
                    "test_003": "I'm confused about what we're doing",
                    "test_004": "Skip to draft please",
                    "test_005": "Tell me more about machine learning",
                    "conv_12345": "I want to stop this conversation",
                    "demo_001": "I want to stop"
                }
                
                if reflection_id not in mock_messages:
                    raise MessageNotFoundError(f"No message found for reflection_id: {reflection_id}")
                
                user_message = mock_messages[reflection_id]
                
                return MessageData(
                    reflection_id=reflection_id,
                    user_message=user_message,
                    timestamp="2024-01-01T12:00:00Z",
                    metadata={"source": "mock", "test": True}
                )
                
        except MessageNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch message for reflection_id {reflection_id}: {e}")
            raise IntentClassifierError(f"Failed to fetch message: {e}")

