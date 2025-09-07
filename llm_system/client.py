from __future__ import annotations
import json
import logging
from typing import Dict, Any, TYPE_CHECKING
from .persona import GOLDEN_PERSONA_PROMPT
import openai


if TYPE_CHECKING:
    from config import LLMConfig

class LLMClient:
    """
    Client to interact with the OpenAI LLM, enforcing the Golden Persona.
    Automatically normalizes all responses to expected format.
    """
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = openai.OpenAI(api_key=self.config.api_key)

    async def chat_completion(self, system_prompt: str, user_message: str, persona: str = None, reflection_id: str = None) -> str:
        """
        Generates a chat completion using the LLM.
        This is a convenience method that wraps process_json_request.
        """
        if persona:
            system_prompt = f"{persona}\n\n{system_prompt}"
            
        llm_request = {
            "reflection_id": reflection_id,
            "prompt": system_prompt,
            "user_message": user_message
        }
        return await self.process_json_request(json.dumps(llm_request))

    async def process_json_request(self, json_input: str) -> str:
        """
        Processes a JSON request, adds the golden persona, calls the LLM,
        and normalizes the response to expected format.
        """
        try:
            input_data = json.loads(json_input)
            reflection_id = input_data.get("reflection_id")
            user_message = input_data.get("user_message", "")
            
            final_prompt_for_llm = f"{GOLDEN_PERSONA_PROMPT}\n\n--- TASK CONTEXT ---\n{input_data.get('prompt')}\n\nEnsure your response is a valid JSON object."
            print(f"🚨 LLM_CLIENT: Calling OpenAI with model: {self.config.model}")
            print(f"🚨 LLM_CLIENT: User message: {user_message}")
            print(f"🚨 LLM_CLIENT: Final prompt length: {len(final_prompt_for_llm)}")
            

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
            print(f"🚨 LLM_CLIENT: Raw OpenAI response: {llm_response_content}")
            
            
            if llm_response_content:
                raw_response = json.loads(llm_response_content)
                print(f"🚨 LLM_CLIENT: Parsed OpenAI response: {raw_response}")
                self.logger.info(f"Raw LLM response: {raw_response}")
                
                normalized_response = self._normalize_response(raw_response, reflection_id)
                print(f"🚨 LLM_CLIENT: Normalized response: {normalized_response}")
                self.logger.info(f"Normalized response: {normalized_response}")
                
                return json.dumps(normalized_response)
            else:
                raise ValueError("LLM returned an empty response.")

        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            return await self._mock_llm_failure_response(reflection_id)

    def _normalize_response(self, raw_response: Dict[str, Any], reflection_id: str) -> Dict[str, Any]:
        """
        Normalize any LLM response format to the expected nested structure:
        {
            "system_response": {...},
            "user_response": {"message": "..."},
            "reflection_id": "..."
        }
        """
        
        if "system_response" in raw_response and "user_response" in raw_response:
            raw_response["reflection_id"] = reflection_id
            return raw_response
        
        system_response = self._extract_system_data(raw_response)
        
        user_message = self._extract_user_message(raw_response)
        
        return {
            "reflection_id": reflection_id,
            "system_response": system_response,
            "user_response": {
                "message": user_message
            }
        }

    def _extract_system_data(self, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract system data from various response formats"""
        system_data = {}

        if "decision" in raw_response:
            system_data["decision"] = raw_response["decision"]
        
        if "send_to_user" in raw_response:
            system_data["send_to_user"] = raw_response["send_to_user"]
        
        for key in ["recipient_name", "relationship", "emotions", "intent"]:
            if key in raw_response:
                system_data[key] = raw_response[key]
        
        # Handle both isValidName and isValid formats
        if "isValidName" in raw_response:
            system_data["is_valid_name"] = "yes" if raw_response["isValidName"] else "no"
            
            if "name" in raw_response:
                system_data["name"] = raw_response["name"]
            if "names" in raw_response:
                system_data["names"] = raw_response["names"]
        elif "isValid" in raw_response:
            system_data["is_valid_name"] = "yes" if raw_response["isValid"] else "no"
            
            if "name" in raw_response:
                system_data["name"] = raw_response["name"]
            if "names" in raw_response:
                system_data["names"] = raw_response["names"]    
        elif "is_valid_name" in raw_response:
            system_data["is_valid_name"] = raw_response["is_valid_name"]

        system_fields = [
            "intent", "confidence", "analysis", "validation", "classification",
            "extracted_data", "metadata", "assessment", "recommendation", "proceed",
            "choice", "confirmation", "user_wants_delivery", "decision", "send_to_user",
            "name", "extracted_name", "recipient_name", "relationship", "emotions", "names"
        ]

        for field in system_fields:
            if field in raw_response and field not in system_data:
                system_data[field] = raw_response[field]
        
        return system_data

    def _extract_user_message(self, raw_response: Dict[str, Any]) -> str:
        """Extract user message from various response formats"""
        
        message_fields = ["reflection", "message", "response", "user_message", "reply", "output"]
        
        for field in message_fields:
            if field in raw_response and raw_response[field]:
                return str(raw_response[field])
        
        return "I hear what you're sharing with me."

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