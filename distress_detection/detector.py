# =======================================================================
# distress_detection/detector.py (Final Correction)
# =======================================================================
from __future__ import annotations
import asyncio
import logging
from typing import Optional, TYPE_CHECKING  # <-- Import TYPE_CHECKING
from openai import AsyncOpenAI
from pinecone import Pinecone
from .keywords import block_list

# This block is only processed by type-checkers, not when the code runs.
# This prevents the circular import error at runtime.
if TYPE_CHECKING:
    from config import DistressConfig

class DistressDetector:
    """Distress detection using a hybrid of word-based and vector search."""
    
    # Now we can use the actual type hint without causing a runtime error
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
        if not message or not message.strip():
            return 0

        message_words = set(message.lower().split())
        for block_word in block_list:
            if block_word in message_words:
                self.logger.warning(f"CRITICAL distress detected by word-based search: found '{block_word}'")
                return 1 # Critical

        try:
            embedding = await self._get_embedding(message)
            result = await asyncio.to_thread(self._query_pinecone, embedding)
            
            if not result or not result.matches:
                return 0
            
            match = result.matches[0]
            confidence = float(match.score)
            category = match.metadata.get("category", "")
            
            if category == "red" and confidence >= self.config.red_threshold:
                return 1
            elif category == "yellow" and confidence >= self.config.yellow_threshold:
                return 2
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Distress detection failed: {str(e)}")
            return 0

_detector: Optional[DistressDetector] = None

async def get_detector(config: DistressConfig, openai_api_key: str) -> DistressDetector:
    global _detector
    if _detector is None:
        _detector = DistressDetector(config, openai_api_key)
    return _detector