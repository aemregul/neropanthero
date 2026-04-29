"""
Redis Cache Service for Nero Panthero AI Studio.
Provides caching for sessions, entities, and AI responses.
"""
import json
from typing import Optional, Any
from datetime import timedelta

import redis.asyncio as redis
from app.core.config import settings


class RedisCache:
    """Redis-based cache service."""
    
    _instance: Optional["RedisCache"] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self):
        """Connect to Redis."""
        if not settings.USE_REDIS or not settings.REDIS_URL:
            return False
        
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._client.ping()
            print("✅ Redis bağlantısı başarılı")
            return True
        except Exception as e:
            print(f"❌ Redis bağlantı hatası: {e}")
            self._client = None
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def is_connected(self) -> bool:
        return self._client is not None
    
    # ============== BASIC OPERATIONS ==============
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set key-value with optional TTL (seconds)."""
        if not self._client:
            return False
        try:
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False
    
    # ============== JSON OPERATIONS ==============
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set JSON value."""
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, ttl)
        except (TypeError, ValueError):
            return False
    
    # ============== SESSION CACHE ==============
    
    async def cache_session(self, session_id: str, data: dict, ttl: int = 3600):
        """Cache session data (1 hour default)."""
        key = f"session:{session_id}"
        return await self.set_json(key, data, ttl)
    
    async def get_cached_session(self, session_id: str) -> Optional[dict]:
        """Get cached session."""
        key = f"session:{session_id}"
        return await self.get_json(key)
    
    async def invalidate_session(self, session_id: str):
        """Invalidate session cache."""
        key = f"session:{session_id}"
        await self.delete(key)
    
    # ============== ENTITY CACHE ==============
    
    async def cache_entities(self, user_id: str, entities: list, ttl: int = 1800):
        """Cache user's entities (30 min default)."""
        key = f"entities:{user_id}"
        return await self.set_json(key, entities, ttl)
    
    async def get_cached_entities(self, user_id: str) -> Optional[list]:
        """Get cached entities."""
        key = f"entities:{user_id}"
        return await self.get_json(key)
    
    async def invalidate_entities(self, user_id: str):
        """Invalidate entity cache."""
        key = f"entities:{user_id}"
        await self.delete(key)
    
    # ============== AI RESPONSE CACHE ==============
    
    async def cache_ai_response(
        self, 
        prompt_hash: str, 
        response: str, 
        ttl: int = 86400  # 24 hours
    ):
        """Cache AI response for similar prompts."""
        key = f"ai_response:{prompt_hash}"
        return await self.set(key, response, ttl)
    
    async def get_cached_ai_response(self, prompt_hash: str) -> Optional[str]:
        """Get cached AI response."""
        key = f"ai_response:{prompt_hash}"
        return await self.get(key)
    
    # ============== RATE LIMITING ==============
    
    async def check_rate_limit(
        self, 
        user_id: str, 
        limit: int = 100, 
        window: int = 3600
    ) -> tuple[bool, int]:
        """Check if user is within rate limit. Returns (allowed, remaining)."""
        if not self._client:
            return True, limit
        
        key = f"rate_limit:{user_id}"
        try:
            current = await self._client.get(key)
            if current is None:
                await self._client.setex(key, window, "1")
                return True, limit - 1
            
            count = int(current)
            if count >= limit:
                return False, 0
            
            await self._client.incr(key)
            return True, limit - count - 1
        except Exception:
            return True, limit
    
    # ============== CONVERSATION MEMORY ==============
    
    async def cache_conversation_summary(
        self, 
        session_id: str, 
        summary: str, 
        ttl: int = 86400  # 24 saat
    ) -> bool:
        """
        Konuşma özetini cache'le.
        Uzun konuşmalar için hafıza yönetimi.
        """
        key = f"conv_summary:{session_id}"
        return await self.set(key, summary, ttl)
    
    async def get_conversation_summary(self, session_id: str) -> Optional[str]:
        """Konuşma özetini al."""
        key = f"conv_summary:{session_id}"
        return await self.get(key)
    
    async def cache_context(
        self, 
        session_id: str, 
        context: dict, 
        ttl: int = 3600  # 1 saat
    ) -> bool:
        """
        Session context'ini cache'le.
        Mevcut entity'ler, tercihler, son işlemler vb.
        """
        key = f"context:{session_id}"
        return await self.set_json(key, context, ttl)
    
    async def get_context(self, session_id: str) -> Optional[dict]:
        """Session context'ini al."""
        key = f"context:{session_id}"
        return await self.get_json(key)
    
    async def update_context(self, session_id: str, updates: dict) -> bool:
        """
        Context'i güncelle (mevcut değerleri koruyarak).
        """
        current = await self.get_context(session_id) or {}
        current.update(updates)
        return await self.cache_context(session_id, current)
    
    # ============== WORKING MEMORY (Kısa Vadeli) ==============
    
    async def set_working_memory(
        self, 
        session_id: str, 
        key: str, 
        value: Any, 
        ttl: int = 1800  # 30 dakika
    ) -> bool:
        """
        Çalışma belleği - kısa vadeli bilgi saklama.
        Örn: Son üretilen görselin URL'si, mevcut görev, vb.
        """
        cache_key = f"working:{session_id}:{key}"
        return await self.set_json(cache_key, value, ttl)
    
    async def get_working_memory(self, session_id: str, key: str) -> Optional[Any]:
        """Çalışma belleğinden değer al."""
        cache_key = f"working:{session_id}:{key}"
        return await self.get_json(cache_key)
    
    async def clear_working_memory(self, session_id: str) -> bool:
        """Session'ın tüm çalışma belleğini temizle."""
        if not self._client:
            return False
        try:
            pattern = f"working:{session_id}:*"
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._client.delete(*keys)
            return True
        except Exception:
            return False
    
    # ============== LAST ACTIONS HISTORY ==============
    
    async def push_action(
        self, 
        session_id: str, 
        action: dict, 
        max_actions: int = 20
    ) -> bool:
        """
        Son işlemleri kaydet (LIFO stack).
        Undo/redo ve context için kullanılır.
        """
        key = f"actions:{session_id}"
        try:
            # Mevcut aksiyonları al
            actions = await self.get_json(key) or []
            
            # Yeni aksiyonu başa ekle
            actions.insert(0, action)
            
            # Max limit aş
            if len(actions) > max_actions:
                actions = actions[:max_actions]
            
            return await self.set_json(key, actions, ttl=86400)  # 24 saat
        except Exception:
            return False
    
    async def get_recent_actions(
        self, 
        session_id: str, 
        count: int = 5
    ) -> list:
        """Son N aksiyonu al."""
        key = f"actions:{session_id}"
        actions = await self.get_json(key) or []
        return actions[:count]
    
    async def pop_last_action(self, session_id: str) -> Optional[dict]:
        """Son aksiyonu al ve listeden çıkar (undo için)."""
        key = f"actions:{session_id}"
        actions = await self.get_json(key) or []
        if not actions:
            return None
        
        last_action = actions.pop(0)
        await self.set_json(key, actions, ttl=86400)
        return last_action


# Singleton instance
cache = RedisCache()


async def get_cache() -> RedisCache:
    """Dependency for getting cache instance."""
    return cache

