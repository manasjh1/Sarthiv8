# =======================================================================
# app/services.py (CORRECTED - Using keyword arguments)
# =======================================================================
from prompt_engine.service import PromptEngineService
from global_intent_classifier.service import GlobalIntentClassifierService
from distress_detection.detector import DistressDetector
from llm_system.client import LLMClient
from config import AppConfig
from delivery_service.service import DeliveryService
import uuid

class DeliveryServiceWrapper:
    """Wrapper to match v7 interface exactly"""
    
    @staticmethod
    async def send_reflection(reflection_id: uuid.UUID, request_data: list = None, db=None):
        """Main entry point - handles user input"""
        delivery_service = DeliveryService()
        return await delivery_service.send_reflection(reflection_id=reflection_id, db=db)
    
    @staticmethod
    async def process_identity_choice(reflection_id: uuid.UUID, reveal_choice: bool, provided_name: str = None, db=None):
        """Process identity reveal choice"""
        delivery_service = DeliveryService()
        # FIXED: Use keyword arguments
        return await delivery_service.process_identity_choice(
            reflection_id=reflection_id,
            reveal_choice=reveal_choice,
            provided_name=provided_name,
            db=db
        )
    
    @staticmethod
    async def process_delivery_choice(reflection_id: uuid.UUID, delivery_mode: int, recipient_contact: dict = None, db=None):
        """Process delivery mode choice"""
        delivery_service = DeliveryService()
        # FIXED: Use keyword arguments
        return await delivery_service.process_delivery_choice(
            reflection_id=reflection_id,
            delivery_mode=delivery_mode,
            recipient_contact=recipient_contact,
            db=db
        )
    
    @staticmethod
    async def process_third_party_email(reflection_id: uuid.UUID, third_party_email: str, db=None):
        """Process third-party email delivery"""
        delivery_service = DeliveryService()
        # FIXED: Use keyword arguments
        return await delivery_service.process_third_party_email(
            reflection_id=reflection_id,
            third_party_email=third_party_email,
            db=db
        )

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

delivery_service = DeliveryServiceWrapper()