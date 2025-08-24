import json
import logging
from typing import Dict, Any, Optional
from .models import MessageRequest, IntentResult, IntentType
from .llm_service_client import LLMServiceClient
from .message_fetcher import MessageFetcher
from .exceptions import IntentClassifierError, PromptEngineError


class GlobalIntentClassifierService:
    """Main service for global intent classification"""

    def __init__(self, prompt_engine_service, llm_service, config, message_service=None):
        """
        Initialize global intent classifier service
        """
        self.prompt_engine = prompt_engine_service
        self.llm_client = LLMServiceClient(llm_service)
        self.message_fetcher = MessageFetcher(message_service)
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def classify_intent(self, reflection_id: str, user_message: str) -> IntentResult:
        """
        Main method to classify intent from a user message.
        """
        try:
            self.logger.info(f"Starting intent classification for reflection_id: {reflection_id}")

            # Step 1: Get classifier prompt from prompt engine
            classifier_prompt_data = await self._get_classifier_prompt()
            self.logger.debug(f"Got classifier prompt from stage {self.config.intent_classifier_stage_id}")

            # Step 2: Send to LLM Service for intent classification
            intent_value = await self.llm_client.classify_intent(
                reflection_id=reflection_id,
                prompt=classifier_prompt_data["prompt"],
                user_message=user_message
            )

            self.logger.info(f"LLM Service returned intent: {intent_value}")

            # Step 3: Create and return result
            result = IntentResult(
                reflection_id=reflection_id,
                intent=IntentType(intent_value)
            )

            self.logger.info(f"Intent classification completed: {intent_value}")
            return result

        except Exception as e:
            self.logger.error(f"Intent classification failed: {e}")
            raise IntentClassifierError(f"Failed to classify intent: {e}")

    async def _get_classifier_prompt(self) -> Dict[str, Any]:
        """
        Get the classifier prompt from prompt engine (using config stage ID, empty data)
        """
        try:
            request_data = {
                "stage_id": self.config.intent_classifier_stage_id,
                "data": {}
            }
            self.logger.debug(f"Requesting classifier prompt with data: {request_data}")
            response = await self.prompt_engine.process_dict_request(request_data)
            if not response.get("prompt"):
                raise PromptEngineError("No prompt returned from prompt engine for classifier stage")
            return response
        except Exception as e:
            self.logger.error(f"Failed to get classifier prompt: {e}")
            raise PromptEngineError(f"Failed to get classifier prompt: {e}")

    async def process_json_request(self, json_input: str) -> str:
        """
        Process JSON request with reflection_id and message, and return JSON response.
        """
        try:
            input_data = json.loads(json_input)
            self.logger.debug(f"Processing JSON request: {input_data}")

            request = MessageRequest(**input_data)

            user_message = request.message
            if not user_message and request.reflection_id:
                # Fetch message if not provided
                message_data = await self.message_fetcher.fetch_message_by_reflection_id(request.reflection_id)
                user_message = message_data.user_message

            if not request.reflection_id:
                # Use a default or generate a new one if not provided
                request.reflection_id = "default-reflection-id"

            result = await self.classify_intent(
                reflection_id=request.reflection_id,
                user_message=user_message
            )

            return result.model_dump_json()

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON input: {e}")
            raise IntentClassifierError(f"Invalid JSON input: {e}")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
            raise IntentClassifierError(f"Service error: {e}")

    async def shutdown(self):
        """Shutdown the service and cleanup resources"""
        try:
            await self.llm_client.shutdown()
            self.logger.info("Global Intent Classifier Service shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")