# =======================================================================
# app/services.py (Final Check)
# =======================================================================
from prompt_engine.service import PromptEngineService
from global_intent_classifier.service import GlobalIntentClassifierService
from distress_detection.detector import DistressDetector
from llm_system.client import LLMClient
from config import AppConfig
import uuid

class DeliveryService:
    @staticmethod
    async def send_reflection(reflection_id: uuid.UUID):
        print(f"DELIVERY_SERVICE: Delivering reflection {reflection_id}. (Not implemented)")
        pass

# This line must use .from_env()
config = AppConfig.from_env()

# Initialize services
prompt_engine_service = PromptEngineService.from_config(config.prompt_engine)
llm_service = LLMClient(config=config.llm)
distress_service = DistressDetector(config=config.distress, openai_api_key=config.llm.api_key)

global_intent_classifier = GlobalIntentClassifierService(
    prompt_engine_service=prompt_engine_service,
    llm_service=llm_service,
    config=config.global_intent_classifier
)

delivery_service = DeliveryService()