# =======================================================================
# config.py (Corrected and Consolidated)
# =======================================================================
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class PromptEngineConfig:
    """Prompt engine specific configuration"""
    supabase_connection_string: str
    max_pool_connections: int = 10
    min_pool_connections: int = 2
    connection_timeout: int = 30

    @classmethod
    def from_env(cls) -> 'PromptEngineConfig':
        connection_string = os.getenv('SUPABASE_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("SUPABASE_CONNECTION_STRING is required")
        return cls(
            supabase_connection_string=connection_string,
            max_pool_connections=int(os.getenv('PROMPT_MAX_POOL_CONNECTIONS', '10')),
            min_pool_connections=int(os.getenv('PROMPT_MIN_POOL_CONNECTIONS', '2')),
            connection_timeout=int(os.getenv('PROMPT_CONNECTION_TIMEOUT', '30'))
        )

@dataclass
class GlobalIntentClassifierConfig:
    """Global Intent Classifier specific configuration"""
    intent_classifier_stage_id: int = 21

    @classmethod
    def from_env(cls) -> 'GlobalIntentClassifierConfig':
        return cls(
            intent_classifier_stage_id=int(os.getenv('GIC_INTENT_STAGE_ID', '21'))
        )

@dataclass
class LLMConfig:
    """Configuration for the LLM service, loaded from environment variables"""
    # --- Fields without default values (required) ---
    api_key: str = field(repr=False)
    jwt_secret_key: str
    zeptomail_token: str
    
    # --- Fields with default values (optional) ---
    provider: str = "openai"
    model: str = "gpt-4o"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    zeptomail_from_domain: str = "noreply@sarthi.me"
    zeptomail_from_name: str = "Sarthi"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_template_name: str = "authentication"

    @classmethod
    def from_env(cls) -> 'LLMConfig':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        jwt_key = os.getenv('JWT_SECRET_KEY')
        if not jwt_key:
            raise ValueError("JWT_SECRET_KEY environment variable is not set")

        zeptomail_t = os.getenv('ZEPTOMAIL_TOKEN')
        if not zeptomail_t:
            raise ValueError("ZEPTOMAIL_TOKEN environment variable is not set")

        return cls(
            api_key=api_key,
            jwt_secret_key=jwt_key,
            zeptomail_token=zeptomail_t,
            provider=os.getenv('LLM_PROVIDER', 'openai'),
            model=os.getenv('LLM_MODEL', 'gpt-4o'),
            jwt_algorithm=os.getenv('JWT_ALGORITHM', 'HS256'),
            jwt_expiration_hours=int(os.getenv('JWT_EXPIRATION_HOURS', '24')),
            zeptomail_from_domain=os.getenv('ZEPTOMAIL_FROM_DOMAIN', 'noreply@sarthi.me'),
            zeptomail_from_name=os.getenv('ZEPTOMAIL_FROM_NAME', 'Sarthi'),
            whatsapp_access_token=os.getenv('WHATSAPP_ACCESS_TOKEN', ''),
            whatsapp_phone_number_id=os.getenv('WHATSAPP_PHONE_NUMBER_ID', ''),
            whatsapp_template_name=os.getenv('WHATSAPP_TEMPLATE_NAME', 'authentication')
        )

@dataclass
class DistressConfig:
    """Configuration for the Distress Detection service"""
    pinecone_api_key: str = field(repr=False)
    pinecone_index: str
    pinecone_namespace: str = "distress"
    openai_embed_model: str = "text-embedding-3-small"
    red_threshold: float = 0.65
    yellow_threshold: float = 0.55

    @classmethod
    def from_env(cls) -> 'DistressConfig':
        pinecone_key = os.getenv('PINECONE_API_KEY')
        pinecone_index = os.getenv('PINECONE_INDEX')
        if not pinecone_key or not pinecone_index:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX are required")
        return cls(
            pinecone_api_key=pinecone_key,
            pinecone_index=pinecone_index,
            pinecone_namespace=os.getenv('PINECONE_NAMESPACE', 'distress'),
            openai_embed_model=os.getenv('OPENAI_EMBED_MODEL', 'text-embedding-3-small'),
            red_threshold=float(os.getenv('DISTRESS_RED_THRESHOLD', '0.65')),
            yellow_threshold=float(os.getenv('DISTRESS_YELLOW_THRESHOLD', '0.55'))
        )

@dataclass
class AppConfig:
    """
    Central application configuration that holds settings for all services.
    This is the single, correct version of the class.
    """
    prompt_engine: PromptEngineConfig
    global_intent_classifier: GlobalIntentClassifierConfig
    llm: LLMConfig
    distress: DistressConfig

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Load all configurations from environment variables"""
        return cls(
            prompt_engine=PromptEngineConfig.from_env(),
            global_intent_classifier=GlobalIntentClassifierConfig.from_env(),
            llm=LLMConfig.from_env(),
            distress=DistressConfig.from_env()
        )