import json
import logging
from typing import Dict, Any
from .models import IntentType
from .exceptions import LLMServiceError


class LLMServiceClient:
    """Client for LLM Service Package interactions"""
    
    def __init__(self, llm_service):
        """
        Initialize LLM Service client
        
        Args:
            llm_service: Instance of LLM Service package (similar to PromptEngineService)
        """
        self.llm_service = llm_service
        self.logger = logging.getLogger(__name__)
    
    async def classify_intent(self, reflection_id: str, prompt: str, user_message: str) -> str:
        """
        Send request to LLM Service Package and get intent
        
        Args:
            reflection_id: Unique reflection ID
            prompt: System prompt from prompt engine
            user_message: User message to classify
            
        Returns:
            Intent string (e.g., "INTENT_STOP")
            
        Raises:
            LLMServiceError: If LLM Service request fails
        """
        try:
            # Prepare the request for LLM Service Package
            llm_request = {
                "reflection_id": reflection_id,
                "prompt": prompt,
                "user_message": user_message
            }
            
            self.logger.info(f"Sending request to LLM Service for reflection_id: {reflection_id}")
            self.logger.debug(f"LLM Service Request: {json.dumps(llm_request, indent=2)}")
            
            # Call LLM Service Package (similar to how we call prompt_engine.process_json_request)
            llm_response_json = await self.llm_service.process_json_request(json.dumps(llm_request))
            llm_response_data = json.loads(llm_response_json)
            
            self.logger.info(f"Received response from LLM Service for reflection_id: {reflection_id}")
            self.logger.debug(f"LLM Response: {llm_response_data}")
            
            # Validate response format
            if "reflection_id" not in llm_response_data:
                raise LLMServiceError("Missing reflection_id in LLM Service response")
            
            if "intent" not in llm_response_data:
                raise LLMServiceError("Missing intent in LLM Service response")
            
            # Validate intent value
            intent_value = llm_response_data["intent"]
            try:
                IntentType(intent_value)  # Validate it's a valid intent
            except ValueError:
                self.logger.warning(f"Invalid intent '{intent_value}' from LLM Service, defaulting to NO_OVERRIDE")
                intent_value = "NO_OVERRIDE"
            
            return intent_value
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response from LLM Service: {e}")
            raise LLMServiceError(f"Invalid JSON response from LLM Service: {e}")
        except Exception as e:
            self.logger.error(f"LLM Service request failed: {e}")
            raise LLMServiceError(f"Failed to classify intent via LLM Service: {e}")
    
    async def shutdown(self):
        """Shutdown the LLM Service client"""
        try:
            if hasattr(self.llm_service, 'shutdown'):
                await self.llm_service.shutdown()
                self.logger.info("LLM Service shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during LLM Service shutdown: {e}")


# Mock LLM Service for demonstration (until real LLM Service package is implemented)
class MockLLMService:
    """
    Mock LLM Service that simulates the LLM Service package
    Returns simple intent classification
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._initialized = False
    
    async def initialize(self):
        """Initialize the mock LLM service"""
        self._initialized = True
        self.logger.info("Mock LLM Service initialized")
    
    async def process_json_request(self, json_input: str) -> str:
        """
        Process JSON request and return JSON response with intent only
        
        Args:
            json_input: JSON string with reflection_id, prompt, and user_message
            
        Returns:
            JSON string with reflection_id and intent only
        """
        try:
            input_data = json.loads(json_input)
            reflection_id = input_data.get("reflection_id")
            user_message = input_data.get("user_message", "")
            
            # Mock intent classification
            intent = self._classify_intent(user_message)
            
            response = {
                "reflection_id": reflection_id,
                "intent": intent
            }
            
            return json.dumps(response)
            
        except Exception as e:
            self.logger.error(f"Mock LLM Service error: {e}")
            raise
    
    def _classify_intent(self, user_message: str) -> str:
        """Mock intent classification"""
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ["stop", "quit", "exit", "end"]):
            return "INTENT_STOP"
        elif any(word in message_lower for word in ["restart", "start over", "begin again"]):
            return "INTENT_RESTART"
        elif any(word in message_lower for word in ["confused", "don't understand", "unclear", "help"]):
            return "INTENT_CONFUSED"
        elif any(word in message_lower for word in ["skip", "draft", "jump to draft"]):
            return "INTENT_SKIP_TO_DRAFT"
        else:
            return "NO_OVERRIDE"
    
    async def shutdown(self):
        """Shutdown the mock LLM service"""
        self._initialized = False
        self.logger.info("Mock LLM Service shutdown")
