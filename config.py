import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class PromptEngineConfig:
    """Prompt engine specific configuration"""
    supabase_connection_string: str
    cache_ttl: int = 3600
    awaiting_emotion_cache_ttl: int = 7200
    max_pool_connections: int = 10
    min_pool_connections: int = 2
    connection_timeout: int = 30
    
    @classmethod
    def from_env(cls) -> 'PromptEngineConfig':
        """Load prompt engine config from environment variables"""
        connection_string = os.getenv('SUPABASE_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("SUPABASE_CONNECTION_STRING environment variable is required")
        
        return cls(
            supabase_connection_string=connection_string,
            cache_ttl=int(os.getenv('PROMPT_CACHE_TTL', '3600')),
            awaiting_emotion_cache_ttl=int(os.getenv('AWAITING_EMOTION_CACHE_TTL', '7200')),
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
        """Load Global Intent Classifier config from environment variables"""
        return cls(
            intent_classifier_stage_id=int(os.getenv('GIC_INTENT_STAGE_ID', '21'))
        )


# Add this to your existing config.py class structure
class AppConfig:
    """Your existing app configuration - updated to include new services"""
    
    def __init__(self):
        # Your existing config initialization
        # ...
        
        # Add prompt engine config
        self.prompt_engine = PromptEngineConfig.from_env()
        
        # Add global intent classifier config
        self.global_intent_classifier = GlobalIntentClassifierConfig.from_env()
