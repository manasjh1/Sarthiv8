import os
import asyncio
import logging
from enum import Enum
from typing import Optional
from openai import AsyncOpenAI
from pinecone import Pinecone
from config import DistressConfig
from .keywords import block_list # Import the new block_list

class DistressDetector:
    """Distress detection using a hybrid of word-based and vector search."""
    
    def __init__(self, config: DistressConfig, openai_api_key: str):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.openai_client = AsyncOpenAI(api_key=openai_api_key, timeout=10.0)
        self.pc = Pinecone(api_key=self.config.pinecone_api_key)
        self.index = self.pc.Index(self.config.pinecone_index)
        
        self.logger.info(f"DistressDetector initialized for index '{self.config.pinecone_index}'")

    async def _get_embedding(self, text: str) -> list[float]:
        response = await self.openai_client.embeddings.create(
            model=self.config.openai_embed_model,
            input=text.strip()
        )
        return response.data[0].embedding

    def _query_pinecone(self, embedding: list[float]):
        return self.index.query(
            vector=embedding,
            top_k=1,
            include_metadata=True,
            namespace=self.config.pinecone_namespace
        )

    async def check(self, message: str) -> int:
        """
        Checks a message for distress using a hybrid approach.
        """
        if not message or not message.strip():
            return 0

        # --- 1. Word-Based Search (Safety Net) ---
        # CORRECTED LOGIC: Split the message into words and check if any word is in the block_list.
        message_words = set(message.lower().split())
        for block_word in block_list:
            if block_word in message_words:
                self.logger.warning(f"CRITICAL distress detected by word-based search: found '{block_word}'")
                return 1 # Critical

        # --- 2. Vector-Based Search (Semantic) ---
        try:
            embedding = await self._get_embedding(message)
            result = await asyncio.to_thread(self._query_pinecone, embedding)
            
            if not result or not result.matches:
                return 0
            
            match = result.matches[0]
            confidence = float(match.score)
            category = match.metadata.get("category", "")
            
            if category == "red" and confidence >= self.config.red_threshold:
                return 1 # Critical
            elif category == "yellow" and confidence >= self.config.yellow_threshold:
                return 2 # Warning
            
            return 0 # Safe
            
        except Exception as e:
            self.logger.error(f"Distress detection failed: {str(e)}")
            return 0 # Fail-safe

# --- Singleton pattern for easy access ---
_detector: Optional[DistressDetector] = None

async def get_detector(config: DistressConfig, openai_api_key: str) -> DistressDetector:
    global _detector
    if _detector is None:
        _detector = DistressDetector(config, openai_api_key)
    return _detector