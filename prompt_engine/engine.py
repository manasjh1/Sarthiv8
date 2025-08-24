import logging
from typing import Dict, Any
from .database import AsyncDatabaseManager
from .template_processor import TemplateProcessor
from .models import PromptRequest, PromptResponse, PromptData
from .exceptions import PromptEngineError, StageNotFoundError, InvalidDataError


class AsyncPromptEngine:
    """Async prompt engine for orchestrating prompt generation"""
    
    def __init__(self, db_manager: AsyncDatabaseManager):
        """
        Initialize prompt engine
        
        Args:
            db_manager: Async database manager instance
        """
        self.db_manager = db_manager
        self.template_processor = TemplateProcessor()
        self.logger = logging.getLogger(__name__)
    
    async def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """
        Process prompt request and return response
        
        Args:
            request: PromptRequest containing stage_id and data (required, can be empty)
            
        Returns:
            PromptResponse with processed prompt and metadata
            
        Raises:
            PromptEngineError: If processing fails
        """
        try:
            prompt_data = await self.db_manager.get_prompt_by_stage_id(request.stage_id)
            
            processed_prompt = await self._process_prompt_text(prompt_data, request.data)
            
            return PromptResponse(
                prompt=processed_prompt,
                is_static=prompt_data.is_static,
                prompt_type=prompt_data.prompt_type,
                next_stage=prompt_data.next_stage
            )
            
            
        except (StageNotFoundError, InvalidDataError) as e:
            self.logger.error(f"Prompt processing error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in prompt processing: {e}")
            raise PromptEngineError(f"Failed to process prompt: {e}")
    
    async def _process_prompt_text(self, prompt_data: PromptData, data: Dict[str, Any]) -> str:
        """
        Process prompt text based on is_static flag
        """
        if prompt_data.is_static:
            # Static prompt - return as is
            return prompt_data.prompt or ""
        else:
            # Dynamic prompt - substitute variables
            return await self.template_processor.substitute_variables(
                prompt_data.prompt or "", data
            )