import json
import logging
from typing import Dict, Any
from config import LLMConfig # <-- Imports from the central config file
from .persona import GOLDEN_PERSONA_PROMPT
import openai


class LLMClient:
    """
    Client to interact with the OpenAI LLM, enforcing the Golden Persona.
    """
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Initialize the official OpenAI client using the API key from the config
        self.client = openai.OpenAI(api_key=self.config.api_key)

    async def process_json_request(self, json_input: str) -> str:
        """
        Processes a JSON request, adds the golden persona, and calls the real LLM.
        """
        try:
            input_data = json.loads(json_input)
            reflection_id = input_data.get("reflection_id")
            user_message = input_data.get("user_message", "")
            
            # Combine the Golden Persona with the specific instructions from the prompt engine
            final_prompt_for_llm = f"{GOLDEN_PERSONA_PROMPT}\n\n--- TASK CONTEXT ---\n{input_data.get('prompt')}"

            self.logger.info(f"Sending request to OpenAI model '{self.config.model}'")
            
            # --- REAL OPENAI API CALL ---
            # This uses the official openai library to make the request
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": final_prompt_for_llm},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"} # Ensures the LLM returns valid JSON
            )
            llm_response_content = response.choices[0].message.content
            
            # The LLM doesn't know the reflection_id, so we add it back to the response
            if llm_response_content:
                response_data = json.loads(llm_response_content)
                response_data["reflection_id"] = reflection_id
                return json.dumps(response_data)
            else:
                raise ValueError("LLM returned an empty response.")

        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            # Provides a safe fallback response if the API call fails
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