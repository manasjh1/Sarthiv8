import asyncpg
import logging
from typing import Optional
from .models import PromptData
from .exceptions import DatabaseError, StageNotFoundError


class AsyncDatabaseManager:
    """Async database manager for Supabase operations"""
    
    def __init__(self, connection_string: str, max_pool_size: int = 10, min_pool_size: int = 2, timeout: int = 30):
        """
        Initialize database manager
        
        Args:
            connection_string: Supabase connection string
            max_pool_size: Maximum pool connections
            min_pool_size: Minimum pool connections  
            timeout: Connection timeout in seconds
        """
        self.connection_string = connection_string
        self.max_pool_size = max_pool_size
        self.min_pool_size = min_pool_size
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._pool: Optional[asyncpg.Pool] = None
        
        # Cache for AWAITING_EMOTION stage ID
        self._awaiting_emotion_stage_id: Optional[int] = None
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self._pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=self.timeout,
                statement_cache_size=0  # Disable prepared statements for Supabase
            )
            self.logger.info("Database pool initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize database pool: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    async def close(self):
        """Close database connection pool"""
        if self._pool:
            await self._pool.close()
            self.logger.info("Database pool closed")
    
    async def get_prompt_by_stage_id(self, stage_id: int, flow_type: Optional[str] = None) -> PromptData:
        """
        Fetch prompt data by stage ID
        
        Args:
            stage_id: Stage ID to fetch
            flow_type: Optional flow type for filtering
            
        Returns:
            PromptData object
            
        Raises:
            StageNotFoundError: If stage not found
            DatabaseError: If database operation fails
        """
        if not self._pool:
            raise DatabaseError("Database not initialized")
        
        query = """
        SELECT prompt_id, flow_type, stage_id, is_static, prompt_type, 
               prompt_name, prompt, next_stage, status
        FROM prompt_table 
        WHERE stage_id = $1 AND status = 1
        """
        params = [stage_id]
        
        # Add flow_type filter if provided
        if flow_type:
            query += " AND (flow_type = $2 OR flow_type IS NULL)"
            params.append(flow_type)
        
        query += " ORDER BY flow_type NULLS LAST LIMIT 1"
        
        try:
            async with self._pool.acquire() as connection:
                result = await connection.fetchrow(query, *params)
                
                if not result:
                    raise StageNotFoundError(f"No prompt found for stage_id: {stage_id}")
                
                return PromptData(
                    prompt_id=result['prompt_id'],
                    flow_type=result['flow_type'],
                    stage_id=result['stage_id'],
                    is_static=result['is_static'],
                    prompt_type=result['prompt_type'],
                    prompt_name=result['prompt_name'],
                    prompt=result['prompt'],
                    next_stage=result['next_stage'],
                    status=result['status']
                )
        except asyncpg.PostgresError as e:
            self.logger.error(f"Database query error: {e}")
            raise DatabaseError(f"Failed to fetch prompt: {e}")
    
    async def get_awaiting_emotion_stage_id(self) -> int:
        """
        Get the stage ID for AWAITING_EMOTION stage with caching
        
        Returns:
            Stage ID for AWAITING_EMOTION
            
        Raises:
            StageNotFoundError: If AWAITING_EMOTION stage not found
        """
        if self._awaiting_emotion_stage_id is not None:
            return self._awaiting_emotion_stage_id
        
        if not self._pool:
            raise DatabaseError("Database not initialized")
        
        query = """
        SELECT stage_id 
        FROM prompt_table 
        WHERE prompt_name = $1 AND status = 1
        LIMIT 1
        """
        
        try:
            async with self._pool.acquire() as connection:
                result = await connection.fetchval(query, 'AWAITING_EMOTION')
                
                if result is None:
                    raise StageNotFoundError("AWAITING_EMOTION stage not found")
                
                self._awaiting_emotion_stage_id = result
                return result
                
        except asyncpg.PostgresError as e:
            self.logger.error(f"Database query error: {e}")
            raise DatabaseError(f"Failed to fetch AWAITING_EMOTION stage: {e}")
