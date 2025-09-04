from __future__ import annotations
import asyncio
import logging
from typing import Optional, TYPE_CHECKING
from openai import AsyncOpenAI
from pinecone import Pinecone
from .keywords import block_list

if TYPE_CHECKING:
    from config import DistressConfig

class DistressDetector:
    """Distress detection using a hybrid of phrase-based and vector search."""
    
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

        message_lower = message.lower()
        self.logger.info(f" DISTRESS CHECK: '{message}'")

        # STEP 1: Phrase-based detection (for exact threats)
        for block_phrase in block_list:
            if block_phrase in message_lower:
                self.logger.warning(f" CRITICAL distress detected by phrase search: found '{block_phrase}'")
                return 1  # Critical

        self.logger.info(f" No phrase match found, checking vector search...")

        # STEP 2: Vector-based detection (for semantic similarity)
        try:
            embedding = await self._get_embedding(message)
            result = await asyncio.to_thread(self._query_pinecone, embedding)
            
            self.logger.info(f" Pinecone query completed")
            
            if not result or not result.matches:
                self.logger.info(f" No Pinecone matches found")
                return 0
            
            match = result.matches[0]
            confidence = float(match.score)
            category = match.metadata.get("category", "")
            matched_text = match.metadata.get("text", "")
            
            self.logger.info(f" Best match: score={confidence:.3f}, category={category}, text='{matched_text}'")
            
            if category == "red" and confidence >= self.config.red_threshold:
                self.logger.warning(f" CRITICAL distress detected by vector search: {confidence:.3f} >= {self.config.red_threshold}")
                return 1
            elif category == "yellow" and confidence >= self.config.yellow_threshold:
                self.logger.warning(f" WARNING distress detected by vector search: {confidence:.3f} >= {self.config.yellow_threshold}")
                return 2
            else:
                self.logger.info(f" Below thresholds: {confidence:.3f} < red({self.config.red_threshold}) and yellow({self.config.yellow_threshold})")
            
            return 0
            
        except Exception as e:
            self.logger.error(f" Vector search failed: {str(e)}")
            return 0

_detector: Optional[DistressDetector] = None

async def get_detector(config: DistressConfig, openai_api_key: str) -> DistressDetector:
    global _detector
    if _detector is None:
        _detector = DistressDetector(config, openai_api_key)
    return _detector