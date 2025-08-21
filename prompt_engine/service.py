import json
import logging
from typing import Dict, Any
from .engine import AsyncPromptEngine
from .database import AsyncDatabaseManager
from .models import PromptRequest, PromptResponse
from .exceptions import PromptEngineError


class PromptEngineService:
    """Main service class for the prompt engine"""
    
    def __init__(self, connection_string: str, max_pool_size: int = 10, min_pool_size: int = 2, timeout: int = 30):
        """
        Initialize prompt engine service
        """
        self.logger = logging.getLogger(__name__)
        self.db_manager = AsyncDatabaseManager(connection_string, max_pool_size, min_pool_size, timeout)
        self.engine = AsyncPromptEngine(self.db_manager)
        self._initialized = False
    
    @classmethod
    def from_config(cls, prompt_config) -> 'PromptEngineService':
        """
        Create service from PromptEngineConfig
        """
        return cls(
            connection_string=prompt_config.supabase_connection_string,
            max_pool_size=prompt_config.max_pool_connections,
            min_pool_size=prompt_config.min_pool_connections,
            timeout=prompt_config.connection_timeout
        )
    
    async def initialize(self):
        """Initialize the service"""
        if not self._initialized:
            await self.db_manager.initialize()
            self._initialized = True
            self.logger.info("Prompt Engine Service initialized")
    
    async def shutdown(self):
        """Shutdown the service"""
        if self._initialized:
            await self.db_manager.close()
            self._initialized = False
            self.logger.info("Prompt Engine Service shutdown")
    
    async def process_json_request(self, json_input: str) -> str:
        """
        Process JSON request and return JSON response
        """
        if not self._initialized:
            raise PromptEngineError("Service not initialized")
        
        try:
            input_data = json.loads(json_input)
            self.logger.info(f"Processing request for stage_id: {input_data.get('stage_id')}")
            
            request = PromptRequest(**input_data)
            
            response = await self.engine.process_prompt(request)
            
            return response.model_dump_json()
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON input: {e}")
            raise PromptEngineError(f"Invalid JSON input: {e}")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
            raise PromptEngineError(f"Service error: {e}")
    
    async def process_dict_request(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process dictionary request and return dictionary response
        """
        if not self._initialized:
            raise PromptEngineError("Service not initialized")
        
        self.logger.info(f"Processing request for stage_id: {input_data.get('stage_id')}")
        request = PromptRequest(**input_data)
        response = await self.engine.process_prompt(request)
        return response.model_dump()

