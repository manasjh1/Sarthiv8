import json
import logging
from typing import Dict, Any
from .exceptions import LLMServiceError


class LLMServiceClient:
    """Client for LLM Service Package interactions"""

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.logger = logging.getLogger(__name__)

    async def classify_intent(self, reflection_id: str, prompt: str, user_message: str) -> Dict[str, Any]:
        """
        Send request to LLM Service and get the universal structured response.
        """
        try:
            llm_request = {
                "reflection_id": reflection_id,
                "prompt": prompt,
                "user_message": user_message
            }
            llm_response_json = await self.llm_service.process_json_request(json.dumps(llm_request))
            llm_response_data = json.loads(llm_response_json)

            if "system_response" not in llm_response_data or "user_response" not in llm_response_data:
                raise LLMServiceError("Missing required fields in LLM Service response")

            return {
                "system_response": llm_response_data.get("system_response", {}),
                "user_response": llm_response_data.get("user_response", {})
            }
        except Exception as e:
            raise LLMServiceError(f"Failed to classify intent via LLM Service: {e}")

    async def shutdown(self):
        pass


class MockLLMService:
    """
    Mock LLM Service that simulates the final, universal response structure.
    """
    async def initialize(self):
        pass

    async def process_json_request(self, json_input: str) -> str:
        input_data = json.loads(json_input)
        user_message = input_data.get("user_message", "")
        intent = self._classify_intent(user_message)

        # The final, universal format from the LLM
        response = {
            "reflection_id": input_data.get("reflection_id"),
            "system_response": {
                "intent": intent,
                "confidence": 0.95,
                "engine": "mock-llm-v1"
            },
            "user_response": {
                "message": f"This is the user-facing message. The intent was {intent}.",
                "suggestions": ["Option A", "Option B"]
            }
        }
        return json.dumps(response)

    def _classify_intent(self, user_message: str) -> str:
        if "stop" in user_message.lower():
            return "INTENT_STOP"
        if "restart" in user_message.lower():
            return "INTENT_RESTART"
        return "NO_OVERRIDE"

    async def shutdown(self):
        pass