"""
Pepper Root AI Agency - Ana uygulama.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.cache import cache
from app.api.routes import sessions, chat, generate, entities, upload, plugins, admin, grid, auth, system, search, ws
from app.services.plugins.plugin_loader import initialize_plugins


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.APP_NAME} başlatılıyor...")
    
    # Veritabanı tablolarını oluştur (SQLite için özellikle gerekli)
    try:
        from app.core.database import engine, Base
        from app.models import models  # tüm modelleri import et
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("   ✅ Veritabanı tabloları hazır")
    except Exception as e:
        print(f"   ⚠️ Tablo oluşturma hatası: {e}")
    
    # Pluginleri yükle
    initialize_plugins()
    
    # Redis bağlantısı (REDIS_URL varsa otomatik aktif)
    if settings.redis_enabled:
        redis_connected = await cache.connect()
        if redis_connected:
            print("   ✅ Redis cache aktif")
        else:
            print("   ⚠️ Redis bağlanılamadı, cache devre dışı")
    else:
        print("   ℹ️ Redis cache devre dışı (USE_REDIS=false)")
    
    # Warm-up: API key kontrolü
    api_status = []
    if settings.ANTHROPIC_API_KEY:
        api_status.append("✅ Anthropic")
    else:
        api_status.append("❌ Anthropic (ANTHROPIC_API_KEY eksik)")
    
    if settings.OPENAI_API_KEY:
        api_status.append("✅ OpenAI (GPT-4)")
    else:
        api_status.append("⚠️ OpenAI (opsiyonel)")
    
    if settings.FAL_KEY:
        api_status.append("✅ fal.ai")
    else:
        api_status.append("❌ fal.ai (FAL_KEY eksik)")
    
    if settings.GOOGLE_CLIENT_ID:
        api_status.append("✅ Google OAuth")
    else:
        api_status.append("⚠️ Google OAuth (opsiyonel)")
    
    print(f"📋 API Durumu:")
    for status in api_status:
        print(f"   {status}")
    
    # Süresi dolan çöp öğelerini temizle
    try:
        from app.core.database import async_session_maker
        from app.models.models import TrashItem
        from sqlalchemy import select, delete
        from datetime import datetime, timezone
        
        async with async_session_maker() as db:
            expired_count = await db.execute(
                delete(TrashItem).where(TrashItem.expires_at < datetime.now(timezone.utc))
            )
            await db.commit()
            deleted = expired_count.rowcount
            if deleted > 0:
                print(f"   🗑️ {deleted} süresi dolmuş çöp öğesi temizlendi")
            else:
                print(f"   ✅ Çöp kutusu temiz")
    except Exception as e:
        print(f"   ⚠️ Çöp temizleme hatası: {e}")
    
    print(f"✅ {settings.APP_NAME} hazır!")
    
    # ⚠️ SECRET_KEY güvenlik uyarısı
    if settings.SECRET_KEY == "CHANGE-ME-IN-PRODUCTION":
        print(f"   ⚠️ UYARI: SECRET_KEY varsayılan değerde! .env dosyasında güvenli bir anahtar belirleyin.")
    
    yield
    
    # === GRACEFUL SHUTDOWN (QUEUE DEGRADATION) ===
    print(f"⏳ {settings.APP_NAME} duraklatılıyor. Devam eden arka plan görevleri bekleniyor...")
    try:
        from app.services.agent.orchestrator import _GLOBAL_BG_TASKS
        import asyncio
        
        pending = [t for t in _GLOBAL_BG_TASKS if not t.done()]
        if pending:
            print(f"   ⚠️ Lütfen bekleyin! Devam eden {len(pending)} adet uzun video / yapay zeka jenerasyonu var.")
            print(f"   ⏳ Veri kaybını önlemek için sonlandırılmaları bekleniyor (maks. 5 dakika)...")
            
            # 5 dakika (300 saniye) boyunca bitmelerini bekle
            done, pending_after_timeout = await asyncio.wait(pending, timeout=300)
            
            if pending_after_timeout:
                print(f"   ❌ {len(pending_after_timeout)} görev 5 dakika içinde tamamlanamadı ve iptal ediliyor!")
                for t in pending_after_timeout:
                    t.cancel()
            else:
                print(f"   ✅ Tüm arka plan üretimleri başarıyla tamamlandı ve kaydedildi.")
        else:
            print("   ✅ Bekleyen arka plan görevi yok.")
    except ImportError:
         print("   ℹ️ Arka plan görev yöneticisi bulunamadı.")
    except Exception as e:
         print(f"   ⚠️ Kapanış sırasında arka plan görev hatası (gözardı ediliyor): {e}")
    # ==========================================

    # Cleanup
    if cache.is_connected:
        await cache.disconnect()
        print("   Redis bağlantısı kapatıldı")
    print(f"👋 {settings.APP_NAME} kapatılıyor...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — origins from env
allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting — DEVRE DIŞI (production sorunlarına neden oldu)
# from app.core.rate_limit import RateLimitMiddleware
# app.add_middleware(RateLimitMiddleware, general_limit=60, ai_limit=10, auth_limit=20)

# Monitoring — DEVRE DIŞI (production sorunlarına neden oldu)
# from app.core.monitoring import MonitoringMiddleware
# app.add_middleware(MonitoringMiddleware, slow_threshold_ms=5000)

# API Route'ları
app.include_router(auth.router, prefix=settings.API_PREFIX)  # Auth first
app.include_router(sessions.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)
app.include_router(entities.router, prefix=settings.API_PREFIX)
app.include_router(upload.router, prefix=settings.API_PREFIX)
app.include_router(plugins.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(grid.router, prefix=settings.API_PREFIX)
app.include_router(system.router, prefix=settings.API_PREFIX)
app.include_router(search.router, prefix=settings.API_PREFIX)
app.include_router(generate.router, prefix=f"{settings.API_PREFIX}/generate")
app.include_router(ws.router)  # WebSocket (no prefix)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    return {
        "message": f"Hoş geldiniz! {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
        "plugins": "/api/v1/plugins",
    }

