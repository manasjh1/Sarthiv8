# =======================================================================
# llm_system/client.py (Corrected)
# =======================================================================
from __future__ import annotations
import json
import logging
from typing import Dict, Any, TYPE_CHECKING
from .persona import GOLDEN_PERSONA_PROMPT
import openai

# This block is only processed by type-checkers, not when the code runs.
if TYPE_CHECKING:
    from config import LLMConfig

class LLMClient:
    """
    Client to interact with the OpenAI LLM, enforcing the Golden Persona.
    """
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = openai.OpenAI(api_key=self.config.api_key)

    async def process_json_request(self, json_input: str) -> str:
        """
        Processes a JSON request, adds the golden persona, and calls the real LLM.
        """
        try:
            input_data = json.loads(json_input)
            reflection_id = input_data.get("reflection_id")
            user_message = input_data.get("user_message", "")
            
            final_prompt_for_llm = f"{GOLDEN_PERSONA_PROMPT}\n\n--- TASK CONTEXT ---\n{input_data.get('prompt')}"

            self.logger.info(f"Sending request to OpenAI model '{self.config.model}'")
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": final_prompt_for_llm},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"}
            )
            llm_response_content = response.choices[0].message.content
            
            if llm_response_content:
                response_data = json.loads(llm_response_content)
                response_data["reflection_id"] = reflection_id
                return json.dumps(response_data)
            else:
                raise ValueError("LLM returned an empty response.")

        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            return await self._mock_llm_failure_response(reflection_id)

    async def _mock_llm_failure_response(self, reflection_id: str) -> str:
        """A fallback to prevent crashes if the real LLM call fails."""
        response = {
            "reflection_id": reflection_id,
            "system_response": {
                "intent": "NO_OVERRIDE",
                "error": "LLM_API_FAILURE",
                "engine": self.config.model
            },
            "user_response": {
                "message": "I'm sorry, I seem to be having technical difficulties. Please try again in a moment."
            }
        }
        return json.dumps(response)

    async def shutdown(self):
        self.logger.info("LLM Client shutdown.")