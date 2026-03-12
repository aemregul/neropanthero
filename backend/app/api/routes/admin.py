"""
Admin API Routes - Sistem yönetimi, istatistikler, modeller.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import (
    AIModel, InstalledPlugin, UsageStats, UserSettings, 
    Preset, TrashItem, Session, GeneratedAsset, Message
)


router = APIRouter(prefix="/admin", tags=["Admin"])


# ============== SCHEMAS ==============

class AIModelResponse(BaseModel):
    id: str
    name: str
    display_name: str
    model_type: str
    provider: str
    description: Optional[str]
    icon: str
    is_enabled: bool

class AIModelToggle(BaseModel):
    is_enabled: bool

class InstalledPluginResponse(BaseModel):
    id: str
    plugin_id: str
    name: str
    description: Optional[str]
    icon: str
    category: str
    is_enabled: bool

class InstallPluginRequest(BaseModel):
    plugin_id: str
    name: str
    description: Optional[str]
    icon: str
    category: str
    api_key: Optional[str]

class UserSettingsResponse(BaseModel):
    id: str
    theme: str
    language: str
    notifications_enabled: bool
    auto_save: bool
    default_model: str

class UserSettingsUpdate(BaseModel):
    theme: Optional[str]
    language: Optional[str]
    notifications_enabled: Optional[bool]
    auto_save: Optional[bool]
    default_model: Optional[str]

class UsageStatsResponse(BaseModel):
    date: str
    api_calls: int
    images_generated: int
    videos_generated: int

class PresetCreate(BaseModel):
    name: str
    description: Optional[str]
    icon: str = "✨"
    color: str = "#22c55e"
    system_prompt: Optional[str]
    is_public: bool = False

class PresetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    icon: str
    color: str
    system_prompt: Optional[str]
    is_public: bool
    usage_count: int

class TrashItemResponse(BaseModel):
    id: str
    item_type: str
    item_id: str
    item_name: str
    original_data: Optional[dict] = None
    deleted_at: datetime
    expires_at: datetime

class OverviewStats(BaseModel):
    total_sessions: int
    total_assets: int
    total_messages: int
    active_models: int
    total_images: int = 0
    total_videos: int = 0


# ============== AI MODELS ==============

@router.get("/models", response_model=list[AIModelResponse])
async def list_ai_models(db: AsyncSession = Depends(get_db)):
    """Tüm AI modellerini listele. İlk çağrıda ~38 gerçek modeli seed eder."""
    
    # Tüm modellerin master listesi — her biri gerçekten projede kullanılan model
    MASTER_MODELS = [
        # 🖼️ Görsel Üretim
        ("nano_banana_pro", "Nano Banana Pro", "image", "fal", "Varsayılan görsel üretim — en iyi kalite", "🖼️"),
        ("nano_banana_2", "Nano Banana 2", "image", "fal", "Hızlı görsel üretim — Gemini 3.1 Flash", "⚡"),
        ("flux2", "Flux.2", "image", "fal", "Metin/tipografi render — yazılı görseller", "✍️"),
        ("flux2_max", "Flux 2 Max", "image", "fal", "Ultra detaylı premium görseller", "💎"),
        ("gpt_image", "GPT Image 1", "image", "fal", "Anime/Ghibli/cartoon tarzı görseller", "🎨"),
        ("reve", "Reve", "image", "fal", "Alternatif görsel üretim", "🌟"),
        ("seedream", "Seedream 4.5", "image", "fal", "ByteDance görsel modeli", "🌱"),
        ("recraft", "Recraft V3", "image", "fal", "Vektör tarzı ve illüstrasyon", "📐"),
        ("grok_imagine", "Grok Imagine 1.0", "image", "xai", "xAI görsel üretim — yüksek estetik, hassas metin render", "🧠"),
        
        # 🎨 Görsel Düzenleme
        ("flux_kontext", "Flux Kontext", "edit", "fal", "Akıllı lokal görsel düzenleme", "🎯"),
        ("flux_kontext_pro", "Flux Kontext Pro", "edit", "fal", "Profesyonel görsel düzenleme", "🎯"),
        ("omnigen", "OmniGen V1", "edit", "fal", "Instruction-based düzenleme", "✨"),
        ("flux_inpainting", "Flux Inpainting", "edit", "fal", "Bölgesel dolgu düzenleme", "🖌️"),
        ("object_removal", "Object Removal", "edit", "fal", "Nesne silme", "🗑️"),
        ("outpainting", "Outpainting", "edit", "fal", "Görsel genişletme", "🔲"),
        ("nano_banana_2_edit", "Nano Banana 2 Edit", "edit", "fal", "AI resize + aspect ratio dönüşümü", "📐"),
        
        # 🎬 Video Üretim
        ("kling", "Kling 3.0 Pro", "video", "fal", "Varsayılan video — yüksek kalite", "🎬"),
        ("sora2", "Sora 2 Pro", "video", "fal", "Uzun/hikaye anlatımı videoları", "🎥"),
        ("veo_fast", "Veo 3.1 Fast", "video", "fal", "Hızlı sinematik video", "⚡"),
        ("veo_quality", "Veo 3.1 Quality", "video", "fal", "En yüksek kalite video — premium", "💎"),
        ("veo_google", "Veo 3.1 (Google SDK)", "video", "google", "Google GenAI SDK ile direkt video", "🔷"),
        ("seedance", "Seedance 1.5 Pro", "video", "fal", "ByteDance video modeli", "🌱"),
        ("hailuo", "Hailuo 02", "video", "fal", "Kısa/hızlı sosyal medya videoları", "📱"),
        ("grok_imagine_video", "Grok Imagine Video", "video", "xai", "xAI sinematik video — senkronize ses + fizik simülasyonu", "🧠"),
        
        # 🔧 Araç & Utility
        ("face_swap", "Face Swap", "utility", "fal", "Yüz değiştirme — karakter tutarlılığı", "👤"),
        ("topaz_upscale", "Topaz Upscale", "utility", "fal", "Görsel çözünürlük artırma", "🔍"),
        ("rembg", "Background Removal", "utility", "fal", "Arka plan kaldırma", "✂️"),
        ("style_transfer", "Style Transfer", "utility", "fal", "Sanatsal stil aktarımı", "🎨"),
        
        # 🔊 Ses & Müzik
        ("elevenlabs_tts", "ElevenLabs TTS", "audio", "elevenlabs", "Metin → ses dönüştürme", "🗣️"),
        ("whisper", "Whisper STT", "audio", "openai", "Ses → metin dönüştürme", "🎤"),
        ("mmaudio", "MMAudio (V2A)", "audio", "fal", "Video → ses efekti üretimi", "🔊"),
        ("stable_audio", "Stable Audio", "audio", "fal", "Müzik üretimi", "🎵"),
        ("elevenlabs_sfx", "ElevenLabs SFX", "audio", "elevenlabs", "Ses efekti üretimi", "💥"),
    ]
    
    # Mevcut modelleri çek
    result = await db.execute(select(AIModel))
    existing = {m.name: m for m in result.scalars().all()}
    
    # Eksik modelleri ekle (mevcut modellerin is_enabled durumunu koru)
    master_names = {m[0] for m in MASTER_MODELS}
    added = 0
    for name, display, mtype, provider, desc, icon in MASTER_MODELS:
        if name not in existing:
            db.add(AIModel(
                name=name, display_name=display, model_type=mtype,
                provider=provider, description=desc, icon=icon, is_enabled=True
            ))
            added += 1
    
    # Master listesinde olmayan modelleri kaldır (ör. eski LLM, placeholder)
    removed = 0
    for name, model in existing.items():
        if name not in master_names:
            await db.delete(model)
            removed += 1
    
    if added > 0 or removed > 0:
        await db.commit()
    
    # Tümünü model_type sırasına göre getir
    result = await db.execute(
        select(AIModel).order_by(AIModel.model_type, AIModel.display_name)
    )
    models = result.scalars().all()
    
    return [AIModelResponse(
        id=str(m.id),
        name=m.name,
        display_name=m.display_name,
        model_type=m.model_type,
        provider=m.provider,
        description=m.description,
        icon=m.icon,
        is_enabled=m.is_enabled
    ) for m in models]


@router.patch("/models/{model_id}", response_model=AIModelResponse)
async def toggle_ai_model(
    model_id: UUID,
    data: AIModelToggle,
    db: AsyncSession = Depends(get_db)
):
    """AI modelini aktif/pasif yap."""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model bulunamadı")
    
    model.is_enabled = data.is_enabled
    await db.commit()
    await db.refresh(model)
    
    # Smart router cache'ini invalidate et
    try:
        from app.services.plugins.fal_plugin_v2 import fal_plugin_v2
        fal_plugin_v2.invalidate_model_cache()
    except Exception:
        pass
    
    return AIModelResponse(
        id=str(model.id),
        name=model.name,
        display_name=model.display_name,
        model_type=model.model_type,
        provider=model.provider,
        description=model.description,
        icon=model.icon,
        is_enabled=model.is_enabled
    )


# ============== INSTALLED PLUGINS ==============

@router.get("/plugins/installed", response_model=list[InstalledPluginResponse])
async def list_installed_plugins(db: AsyncSession = Depends(get_db)):
    """Yüklü pluginleri listele."""
    result = await db.execute(select(InstalledPlugin).order_by(InstalledPlugin.installed_at.desc()))
    plugins = result.scalars().all()
    
    # Varsayılan pluginleri ekle
    if not plugins:
        default_plugins = [
            InstalledPlugin(plugin_id="falai", name="fal.ai", description="Hızlı görsel üretimi", icon="🖼️", category="Görsel", is_enabled=True),
            InstalledPlugin(plugin_id="kling", name="Kling 2.5 Video", description="AI video üretimi", icon="🎬", category="Video", is_enabled=True),
        ]
        for plugin in default_plugins:
            db.add(plugin)
        await db.commit()
        
        result = await db.execute(select(InstalledPlugin).order_by(InstalledPlugin.installed_at.desc()))
        plugins = result.scalars().all()
    
    return [InstalledPluginResponse(
        id=str(p.id),
        plugin_id=p.plugin_id,
        name=p.name,
        description=p.description,
        icon=p.icon,
        category=p.category,
        is_enabled=p.is_enabled
    ) for p in plugins]


@router.post("/plugins/install", response_model=InstalledPluginResponse)
async def install_plugin(
    data: InstallPluginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Yeni plugin yükle."""
    plugin = InstalledPlugin(
        plugin_id=data.plugin_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        category=data.category,
        api_key_encrypted=data.api_key,  # Gerçek uygulamada şifrelenecek
        is_enabled=True
    )
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    
    return InstalledPluginResponse(
        id=str(plugin.id),
        plugin_id=plugin.plugin_id,
        name=plugin.name,
        description=plugin.description,
        icon=plugin.icon,
        category=plugin.category,
        is_enabled=plugin.is_enabled
    )


