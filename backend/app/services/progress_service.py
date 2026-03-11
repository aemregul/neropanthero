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
        """Son bilinen ilerleme bilgisini cache'den al."""
        in_memory = self._latest_payloads.get(session_id)
        if isinstance(in_memory, dict):
            return in_memory
        try:
            from app.core.cache import cache
            if not cache.is_connected:
                return None
            payload = await cache.get_json(f"progress:{session_id}")
            return payload if isinstance(payload, dict) else None
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
        message: str
    ):
        """
        Akıllı bilgilendirme mesajı — gerçek chat mesajı olarak.
        
        Progress card'ı ETKİLEMEZ. Chat'e yeni bir asistan mesajı düşürür.
        Mesaj aynı zamanda DB'ye kaydedilir (sayfa yenilenince kaybolmasın).
        """
        import uuid as _uuid

        message_id = None
        # DB'ye gerçek assistant mesajı kaydet
        try:
            from app.core.database import async_session_maker
            from app.models.models import Message as DBMessage

            async with async_session_maker() as db:
                db_msg = DBMessage(
                    session_id=_uuid.UUID(session_id),
                    role="assistant",
                    content=message,
                )
                db.add(db_msg)
                await db.commit()
                await db.refresh(db_msg)
                message_id = str(db_msg.id)
        except Exception as e:
            print(f"⚠️ Reassurance DB kayıt hatası: {e}")
            message_id = str(_uuid.uuid4())

        payload = {
            "type": "reassurance",
            "task_type": task_type,
            "message": message,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        # WebSocket'lere gönder
        if session_id in self._connections:
            dead_connections = []
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead_connections.append(ws)
            for ws in dead_connections:
                self._connections[session_id].remove(ws)

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
        
        if session_id in self._connections:
            for ws in self._connections[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass


# Singleton
progress_service = ProgressService()
