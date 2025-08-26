# =======================================================================
# global_intent_classifier/llm_service_client.py (Corrected)
# =======================================================================
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
            # Assuming llm_service has a method like process_json_request
            llm_response_json = await self.llm_service.process_json_request(json.dumps(llm_request))
            llm_response_data = json.loads(llm_response_json)

            # FIXED: Use .get() to safely access keys that might be missing.
            # This provides a default empty dictionary {} if a key is not found,
            # preventing the "Missing required fields" error.
            return {
                "system_response": llm_response_data.get("system_response", {}),
                "user_response": llm_response_data.get("user_response", {})
            }
        except Exception as e:
            self.logger.error(f"Failed to classify intent via LLM Service: {e}")
            raise LLMServiceError(f"Failed to classify intent via LLM Service: {e}")

    async def shutdown(self):
        # Implement shutdown logic if your llm_service needs it
        pass