@router.delete("/plugins/{plugin_id}")
async def uninstall_plugin(plugin_id: UUID, db: AsyncSession = Depends(get_db)):
    """Plugin kaldır."""
    result = await db.execute(select(InstalledPlugin).where(InstalledPlugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin bulunamadı")
    
    await db.delete(plugin)
    await db.commit()
    
    return {"success": True, "message": "Plugin kaldırıldı"}


# ============== USER SETTINGS ==============

@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(db: AsyncSession = Depends(get_db)):
    """Kullanıcı ayarlarını getir."""
    result = await db.execute(select(UserSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = UserSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return UserSettingsResponse(
        id=str(settings.id),
        theme=settings.theme,
        language=settings.language,
        notifications_enabled=settings.notifications_enabled,
        auto_save=settings.auto_save,
        default_model=settings.default_model
    )


@router.patch("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    data: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Kullanıcı ayarlarını güncelle."""
    result = await db.execute(select(UserSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = UserSettings()
        db.add(settings)
    
    if data.theme is not None:
        settings.theme = data.theme
    if data.language is not None:
        settings.language = data.language
    if data.notifications_enabled is not None:
        settings.notifications_enabled = data.notifications_enabled
    if data.auto_save is not None:
        settings.auto_save = data.auto_save
    if data.default_model is not None:
        settings.default_model = data.default_model
    
    await db.commit()
    await db.refresh(settings)
    
    return UserSettingsResponse(
        id=str(settings.id),
        theme=settings.theme,
        language=settings.language,
        notifications_enabled=settings.notifications_enabled,
        auto_save=settings.auto_save,
        default_model=settings.default_model
    )


# ============== USAGE STATS ==============

@router.get("/stats/usage", response_model=list[UsageStatsResponse])
async def get_usage_stats(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Son N günün kullanım istatistiklerini getir."""
    start_date = datetime.now() - timedelta(days=days)
    
    result = await db.execute(
        select(UsageStats)
        .where(UsageStats.date >= start_date)
        .order_by(UsageStats.date)
    )
    stats = result.scalars().all()
    
    # Eğer veritabanında veri yoksa, son 7 gün için sıfır değerlerle döndür
    if not stats:
        day_names_tr = {0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"}
        today = datetime.now()
        return [
            UsageStatsResponse(
                date=day_names_tr[(today - timedelta(days=6-i)).weekday()],
                api_calls=0,
                images_generated=0,
                videos_generated=0
            )
            for i in range(7)
        ]
    
    # Aynı güne ait kayıtları grupla ve topla (çift kayıt önle)
    day_names_tr = {0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"}
    from collections import OrderedDict
    daily: OrderedDict[str, dict] = OrderedDict()
    for s in stats:
        date_key = s.date.strftime("%Y-%m-%d")
        day_label = day_names_tr[s.date.weekday()]
        if date_key not in daily:
            daily[date_key] = {"date": day_label, "api_calls": 0, "images_generated": 0, "videos_generated": 0}
        daily[date_key]["api_calls"] += s.api_calls
        daily[date_key]["images_generated"] += s.images_generated
        daily[date_key]["videos_generated"] += s.videos_generated
    
    return [UsageStatsResponse(**d) for d in daily.values()]


@router.get("/stats/overview", response_model=OverviewStats)
async def get_overview_stats(db: AsyncSession = Depends(get_db)):
    """Genel sistem istatistikleri."""
    sessions_count = await db.execute(select(func.count(Session.id)))
    assets_count = await db.execute(select(func.count(GeneratedAsset.id)))
    messages_count = await db.execute(select(func.count(Message.id)))
    models_count = await db.execute(select(func.count(AIModel.id)).where(AIModel.is_enabled == True))
    
    # Görsel ve video sayılarını ayrı ayrı hesapla
    images_count = await db.execute(
        select(func.count(GeneratedAsset.id)).where(GeneratedAsset.asset_type == "image")
    )
    videos_count = await db.execute(
        select(func.count(GeneratedAsset.id)).where(GeneratedAsset.asset_type == "video")
    )
    
    return OverviewStats(
        total_sessions=sessions_count.scalar() or 0,
        total_assets=assets_count.scalar() or 0,
        total_messages=messages_count.scalar() or 0,
        active_models=models_count.scalar() or 0,
        total_images=images_count.scalar() or 0,
        total_videos=videos_count.scalar() or 0
    )


class ModelDistributionItem(BaseModel):
    name: str
    value: int
    color: str


@router.get("/stats/model-distribution", response_model=list[ModelDistributionItem])
async def get_model_distribution(db: AsyncSession = Depends(get_db)):
    """Model kullanım dağılımı - Hangi model ne kadar kullanılmış."""
    
    result = await db.execute(
        select(
            GeneratedAsset.model_name,
            func.count(GeneratedAsset.id).label("count")
        )
        .where(GeneratedAsset.model_name.isnot(None))
        .group_by(GeneratedAsset.model_name)
    )
    
    model_counts = result.all()
    
    # Model adı → display name normalize mapping
    name_normalize: dict[str, str] = {}
    for raw_name in [
        "nano-banana-pro", "nano_banana_pro", "nano-banana", "nano_banana_with_face_swap"
    ]:
        name_normalize[raw_name] = "Nano Banana Pro"
    for raw_name in ["nano-banana-2", "nano_banana_2"]:
        name_normalize[raw_name] = "Nano Banana 2"
    for raw_name in ["flux-dev", "flux-dev-img2img", "flux", "flux2"]:
        name_normalize[raw_name] = "Flux"
    for raw_name in ["flux-kontext", "flux_kontext", "flux_kontext_pro"]:
        name_normalize[raw_name] = "Flux Kontext"
    for raw_name in ["gpt-image-1-mini", "gpt_image"]:
        name_normalize[raw_name] = "GPT Image"
    for raw_name in ["gpt_image_1_edit"]:
        name_normalize[raw_name] = "GPT Image Edit"
    for raw_name in ["nano_banana_pro_edit", "nano-banana-2-edit", "nano_banana_2_edit"]:
        name_normalize[raw_name] = "Nano Edit"
    for raw_name in ["gemini-inpainting", "gemini-2.5-flash"]:
        name_normalize[raw_name] = "Gemini Edit"
    for raw_name in ["kling-3.0-pro", "kling-2.5-turbo", "kling"]:
        name_normalize[raw_name] = "Kling Video"
    for raw_name in ["veo", "veo-3.1", "veo_fast", "veo_quality"]:
        name_normalize[raw_name] = "Veo 3.1"
    for raw_name in ["face-swap", "face_swap"]:
        name_normalize[raw_name] = "Face Swap"
    for raw_name in ["birefnet-v2", "rembg"]:
        name_normalize[raw_name] = "Arka Plan Kaldırma"
    name_normalize.update({
        "reve": "Reve", "seedream": "Seedream", "recraft": "Recraft",
        "omnigen": "OmniGen", "object-removal": "Object Removal",
        "sora2": "Sora 2", "seedance": "Seedance", "hailuo": "Hailuo",
        "ltx-video": "LTX Video", "topaz": "Topaz Upscale",
        "elevenlabs": "ElevenLabs", "stable_audio": "Stable Audio",
        "whisper": "Whisper", "mmaudio": "MMAudio", "ffmpeg-local": "FFmpeg",
        "style_transfer": "Stil Aktarımı",
        # Edge case model adları
        "nano_banana_faceswap": "Nano Banana Pro",
        "nano banana faceswap": "Nano Banana Pro",
        "nano_banana_regen": "Nano Banana Pro",
        "nano banana regen": "Nano Banana Pro",
        "nano_banana+face_swap": "Nano Banana Pro",
        "nano banana+face swap": "Nano Banana Pro",
        "veo_fallback_kling": "Kling Video",
        "veo fallback kling": "Kling Video",
        "flux_kontext_native": "Flux Kontext",
        "flux kontext native": "Flux Kontext",
        "grok_imagine": "Grok Imagine",
        "grok-imagine-image": "Grok Imagine",
        "grok_imagine_video": "Grok Imagine Video",
        "grok-imagine-video": "Grok Imagine Video",
    })
    
    # Gizlenen iç model adları
    hidden = {"user_upload", "unknown", ""}
    
    # Renk haritası (kategori bazlı)
    color_map = {
        "Nano Banana Pro": "#22c55e", "Nano Banana 2": "#16a34a",
        "Flux": "#f59e0b", "Flux Kontext": "#d97706",
        "GPT Image": "#8b5cf6", "GPT Image Edit": "#7c3aed",
        "Reve": "#06b6d4", "Seedream": "#14b8a6", "Recraft": "#ec4899",
        "Nano Edit": "#10b981", "Gemini Edit": "#a855f7",
        "OmniGen": "#6366f1", "Object Removal": "#64748b",
        "Kling Video": "#3b82f6", "Sora 2": "#2563eb",
        "Veo 3.1": "#1d4ed8", "Seedance": "#0ea5e9",
        "Hailuo": "#0284c7", "LTX Video": "#0369a1",
        "Face Swap": "#e11d48", "Topaz Upscale": "#be185d",
        "Arka Plan Kaldırma": "#64748b", "FFmpeg": "#475569",
        "ElevenLabs": "#f97316", "Stable Audio": "#ea580c",
        "Whisper": "#c2410c", "MMAudio": "#9a3412",
        "Stil Aktarımı": "#db2777",
        "Grok Imagine": "#4a4a4a",
        "Grok Imagine Video": "#2d2d2d",
    }
    
    # Normalize et, grupla, topla
    grouped: dict[str, int] = {}
    for model_name, count in model_counts:
        if not model_name or model_name.lower() in hidden:
            continue
        
        display_name = name_normalize.get(model_name.lower())
        if display_name is None:
            display_name = name_normalize.get(model_name)
        if display_name is None:
            # Contains-based fallback (tam endpoint path'leri için)
            ml = model_name.lower()
            if "nano" in ml and "banana" in ml:
                display_name = "Nano Banana Pro"
            elif "kling" in ml:
                display_name = "Kling Video"
            elif "veo" in ml:
                display_name = "Veo 3.1"
            elif "sora" in ml:
                display_name = "Sora 2"
            elif "flux" in ml and "kontext" in ml:
                display_name = "Flux Kontext"
            elif "flux" in ml:
                display_name = "Flux"
            elif "seedance" in ml:
                display_name = "Seedance"
            elif "hailuo" in ml:
                display_name = "Hailuo"
            elif "gemini" in ml:
                display_name = "Gemini Edit"
            elif "face" in ml and "swap" in ml:
                display_name = "Face Swap"
            elif "topaz" in ml:
                display_name = "Topaz Upscale"
            else:
                display_name = model_name.replace("-", " ").replace("_", " ").title()
        
        grouped[display_name] = grouped.get(display_name, 0) + count
    
    # Sırala (en çok kullanılan üstte)
    distribution = []
    for name, count in sorted(grouped.items(), key=lambda x: -x[1]):
        distribution.append(ModelDistributionItem(
            name=name,
            value=count,
            color=color_map.get(name, "#6b7280")
        ))
    
    if not distribution:
        distribution = [
            ModelDistributionItem(name="Nano Banana Pro", value=0, color="#22c55e"),
            ModelDistributionItem(name="Kling Video", value=0, color="#3b82f6"),
            ModelDistributionItem(name="Flux", value=0, color="#f59e0b"),
        ]
    
    return distribution


# ============== CREATIVE PLUGINS ==============

@router.get("/presets", response_model=list[PresetResponse])
async def list_presets(
    session_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """Kullanıcı tanımlı creative pluginleri listele."""
    query = select(Preset)
    if session_id:
        query = query.where(Preset.session_id == session_id)
    query = query.order_by(Preset.created_at.desc())
    
    result = await db.execute(query)
    plugins = result.scalars().all()
    
    return [PresetResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        icon=p.icon,
        color=p.color,
        system_prompt=p.system_prompt,
        is_public=p.is_public,
        usage_count=p.usage_count
    ) for p in plugins]


@router.post("/presets", response_model=PresetResponse)
async def create_preset(
    data: PresetCreate,
    session_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """Yeni creative plugin oluştur."""
    plugin = Preset(
        session_id=session_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        color=data.color,
        system_prompt=data.system_prompt,
        is_public=data.is_public
    )
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    
    return PresetResponse(
        id=str(plugin.id),
        name=plugin.name,
        description=plugin.description,
        icon=plugin.icon,
        color=plugin.color,
        system_prompt=plugin.system_prompt,
        is_public=plugin.is_public,
        usage_count=plugin.usage_count
    )


@router.delete("/presets/{plugin_id}")
async def delete_preset(plugin_id: UUID, db: AsyncSession = Depends(get_db)):
    """Creative plugin'i çöp kutusuna taşı."""
    result = await db.execute(select(Preset).where(Preset.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="Preset bulunamadı")
    
    # TrashItem oluştur
    trash_item = TrashItem(
        user_id=plugin.user_id,
        session_id=plugin.session_id,
        item_type="preset",
        item_id=str(plugin.id),
        item_name=plugin.name,
        original_data={
            "description": plugin.description,
            "icon": plugin.icon,
            "color": plugin.color,
            "system_prompt": plugin.system_prompt,
            "is_public": plugin.is_public,
            "usage_count": plugin.usage_count,
            "config": plugin.config,
        },
        expires_at=datetime.now() + timedelta(days=3)
    )
    db.add(trash_item)
    
    await db.delete(plugin)
    await db.commit()
    
    return {"success": True, "message": "Preset çöp kutusuna taşındı"}


# ============== MARKETPLACE ==============

class MarketplacePluginItem(BaseModel):
    id: str
    name: str
    description: str
    author: str
    icon: str
    color: str
    style: str
    rating: float
    downloads: int
    created_at: str
    source: str  # "official" veya "community"
    config: dict
    is_installed: bool = False

# Resmi (seed) marketplace pluginleri  
MARKETPLACE_SEED_PLUGINS = [
    # === SANAT & YARATICI ===
    {"id": "mp_fantasy", "name": "Digital Art Fantasy", "description": "Fantastik dijital sanat. Ejderhalar, büyücüler, efsanevi dünyalar.", "author": "PepperRoot Studio", "icon": "🐉", "color": "#8b5cf6", "style": "Fantasy Art", "rating": 4.9, "downloads": 4500, "created_at": "2025-10-15",
     "config": {"promptTemplate": "digital fantasy art, epic, magical, detailed, {character}", "cameraAngles": ["Epic Wide", "Character Portrait", "Action Scene"], "timeOfDay": "Magical"}},
    {"id": "mp_anime", "name": "Anime & Manga Style", "description": "Studio Ghibli, Makoto Shinkai tarzı anime karakter ve sahne üretimi.", "author": "PepperRoot Studio", "icon": "🎌", "color": "#ec4899", "style": "Anime", "rating": 4.8, "downloads": 3450, "created_at": "2025-09-20",
     "config": {"promptTemplate": "anime style, detailed, vibrant colors, studio ghibli inspired, {character}", "cameraAngles": ["Anime", "Portrait", "Action Pose"], "timeOfDay": "Sunset"}},
    {"id": "mp_watercolor", "name": "Watercolor Illustration", "description": "Sulu boya tarzı illüstrasyonlar. Yumuşak, organik, sanatsal.", "author": "PepperRoot Studio", "icon": "🎨", "color": "#06b6d4", "style": "Watercolor", "rating": 4.7, "downloads": 1230, "created_at": "2026-01-15",
     "config": {"promptTemplate": "watercolor illustration, soft colors, artistic, organic texture, {character}", "cameraAngles": ["Portrait", "Landscape", "Still Life"], "timeOfDay": "Soft"}},
    {"id": "mp_synthwave", "name": "Retro 80s Synthwave", "description": "80'ler retro synthwave estetiği. Neon, grid, güneş batımı.", "author": "PepperRoot Studio", "icon": "🌆", "color": "#f59e0b", "style": "Synthwave", "rating": 4.8, "downloads": 2340, "created_at": "2026-02-02",
     "config": {"promptTemplate": "synthwave aesthetic, 80s retro, neon colors, grid, sunset, {character}", "cameraAngles": ["Wide Horizon", "Neon Portrait", "Car Chase"], "timeOfDay": "Sunset"}},
    {"id": "mp_cyberpunk", "name": "Cyberpunk 2077 Style", "description": "Neon ışıklar, fütüristik şehir, cyberpunk estetiği.", "author": "PepperRoot Studio", "icon": "🌃", "color": "#a855f7", "style": "Cyberpunk", "rating": 4.7, "downloads": 1280, "created_at": "2026-02-03",
     "config": {"promptTemplate": "cyberpunk aesthetic, neon lights, futuristic, {character}", "cameraAngles": ["Cyberpunk", "Neon Portrait", "Street Scene"], "timeOfDay": "Night"}},
    {"id": "mp_vintage", "name": "Vintage Film Look", "description": "80'ler ve 90'lar film estetiği. Grain, fade, nostaljik renkler.", "author": "PepperRoot Studio", "icon": "📷", "color": "#78716c", "style": "Vintage", "rating": 4.6, "downloads": 890, "created_at": "2026-02-02",
     "config": {"promptTemplate": "vintage film aesthetic, 80s style, grain, nostalgic, {character}", "cameraAngles": ["Vintage", "Film Look", "Nostalgic"], "timeOfDay": "Warm"}},
    {"id": "mp_horror", "name": "Horror & Dark Fantasy", "description": "Korku ve karanlık fantezi temalı atmosferik görseller.", "author": "PepperRoot Studio", "icon": "👻", "color": "#1e293b", "style": "Horror", "rating": 4.6, "downloads": 1670, "created_at": "2026-01-28",
     "config": {"promptTemplate": "horror art, dark fantasy, atmospheric, eerie, haunting, {character}", "cameraAngles": ["Atmospheric", "Creature Reveal", "Suspense"], "timeOfDay": "Night"}},
    {"id": "mp_scifi", "name": "Sci-Fi & Space", "description": "Bilim kurgu ve uzay temalı futuristik görseller.", "author": "PepperRoot Studio", "icon": "🚀", "color": "#3b82f6", "style": "Sci-Fi", "rating": 4.9, "downloads": 2890, "created_at": "2026-02-03",
     "config": {"promptTemplate": "science fiction art, space, futuristic, cosmic, epic scale, {character}", "cameraAngles": ["Space Vista", "Ship Design", "Planet View"], "timeOfDay": "Cosmic"}},

    # === SOSYAL MEDYA ===
    {"id": "mp_instagram", "name": "Instagram Influencer Pack", "description": "Instagram için estetik içerik. Lifestyle, selfie, flat lay.", "author": "PepperRoot Studio", "icon": "📱", "color": "#e11d48", "style": "Instagram", "rating": 4.9, "downloads": 4200, "created_at": "2025-11-01",
     "config": {"promptTemplate": "instagram aesthetic, lifestyle, vibrant, trendy, {character}", "cameraAngles": ["Instagram", "Selfie Style", "Flat Lay"], "timeOfDay": "Golden Hour"}},
    {"id": "mp_youtube", "name": "YouTube Thumbnail Pro", "description": "Yüksek CTR için dikkat çekici YouTube thumbnail tasarımları.", "author": "PepperRoot Studio", "icon": "▶️", "color": "#ef4444", "style": "YouTube", "rating": 4.8, "downloads": 2890, "created_at": "2025-12-15",
     "config": {"promptTemplate": "youtube thumbnail, expressive, bold colors, eye-catching, {character}", "cameraAngles": ["YouTube", "Face Reaction", "Dramatic"], "timeOfDay": "Bright"}},
    {"id": "mp_podcast", "name": "Podcast Cover Art", "description": "Podcast kapak görselleri ve sosyal medya tanıtımları.", "author": "PepperRoot Studio", "icon": "🎙️", "color": "#7c3aed", "style": "Podcast", "rating": 4.5, "downloads": 560, "created_at": "2026-02-03",
     "config": {"promptTemplate": "podcast cover art, professional, engaging, personal brand, {character}", "cameraAngles": ["Portrait", "Microphone Shot", "Graphic Style"], "timeOfDay": "Moody"}},

    # === İŞ & TİCARET ===
    {"id": "mp_ecommerce", "name": "E-Commerce Product Shots", "description": "Online mağaza için ürün fotoğrafları. Beyaz arka plan, soft shadows.", "author": "PepperRoot Studio", "icon": "🛒", "color": "#22c55e", "style": "Commercial", "rating": 4.7, "downloads": 1890, "created_at": "2025-10-20",
     "config": {"promptTemplate": "product photography, white background, professional lighting", "cameraAngles": ["E-Commerce", "Front View", "45 Degree"], "timeOfDay": "Studio Light"}},
    {"id": "mp_video_ad", "name": "Video Reklam Paketi", "description": "Sosyal medya video reklamları için hazır şablonlar.", "author": "PepperRoot Studio", "icon": "🎬", "color": "#f97316", "style": "Commercial Video", "rating": 4.7, "downloads": 2100, "created_at": "2025-11-20",
     "config": {"promptTemplate": "video advertisement, product showcase, engaging, {character}", "cameraAngles": ["Commercial", "Product Hero", "Lifestyle"], "timeOfDay": "Bright"}},
    {"id": "mp_startup", "name": "Tech Startup Visuals", "description": "Teknoloji startup'ları için modern ve futuristik görseller.", "author": "PepperRoot Studio", "icon": "💡", "color": "#0ea5e9", "style": "Tech", "rating": 4.6, "downloads": 780, "created_at": "2026-02-04",
     "config": {"promptTemplate": "technology, futuristic, innovative, clean design, startup, {character}", "cameraAngles": ["Product Feature", "In Use", "Abstract Tech"], "timeOfDay": "Blue Hour"}},
    {"id": "mp_fintech", "name": "Fintech & Banking", "description": "Fintech ve bankacılık için modern, güvenilir görseller.", "author": "PepperRoot Studio", "icon": "💳", "color": "#14b8a6", "style": "Fintech", "rating": 4.6, "downloads": 780, "created_at": "2026-01-30",
     "config": {"promptTemplate": "fintech design, modern, trustworthy, clean, professional, digital banking, {character}", "cameraAngles": ["Data Visualization", "App Interface", "Trust Shot"], "timeOfDay": "Professional"}},
    {"id": "mp_crypto", "name": "Crypto & Blockchain", "description": "Kripto para ve blockchain projeleri için futuristik görseller.", "author": "PepperRoot Studio", "icon": "₿", "color": "#f59e0b", "style": "Crypto", "rating": 4.7, "downloads": 1890, "created_at": "2026-02-02",
     "config": {"promptTemplate": "cryptocurrency design, blockchain, futuristic, neon, digital, {character}", "cameraAngles": ["Abstract", "Network Visual", "Coin Hero"], "timeOfDay": "Neon"}},

    # === FOTOĞRAFÇILIK ===
    {"id": "mp_wedding", "name": "Wedding Photography", "description": "Düğün fotoğrafçılığı için romantik ve duygusal anlar.", "author": "PepperRoot Studio", "icon": "💒", "color": "#fbbf24", "style": "Romantic", "rating": 4.9, "downloads": 2100, "created_at": "2025-08-22",
     "config": {"promptTemplate": "wedding photography, romantic, emotional, {character}", "cameraAngles": ["Romantic", "Couple Portrait", "Candid Moment"], "timeOfDay": "Golden Hour"}},
    {"id": "mp_portrait", "name": "AI Portrait Studio", "description": "Profesyonel portre stüdyosu. Headshot, CV fotoğrafları.", "author": "PepperRoot Studio", "icon": "🤳", "color": "#6366f1", "style": "Professional", "rating": 4.5, "downloads": 450, "created_at": "2026-02-04",
     "config": {"promptTemplate": "professional headshot, clean background, confident, {character}", "cameraAngles": ["Headshot", "Professional", "LinkedIn"], "timeOfDay": "Studio"}},
    {"id": "mp_sports", "name": "Sports Action Shots", "description": "Spor ve aksiyon fotoğrafçılığı. Dinamik hareketler.", "author": "PepperRoot Studio", "icon": "⚽", "color": "#ef4444", "style": "Sports", "rating": 4.7, "downloads": 890, "created_at": "2025-09-18",
     "config": {"promptTemplate": "sports photography, action, dynamic, powerful, {character}", "cameraAngles": ["Sports", "Action Freeze", "Wide Arena"], "timeOfDay": "Day"}},
    {"id": "mp_travel", "name": "Travel Photography", "description": "Seyahat ve turizm için etkileyici destinasyon fotoğrafları.", "author": "PepperRoot Studio", "icon": "✈️", "color": "#0284c7", "style": "Travel", "rating": 4.8, "downloads": 2100, "created_at": "2026-01-20",
     "config": {"promptTemplate": "travel photography, wanderlust, beautiful destination, inspiring, {character}", "cameraAngles": ["Landscape Wide", "Detail Shot", "Human Element"], "timeOfDay": "Golden Hour"}},
    {"id": "mp_pet", "name": "Pet Photography Pro", "description": "Evcil hayvan fotoğrafçılığı için eğlenceli ve sevimli kareler.", "author": "PepperRoot Studio", "icon": "🐾", "color": "#f97316", "style": "Pet", "rating": 4.9, "downloads": 2200, "created_at": "2026-02-01",
     "config": {"promptTemplate": "pet photography, adorable, playful, expressive, {character}", "cameraAngles": ["Portrait", "Action", "Funny Moment"], "timeOfDay": "Bright"}},
    {"id": "mp_newborn", "name": "Newborn & Baby Photos", "description": "Yeni doğan ve bebek fotoğrafçılığı için yumuşak tonlar.", "author": "PepperRoot Studio", "icon": "👶", "color": "#fda4af", "style": "Newborn", "rating": 4.9, "downloads": 1340, "created_at": "2026-01-18",
     "config": {"promptTemplate": "newborn photography, soft, gentle, warm tones, precious moments, {character}", "cameraAngles": ["Close-up", "With Parent", "Sleeping"], "timeOfDay": "Soft Natural"}},
    {"id": "mp_family", "name": "Family Portrait Sessions", "description": "Aile portreleri için doğal ve samimi anlar.", "author": "PepperRoot Studio", "icon": "👨‍👩‍👧‍👦", "color": "#16a34a", "style": "Family", "rating": 4.7, "downloads": 980, "created_at": "2026-01-25",
     "config": {"promptTemplate": "family photography, warm, loving, natural, candid moments, {character}", "cameraAngles": ["Group Portrait", "Candid Moment", "Playful"], "timeOfDay": "Golden Hour"}},

    # === MODA & GÜZELLİK ===
    {"id": "mp_fashion", "name": "Fashion Lookbook", "description": "Moda markaları için lookbook ve katalog çekimleri.", "author": "PepperRoot Studio", "icon": "👗", "color": "#ec4899", "style": "Fashion Editorial", "rating": 4.8, "downloads": 1340, "created_at": "2025-12-01",
     "config": {"promptTemplate": "fashion photography, editorial, high fashion, {character}", "cameraAngles": ["Fashion", "Full Body", "Detail Close-up"], "timeOfDay": "Soft Light"}},
    {"id": "mp_beauty", "name": "Beauty & Cosmetics", "description": "Kozmetik ürünleri ve güzellik içerikleri için glamour çekimler.", "author": "PepperRoot Studio", "icon": "💄", "color": "#f472b6", "style": "Beauty", "rating": 4.8, "downloads": 1670, "created_at": "2026-01-30",
     "config": {"promptTemplate": "beauty photography, glamorous, elegant, cosmetics, flawless, {character}", "cameraAngles": ["Product Close-up", "Application Shot", "Model Portrait"], "timeOfDay": "Soft Light"}},
    {"id": "mp_jewelry", "name": "Jewelry & Accessories", "description": "Takı ve aksesuar için detaylı makro çekimler.", "author": "PepperRoot Studio", "icon": "💎", "color": "#d97706", "style": "Jewelry", "rating": 4.7, "downloads": 920, "created_at": "2026-01-25",
     "config": {"promptTemplate": "jewelry photography, luxury, detailed, elegant, precious, {character}", "cameraAngles": ["Macro Detail", "On Model", "Artistic"], "timeOfDay": "Studio"}},

    # === OYUN & ENTERTAİNMENT ===
    {"id": "mp_game", "name": "Game Character Design", "description": "Video oyun karakterleri için konsept sanatı.", "author": "PepperRoot Studio", "icon": "🎮", "color": "#8b5cf6", "style": "Game Art", "rating": 4.9, "downloads": 3200, "created_at": "2026-01-22",
     "config": {"promptTemplate": "game character design, detailed, dynamic, concept art, {character}", "cameraAngles": ["Character Sheet", "Action Pose", "Portrait"], "timeOfDay": "Dramatic"}},
    {"id": "mp_gameui", "name": "Mobile Game UI", "description": "Mobil oyunlar için renkli ve eğlenceli UI elementleri.", "author": "PepperRoot Studio", "icon": "📲", "color": "#10b981", "style": "Game UI", "rating": 4.7, "downloads": 1450, "created_at": "2026-02-01",
     "config": {"promptTemplate": "mobile game UI, colorful, playful, engaging, cartoon style, {character}", "cameraAngles": ["Button", "Icon", "Screen Layout"], "timeOfDay": "Vibrant"}},
    {"id": "mp_nft", "name": "NFT Collection Art", "description": "NFT koleksiyonları için unique dijital sanat eserleri.", "author": "PepperRoot Studio", "icon": "🖼️", "color": "#7c3aed", "style": "NFT Art", "rating": 4.7, "downloads": 3100, "created_at": "2026-02-04",
     "config": {"promptTemplate": "NFT art, unique, collectible, digital art, distinctive style, {character}", "cameraAngles": ["Character Portrait", "Full Body", "Trait Variations"], "timeOfDay": "Vibrant"}},

    # === DİĞER ===
    {"id": "mp_3d", "name": "3D Product Render", "description": "Ürün için fotorealistik 3D renderlar. Stüdyo kalitesinde.", "author": "PepperRoot Studio", "icon": "🎲", "color": "#0ea5e9", "style": "3D Render", "rating": 4.8, "downloads": 1120, "created_at": "2026-02-04",
     "config": {"promptTemplate": "3d product render, photorealistic, studio lighting, professional, {character}", "cameraAngles": ["Hero Shot", "Exploded View", "Material Detail"], "timeOfDay": "Studio"}},
    {"id": "mp_elearning", "name": "E-Learning Course Visuals", "description": "Online kurslar için eğitici görseller ve illüstrasyonlar.", "author": "PepperRoot Studio", "icon": "📚", "color": "#2563eb", "style": "Educational", "rating": 4.6, "downloads": 890, "created_at": "2026-02-03",
     "config": {"promptTemplate": "educational illustration, clean, informative, friendly, modern design, {character}", "cameraAngles": ["Infographic", "Diagram", "Character Explain"], "timeOfDay": "Bright"}},
    {"id": "mp_children", "name": "Children's Book Illustration", "description": "Çocuk kitapları için sevimli ve eğlenceli illüstrasyonlar.", "author": "PepperRoot Studio", "icon": "🧸", "color": "#fbbf24", "style": "Children's Book", "rating": 4.9, "downloads": 1560, "created_at": "2026-01-28",
     "config": {"promptTemplate": "children's book illustration, cute, colorful, whimsical, friendly, {character}", "cameraAngles": ["Character Focus", "Scene Wide", "Action Moment"], "timeOfDay": "Colorful"}},
    {"id": "mp_medical", "name": "Medical & Healthcare", "description": "Sağlık sektörü için profesyonel tıbbi görseller.", "author": "PepperRoot Studio", "icon": "🏥", "color": "#0d9488", "style": "Medical", "rating": 4.5, "downloads": 670, "created_at": "2026-01-25",
     "config": {"promptTemplate": "medical photography, healthcare, professional, clean, trustworthy, {character}", "cameraAngles": ["Clinical", "Caring", "Professional"], "timeOfDay": "Clean Light"}},
    {"id": "mp_yoga", "name": "Yoga & Meditation", "description": "Yoga ve meditasyon için huzurlu, zen görseller.", "author": "PepperRoot Studio", "icon": "🧘", "color": "#a78bfa", "style": "Zen", "rating": 4.8, "downloads": 1120, "created_at": "2026-02-01",
     "config": {"promptTemplate": "yoga photography, peaceful, serene, natural light, mindfulness, {character}", "cameraAngles": ["Full Body Flow", "Close Focus", "Environment"], "timeOfDay": "Soft Morning"}},
    {"id": "mp_fitness", "name": "Gym & Fitness Marketing", "description": "Spor salonları ve fitness markaları için enerjik görseller.", "author": "PepperRoot Studio", "icon": "💪", "color": "#dc2626", "style": "Fitness", "rating": 4.7, "downloads": 1450, "created_at": "2026-01-28",
     "config": {"promptTemplate": "fitness photography, powerful, energetic, motivational, athletic, {character}", "cameraAngles": ["Action Shot", "Equipment Focus", "Motivation"], "timeOfDay": "Dramatic"}},
    {"id": "mp_arch", "name": "Architectural Visualization", "description": "Mimari projeler için fotorealistik 3D görselleştirmeler.", "author": "PepperRoot Studio", "icon": "🏗️", "color": "#475569", "style": "Architectural", "rating": 4.8, "downloads": 1120, "created_at": "2026-02-03",
     "config": {"promptTemplate": "architectural visualization, photorealistic, modern design, {character}", "cameraAngles": ["Exterior Hero", "Interior Space", "Detail"], "timeOfDay": "Blue Hour"}},
    {"id": "mp_album", "name": "Album Cover Art", "description": "Albüm kapakları için yaratıcı ve dikkat çekici tasarımlar.", "author": "PepperRoot Studio", "icon": "💿", "color": "#be185d", "style": "Album Art", "rating": 4.8, "downloads": 2560, "created_at": "2026-01-22",
     "config": {"promptTemplate": "album cover art, creative, eye-catching, artistic, memorable, {character}", "cameraAngles": ["Square Format", "Visual Metaphor", "Typography Ready"], "timeOfDay": "Artistic"}},
    {"id": "mp_movie", "name": "Movie Poster Design", "description": "Film ve dizi posterleri için sinematik kompozisyonlar.", "author": "PepperRoot Studio", "icon": "🎥", "color": "#1e293b", "style": "Movie Poster", "rating": 4.9, "downloads": 1890, "created_at": "2026-02-01",
     "config": {"promptTemplate": "movie poster design, cinematic, dramatic, compelling, theatrical, {character}", "cameraAngles": ["Hero Poster", "Character Ensemble", "Teaser"], "timeOfDay": "Dramatic"}},
    {"id": "mp_documentary", "name": "Documentary Style", "description": "Belgesel ve gerçekçi hikaye anlatımı için görsel stil.", "author": "PepperRoot Studio", "icon": "📹", "color": "#64748b", "style": "Documentary", "rating": 4.5, "downloads": 670, "created_at": "2026-01-28",
     "config": {"promptTemplate": "documentary photography, authentic, real, storytelling, human interest, {character}", "cameraAngles": ["Candid", "Environmental Portrait", "Detail"], "timeOfDay": "Natural"}},
    {"id": "mp_hotel", "name": "Hotel & Resort Marketing", "description": "Otel ve resort tanıtımı için lüks konaklama görselleri.", "author": "PepperRoot Studio", "icon": "🏨", "color": "#0369a1", "style": "Hospitality", "rating": 4.6, "downloads": 760, "created_at": "2026-01-28",
     "config": {"promptTemplate": "luxury hotel photography, elegant, inviting, high-end resort, relaxing atmosphere", "cameraAngles": ["Room Interior", "Pool View", "Dining Experience"], "timeOfDay": "Warm Afternoon"}},
    {"id": "mp_nature", "name": "Environmental & Nature", "description": "Çevre ve doğa koruma projeleri için etkileyici görseller.", "author": "PepperRoot Studio", "icon": "🌿", "color": "#16a34a", "style": "Nature", "rating": 4.9, "downloads": 1450, "created_at": "2026-01-20",
     "config": {"promptTemplate": "nature photography, environmental, majestic, conservation, beauty of earth, {character}", "cameraAngles": ["Landscape", "Wildlife", "Environmental Impact"], "timeOfDay": "Golden Hour"}},
]


@router.get("/marketplace/plugins", response_model=list[MarketplacePluginItem])
async def get_marketplace_plugins(
    sort: str = "downloads",  # downloads, rating, recent
    category: str = "all",     # all, community
    search: str = "",
    db: AsyncSession = Depends(get_db)
):
    """Marketplace pluginlerini getir — resmi + topluluk."""
    all_plugins: list[dict] = []
    
    # 1. Resmi (seed) pluginler
    if category in ("all", "official"):
        for sp in MARKETPLACE_SEED_PLUGINS:
            all_plugins.append({**sp, "source": "official", "is_installed": False})
    
    # 2. Topluluk (kullanıcı oluşturmuş, public)
    if category in ("all", "community"):
        result = await db.execute(
            select(Preset).where(Preset.is_public == True)
        )
        user_plugins = result.scalars().all()
        for p in user_plugins:
            config = p.config or {}
            all_plugins.append({
                "id": str(p.id),
                "name": p.name,
                "description": p.description or "",
                "author": config.get("author", "Topluluk Üyesi"),
                "icon": p.icon,
                "color": p.color,
                "style": config.get("style", "Custom"),
                "rating": config.get("rating", 4.0),
                "downloads": p.usage_count,
                "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else "2026-01-01",
                "source": "community",
                "config": config,
                "is_installed": False,
            })
    
    # Arama filtresi
    if search:
        search_lower = search.lower()
        all_plugins = [
            p for p in all_plugins
            if search_lower in p["name"].lower()
            or search_lower in p["description"].lower()
            or search_lower in p.get("style", "").lower()
            or search_lower in p.get("author", "").lower()
        ]
    
    # Sıralama
    if sort == "rating":
        all_plugins.sort(key=lambda x: x.get("rating", 0), reverse=True)
    elif sort == "recent":
        all_plugins.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    else:  # downloads (default)
        all_plugins.sort(key=lambda x: x.get("downloads", 0), reverse=True)
    
    return all_plugins


@router.patch("/presets/{plugin_id}/publish")
async def publish_plugin(plugin_id: UUID, db: AsyncSession = Depends(get_db)):
    """Kullanıcı pluginini marketplace'e yayınla."""
    result = await db.execute(select(Preset).where(Preset.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin bulunamadı")
    
    plugin.is_public = not plugin.is_public
    await db.commit()
    
    if plugin.is_public:
        return {"success": True, "message": f"'{plugin.name}' toplulukta yayınlandı!"}
    else:
        return {"success": True, "message": f"'{plugin.name}' yayından kaldırıldı."}


class InstallPluginRequest(BaseModel):
    session_id: str  # Hedef proje ID'si

@router.post("/marketplace/plugins/{plugin_id}/install")
async def install_marketplace_plugin(
    plugin_id: str, 
    request: InstallPluginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Marketplace pluginini belirli bir projeye yükle. Duplicate kontrolü yapar."""
    target_session_id = request.session_id
    
    # Duplicate kontrolü — bu session'da aynı isimli/kaynaklı plugin var mı?
    try:
        target_uuid = UUID(target_session_id)
        existing_result = await db.execute(
            select(Preset).where(
                Preset.session_id == target_uuid
            )
        )
        existing_plugins = existing_result.scalars().all()
    except (ValueError, AttributeError):
        existing_plugins = []
    
    # Kaynak plugin bilgisini al
    source_plugin = None
    source_name = None
    source_config = {}
    
    try:
        uid = UUID(plugin_id)
        result = await db.execute(select(Preset).where(Preset.id == uid))
        source_plugin = result.scalar_one_or_none()
        if source_plugin:
            source_name = source_plugin.name
            source_config = source_plugin.config or {}
    except (ValueError, AttributeError):
        pass
    
    # Seed plugin mi?
    if not source_plugin:
        seed_match = next((sp for sp in MARKETPLACE_SEED_PLUGINS if sp["id"] == plugin_id), None)
        if seed_match:
            source_name = seed_match["name"]
            source_config = seed_match.get("config", {})
        else:
            raise HTTPException(status_code=404, detail="Plugin bulunamadı")
    
    # Duplicate check by name
    if any(p.name == source_name for p in existing_plugins):
        return {"success": False, "error": "already_installed", "message": f"'{source_name}' bu projede zaten ekli."}
    
    # İndirme sayacını artır (community plugins)
    if source_plugin:
        source_plugin.usage_count += 1
    
    # Plugin'i hedef session'a kopyala
    installed_plugin = Preset(
        session_id=target_uuid,
        user_id=source_plugin.user_id if source_plugin else None,
        name=source_name,
        description=source_plugin.description if source_plugin else (next((sp.get("description", "") for sp in MARKETPLACE_SEED_PLUGINS if sp["id"] == plugin_id), "")),
        icon=source_plugin.icon if source_plugin else "🧩",
        color=source_plugin.color if source_plugin else "#22c55e",
        system_prompt=source_plugin.system_prompt if source_plugin else source_config.get("promptTemplate", ""),
        is_public=False,  # Yüklenen kopya public değil
        config=source_config
    )
    db.add(installed_plugin)
    await db.commit()
    await db.refresh(installed_plugin)
    
    return {"success": True, "plugin_id": str(installed_plugin.id), "installed_name": source_name}

@router.get("/trash", response_model=list[TrashItemResponse])
async def list_trash_items(db: AsyncSession = Depends(get_db)):
    """Çöp kutusundaki öğeleri listele."""
    result = await db.execute(
        select(TrashItem)
        .where(TrashItem.expires_at > datetime.now())
        .order_by(TrashItem.deleted_at.desc())
    )
    items = result.scalars().all()
    
    return [TrashItemResponse(
        id=str(i.id),
        item_type=i.item_type,
        item_id=i.item_id,
        item_name=i.item_name,
        original_data=i.original_data,
        deleted_at=i.deleted_at,
        expires_at=i.expires_at
    ) for i in items]


@router.post("/trash/{item_id}/restore")
async def restore_trash_item(item_id: UUID, db: AsyncSession = Depends(get_db)):
    """Çöpteki öğeyi geri yükle."""
    result = await db.execute(select(TrashItem).where(TrashItem.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Öğe bulunamadı")
    
    original_data = item.original_data or {}
    item_type = item.item_type
    restored_item = None
    
    try:
        # Session (proje) geri yükleme
        if item_type == "session":
            from uuid import UUID as UUIDType
            session_result = await db.execute(
                select(Session).where(Session.id == UUIDType(item.item_id))
            )
            session = session_result.scalar_one_or_none()
            if session:
                session.is_active = True
                restored_item = {"type": "session", "id": str(session.id), "title": session.title}
            else:
                # Session tamamen silinmişse yeniden oluştur
                new_session = Session(
                    id=UUIDType(item.item_id),
                    user_id=UUIDType(original_data.get("user_id")) if original_data.get("user_id") else None,
                    title=original_data.get("title", "Restored Project"),
                    is_active=True
                )
                db.add(new_session)
                restored_item = {"type": "session", "id": str(new_session.id), "title": new_session.title}
        
        # Entity (karakter, lokasyon, marka) geri yükleme
        elif item_type in ["character", "location", "brand"]:
            from app.models.models import Entity
            new_entity = Entity(
                user_id=item.user_id,
                session_id=None,  # Session bağımsız olarak geri yükle
                entity_type=original_data.get("entity_type", item_type),
                name=item.item_name,
                tag=original_data.get("tag", f"@{item.item_name.lower().replace(' ', '_')}"),
                description=original_data.get("description"),
                attributes=original_data.get("attributes", {}),
                reference_image_url=original_data.get("reference_image_url")
            )
            db.add(new_entity)
            await db.flush()
            restored_item = {"type": item_type, "id": str(new_entity.id), "name": new_entity.name, "tag": new_entity.tag}
        
        # Asset geri yükleme
        elif item_type == "asset":
            from app.models.models import GeneratedAsset
            from uuid import UUID as UUIDType
            new_asset = GeneratedAsset(
                session_id=UUIDType(original_data.get("session_id")) if original_data.get("session_id") else None,
                asset_type=original_data.get("type", "image"),
                url=original_data.get("url", ""),
                prompt=original_data.get("prompt"),
                model_name=original_data.get("model_name")
            )
            db.add(new_asset)
            await db.flush()
            restored_item = {"type": "asset", "id": str(new_asset.id), "url": new_asset.url}
        
        # Preset geri yükleme
        elif item_type == "preset":
            new_plugin = Preset(
                user_id=item.user_id,
                session_id=item.session_id,
                name=item.item_name,
                description=original_data.get("description"),
                icon=original_data.get("icon", "🧩"),
                color=original_data.get("color", "#22c55e"),
                system_prompt=original_data.get("system_prompt"),
                is_public=original_data.get("is_public", False),
                usage_count=original_data.get("usage_count", 0),
                config=original_data.get("config", {})
            )
            db.add(new_plugin)
            await db.flush()
            restored_item = {"type": "preset", "id": str(new_plugin.id), "name": new_plugin.name}
        
        else:
            # Bilinmeyen tip - sadece çöpten sil
            restored_item = {"type": item_type, "data": original_data}
        
        # TrashItem'ı sil
        await db.delete(item)
        await db.commit()
        
        return {"success": True, "message": f"{item_type} başarıyla geri yüklendi!", "restored": restored_item}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Geri yükleme hatası: {str(e)}")


@router.delete("/trash/{item_id}")
async def permanent_delete_trash_item(item_id: UUID, db: AsyncSession = Depends(get_db)):
    """Öğeyi kalıcı olarak sil."""
    result = await db.execute(select(TrashItem).where(TrashItem.id == item_id))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Öğe bulunamadı")
    
    await db.delete(item)
    await db.commit()
    
    return {"success": True, "message": "Öğe kalıcı olarak silindi"}
