"""
Real-Time Progress Service — WebSocket + Redis Pub/Sub.

Uzun süren işlemler (long video, batch campaign) için 
gerçek zamanlı ilerleme bildirimi.
"""
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from app.services.user_error_formatter import format_user_error_message


class ProgressService:
    """Gerçek zamanlı ilerleme takip servisi."""
    
    _instance: Optional["ProgressService"] = None
    _connections: Dict[str, list] = {}  # session_id → [websocket connections]
    _latest_payloads: Dict[str, Dict[str, Any]] = {}  # session_id → son payload
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._connections = {}
            cls._latest_payloads = {}
        return cls._instance
    
    def register(self, session_id: str, websocket):
        """WebSocket bağlantısı kaydet."""
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        print(f"🔌 WebSocket bağlandı: session={session_id[:8]}... (toplam: {len(self._connections[session_id])})")
    
    def unregister(self, session_id: str, websocket):
        """WebSocket bağlantısı kaldır."""
        if session_id in self._connections:
            self._connections[session_id] = [
                ws for ws in self._connections[session_id] if ws != websocket
            ]
            if not self._connections[session_id]:
                del self._connections[session_id]
        print(f"🔌 WebSocket ayrıldı: session={session_id[:8]}...")
    
    async def send_progress(
        self,
        session_id: str,
        task_type: str,
        progress: float,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        İlerleme bildirimi gönder.
        
        Args:
            session_id: Session ID
            task_type: İşlem tipi (long_video, campaign, quality_check)
            progress: 0.0 - 1.0 arası ilerleme
            message: Kullanıcıya gösterilecek mesaj
            details: Ek bilgiler (opsiyonel)
        """
        payload = {
            "type": "progress",
            "task_type": task_type,
            "progress": round(progress, 2),
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self._latest_payloads[session_id] = payload
        
        # Redis pub/sub ile yayınla
        try:
            from app.core.cache import cache
            if cache.is_connected:
                await cache.set(
                    f"progress:{session_id}",
                    json.dumps(payload),
                    ttl=300  # 5 dakika
                )
        except Exception:
            pass
        
        # Doğrudan WebSocket'lere gönder
        if session_id in self._connections:
            dead_connections = []
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead_connections.append(ws)
            
            # Ölü bağlantıları temizle
            for ws in dead_connections:
                self._connections[session_id].remove(ws)

    async def get_cached_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Son bilinen ilerleme bilgisini cache'den al.
        
        Stale guard: 10 dakikadan eski progress payload'ları yok sayılır.
        Sadece 'progress' tipi payload'lar döndürülür (complete/error değil).
        """
        from datetime import timezone
        
        def _is_stale(payload: dict, max_age_seconds: int = 600) -> bool:
            """Payload 10 dakikadan eski mi?"""
            ts = payload.get("timestamp")
            if not ts:
                return True  # timestamp yoksa stale kabul et
            try:
                payload_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                if payload_time.tzinfo is None:
                    payload_time = payload_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                return (now - payload_time).total_seconds() > max_age_seconds
            except Exception:
                return True  # parse edilemezse stale kabul et
        
        def _is_valid_progress(payload: dict) -> bool:
            """Sadece aktif progress payload'larını kabul et."""
            return (
                isinstance(payload, dict)
                and payload.get("type") == "progress"
                and not _is_stale(payload)
            )
        
        in_memory = self._latest_payloads.get(session_id)
        if _is_valid_progress(in_memory):
            return in_memory
        elif isinstance(in_memory, dict) and _is_stale(in_memory):
            # Stale in-memory payload'ı temizle
            self._latest_payloads.pop(session_id, None)
        
        try:
            from app.core.cache import cache
            if not cache.is_connected:
                return None
            payload = await cache.get_json(f"progress:{session_id}")
            if _is_valid_progress(payload):
                return payload
            elif isinstance(payload, dict) and _is_stale(payload):
                # Stale Redis cache'i temizle
                await cache.delete(f"progress:{session_id}")
            return None
        except Exception:
            return None
    
    async def send_complete(
        self,
        session_id: str,
        task_type: str,
        result: Dict[str, Any]
    ):
        """İşlem tamamlandı bildirimi."""
        payload = {
            "type": "complete",
            "task_type": task_type,
            "progress": 1.0,
            "message": "Tamamlandı!",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._latest_payloads.pop(session_id, None)
        
        if session_id in self._connections:
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass
        
        # Cache temizle
        try:
            from app.core.cache import cache
            if cache.is_connected:
                await cache.delete(f"progress:{session_id}")
        except Exception:
            pass
    
    async def send_reassurance(
        self,
        session_id: str,
        task_type: str,
        message: str,
        completed_scenes: int = 0,
        total_scenes: int = 0
    ):
        """
        Production card bilgilendirme mesajı — geçici, DB'ye yazılmaz.
        
        Mesaj frontend'de production card içinde mini-log'da gösterilir.
        Card kaybolunca mesajlar da kaybolur.
        """
        import uuid as _uuid

        payload = {
            "type": "reassurance",
            "task_type": task_type,
            "message": message,
            "message_id": str(_uuid.uuid4()),
            "completed_scenes": completed_scenes,
            "total_scenes": total_scenes,
            "timestamp": datetime.utcnow().isoformat()
        }

        # WebSocket'lere gönder
        conn_count = len(self._connections.get(session_id, []))
        print(f"💬 [Reassurance] session={session_id[:8]}... | connections={conn_count} | msg={message[:60]}...")
        
        if session_id in self._connections:
            dead_connections = []
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                    print(f"✅ [Reassurance] WebSocket gönderildi: {session_id[:8]}...")
                except Exception as ws_err:
                    print(f"❌ [Reassurance] WebSocket gönderim hatası: {ws_err}")
                    dead_connections.append(ws)
            for ws in dead_connections:
                self._connections[session_id].remove(ws)
        else:
            print(f"⚠️ [Reassurance] session_id={session_id[:8]}... için aktif WebSocket bağlantısı YOK!")
            print(f"   Mevcut bağlantılar: {[k[:8] for k in self._connections.keys()]}")

    async def send_error(
        self,
        session_id: str,
        task_type: str,
        error: str
    ):
        """Hata bildirimi."""
        payload = {
            "type": "error",
            "task_type": task_type,
            "progress": 0,
            "message": format_user_error_message(error, task_type),
            "timestamp": datetime.utcnow().isoformat()
        }
        self._latest_payloads.pop(session_id, None)
        
        # Redis cache'i de temizle — stale progress card'ları önle
        try:
            from app.core.cache import cache
            if cache.is_connected:
                await cache.delete(f"progress:{session_id}")
        except Exception:
            pass
        
        if session_id in self._connections:
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass


# Singleton
progress_service = ProgressService()
