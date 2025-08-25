import json
import logging
from typing import Dict, Any, Optional
from .models import ConversationRequest, IntentResult
from .llm_service_client import LLMServiceClient
from .message_fetcher import MessageFetcher
from .exceptions import IntentClassifierError, PromptEngineError


class GlobalIntentClassifierService:
    """Main service for global intent classification"""

    def __init__(self, prompt_engine_service, llm_service, config, message_service=None):
        self.prompt_engine = prompt_engine_service
        self.llm_client = LLMServiceClient(llm_service)
        self.message_fetcher = MessageFetcher(message_service)
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def classify_intent(self, reflection_id: str, user_message: str) -> IntentResult:
        """
        Main method to get the final universal response from the LLM.
        """
        try:
            classifier_prompt_data = await self._get_classifier_prompt()
            llm_result = await self.llm_client.classify_intent(
                reflection_id=reflection_id,
                prompt=classifier_prompt_data["prompt"],
                user_message=user_message
            )
            return IntentResult(
                reflection_id=reflection_id,
                system_response=llm_result["system_response"],
                user_response=llm_result["user_response"]
            )
        except Exception as e:
            raise IntentClassifierError(f"Failed to classify intent: {e}")

    async def _get_classifier_prompt(self) -> Dict[str, Any]:
        request_data = {"stage_id": self.config.intent_classifier_stage_id, "data": {}}
        response = await self.prompt_engine.process_dict_request(request_data)
        if not response.get("prompt"):
            raise PromptEngineError("No prompt returned for classifier stage")
        return response

    async def process_json_request(self, json_input: str) -> str:
        try:
            input_data = json.loads(json_input)
            request = ConversationRequest(**input_data) # <-- CORRECTED
            user_message = request.user_response or ""
            reflection_id = request.reflection_id or "default-reflection-id"
            result = await self.classify_intent(
                reflection_id=reflection_id,
                user_message=user_message
            )
            return result.model_dump_json()
        except Exception as e:
            raise IntentClassifierError(f"Service error: {e}")

    async def shutdown(self):
        await self.llm_client.shutdown()