"""
fal.ai Plugin V2 - Yeni plugin sistemine uyumlu fal.ai adapter.

Bu plugin PluginBase'den türetilir ve plugin_loader tarafından yönetilir.

V3 Upgrade (17 Şubat 2026):
- Smart Model Router: İstek tipine göre en iyi modeli otomatik seç
- Auto-Retry Fallback: Başarısız olursa alternatif modelle dene
- FLUX 2 Flex: Metin/tipografi render için
- FLUX Kontext: Akıllı lokal görsel düzenleme
- Veo 3.1: Google'ın en kaliteli video modeli
- Outpainting: Görseli genişletme
- Style Transfer: Sanatsal stil uygulama
"""
import os
import time
import asyncio
import logging
from typing import Optional, Any
import fal_client

from app.core.config import settings
from app.services.plugins.plugin_base import (
    PluginBase, PluginInfo, PluginResult, PluginCategory
)
from app.services.plugins.fal_models import ALL_MODELS, ModelCategory as FalModelCategory

logger = logging.getLogger(__name__)


class FalPluginV2(PluginBase):
    """
    fal.ai Plugin - Görsel ve video üretim servisi.
    
    Özellikler:
    - 25+ AI modeli (görsel, video, upscale, edit)
    - Akıllı model seçimi
    - Yüz tutarlılığı (face swap)
    """
    
    # Endpoint → DB model name mapping (admin toggle ile eşleştirme)
    ENDPOINT_TO_DB_NAME = {
        # Görsel
        "fal-ai/nano-banana-pro": "nano_banana_pro",
        "fal-ai/nano-banana-2": "nano_banana_2",
        "fal-ai/flux-2": "flux2",
        "fal-ai/flux-2-max": "flux2_max",
        "fal-ai/gpt-image-1-mini": "gpt_image",
        "fal-ai/reve/text-to-image": "reve",
        "fal-ai/bytedance/seedream/v4.5/text-to-image": "seedream",
        "fal-ai/recraft/v3/text-to-image": "recraft",
        "xai/grok-imagine-image": "grok_imagine",
        # Edit
        "fal-ai/flux-kontext": "flux_kontext",
        "fal-ai/flux-pro/kontext": "flux_kontext_pro",
        "fal-ai/omnigen-v1": "omnigen",
        "fal-ai/flux-general/inpainting": "flux_inpainting",
        "fal-ai/object-removal": "object_removal",
        "fal-ai/image-apps-v2/outpaint": "outpainting",
        "fal-ai/nano-banana-2/edit": "nano_banana_2_edit",
        # Video (i2v + t2v endpoints → tek DB name)
        "fal-ai/kling-video/v3/pro/image-to-video": "kling",
        "fal-ai/kling-video/v3/pro/text-to-video": "kling",
        "fal-ai/sora-2/image-to-video/pro": "sora2",
        "fal-ai/sora-2/text-to-video/pro": "sora2",
        "fal-ai/veo3.1/fast/image-to-video": "veo_fast",
        "fal-ai/veo3.1/fast": "veo_fast",
        "fal-ai/veo3.1/image-to-video": "veo_quality",
        "fal-ai/veo3.1": "veo_quality",
        "fal-ai/bytedance/seedance/v1.5/pro/image-to-video": "seedance",
        "fal-ai/bytedance/seedance/v1.5/pro/fast/text-to-video": "seedance",
        "fal-ai/minimax/hailuo-02/standard/image-to-video": "hailuo",
        "fal-ai/minimax/hailuo-02/standard/text-to-video": "hailuo",
        "xai/grok-imagine-video/text-to-video": "grok_imagine_video",
        "xai/grok-imagine-video/image-to-video": "grok_imagine_video",
        # Utility
        "fal-ai/face-swap": "face_swap",
        "fal-ai/topaz": "topaz_upscale",
        "fal-ai/imageutils/rembg": "rembg",
        "fal-ai/image-apps-v2/style-transfer": "style_transfer",
    }
    
    # Shortcode → DB name mapping (IMAGE/VIDEO MAP key → DB name)
    SHORTCODE_TO_DB_NAME = {
        "nano_banana": "nano_banana_pro",
        "nano_banana_2": "nano_banana_2",
        "flux2": "flux2",
        "flux2_max": "flux2_max",
        "gpt_image": "gpt_image",
        "reve": "reve",
        "seedream": "seedream",
        "recraft": "recraft",
        "grok_imagine": "grok_imagine",
        "kling": "kling",
        "sora2": "sora2",
        "veo": "veo_fast",
        "veo_quality": "veo_quality",
        "seedance": "seedance",
        "hailuo": "hailuo",
        "grok_imagine_video": "grok_imagine_video",
    }
    
    def __init__(self):
        super().__init__()
        
        # API key ayarla
        if settings.FAL_KEY:
            os.environ["FAL_KEY"] = settings.FAL_KEY
        
        # Model enabled/disabled cache (30s TTL)
        self._enabled_models_cache: dict[str, bool] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 30.0  # 30 saniye
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="fal_ai",
            display_name="fal.ai",
            version="3.0.0",
            description="Görsel ve video üretimi için fal.ai AI modelleri (Smart Router + Auto-Retry)",
            category=PluginCategory.IMAGE_GENERATION,
            author="Pepper Root",
            requires_api_key=True,
            api_key_env_var="FAL_KEY",
            capabilities=[
                "image_generation",
                "video_generation",
                "image_editing",
                "video_editing",
                "upscaling",
                "face_swap",
                "background_removal",
                "outpainting",
                "style_transfer",
            ],
            config_schema={
                "default_model": {"type": "string", "default": "fal-ai/nano-banana-pro"},
                "default_resolution": {"type": "string", "default": "1K"},
            }
        )
    
    def get_available_actions(self) -> list[str]:
        return [
            "generate_image",
            "generate_video",
            "edit_video",
            "edit_image",
            "upscale_image",
            "upscale_video",
            "remove_background",
            "face_swap",
            "smart_generate_with_face",
            "outpaint_image",
            "apply_style",
            "text_to_speech",
            "video_to_audio",
            "resize_image",
        ]
    
    async def execute(self, action: str, params: dict) -> PluginResult:
        """
        Ana çalışma metodu - action'a göre ilgili fonksiyonu çağır.
        """
        start_time = time.time()
        
        if not self.is_enabled:
            return PluginResult(
                success=False,
                error="Plugin devre dışı"
            )
        
        # Parametre doğrulama
        valid, error = self.validate_params(action, params)
        if not valid:
            return PluginResult(success=False, error=error)
        
        try:
            # Action'a göre yönlendir
            if action == "generate_image":
                result = await self._generate_image(params)
            elif action == "generate_video":
                result = await self._generate_video(params)
            elif action == "edit_video":
                result = await self._edit_video(params)
            elif action == "edit_image":
                result = await self._edit_image(params)
            elif action == "upscale_image":
                result = await self._upscale_image(params)
            elif action == "upscale_video":
                result = await self._upscale_video(params)
            elif action == "remove_background":
                result = await self._remove_background(params)
            elif action == "face_swap":
                result = await self._face_swap(params)
            elif action == "smart_generate_with_face":
                result = await self._smart_generate_with_face(params)
            elif action == "outpaint_image":
                result = await self._outpaint_image(params)
            elif action == "apply_style":
                result = await self._apply_style(params)
            elif action == "text_to_speech":
                result = await self._text_to_speech(params)
            elif action == "video_to_audio":
                result = await self._video_to_audio(params)
            elif action == "resize_image":
                result = await self._resize_image(params)
            else:
                return PluginResult(
                    success=False,
                    error=f"Bilinmeyen action: {action}"
                )
            
            execution_time = (time.time() - start_time) * 1000
            
            return PluginResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def health_check(self) -> bool:
        """fal.ai API bağlantısını kontrol et."""
        try:
            # Basit bir ping
            if not settings.FAL_KEY:
                return False
            return True
        except:
            return False
    
    # ===============================
    # MODEL ENABLED/DISABLED CHECK
    # ===============================
    
    async def _load_enabled_models(self) -> dict[str, bool]:
        """DB'den enabled model listesini çek (cache'li)."""
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and self._enabled_models_cache:
            return self._enabled_models_cache
        
        try:
            from app.core.database import async_session_maker
            from app.models.models import AIModel
            from sqlalchemy import select
            
            async with async_session_maker() as db:
                result = await db.execute(select(AIModel.name, AIModel.is_enabled))
                rows = result.all()
                self._enabled_models_cache = {name: enabled for name, enabled in rows}
                self._cache_timestamp = now
                logger.debug(f"🔄 Model cache yenilendi: {len(self._enabled_models_cache)} model")
        except Exception as e:
            logger.warning(f"⚠️ Model cache yüklenemedi: {e} — tüm modeller enabled sayılacak")
            # Cache yüklenemezse tüm modeller enabled
            if not self._enabled_models_cache:
                self._enabled_models_cache = {}
        
        return self._enabled_models_cache
    
    def invalidate_model_cache(self):
        """Admin toggle sonrası cache'i invalidate et."""
        self._cache_timestamp = 0
        self._enabled_models_cache = {}
        logger.info("🔄 Model cache invalidate edildi")
    
    async def is_model_enabled(self, endpoint_or_shortcode: str) -> bool:
        """Bir modelin enabled olup olmadığını kontrol et."""
        cache = await self._load_enabled_models()
        
        # Önce shortcode olarak bak
        db_name = self.SHORTCODE_TO_DB_NAME.get(endpoint_or_shortcode)
        if not db_name:
            # Endpoint olarak bak
            db_name = self.ENDPOINT_TO_DB_NAME.get(endpoint_or_shortcode)
        if not db_name:
            # Doğrudan DB name olabilir
            db_name = endpoint_or_shortcode
        
        # Cache'de yoksa (yeni model, henüz DB'ye eklenmemiş) → enabled say
        return cache.get(db_name, True)
    
    async def _filter_enabled_endpoint(self, endpoint: str, fallback_chain: list[str]) -> str:
        """Endpoint disabled ise fallback chain'den ilk enabled olanı döndür."""
        if await self.is_model_enabled(endpoint):
            return endpoint
        
        logger.info(f"⛔ {endpoint} disabled — fallback aranıyor...")
        for fb in fallback_chain:
            if await self.is_model_enabled(fb):
                logger.info(f"✅ Fallback: {fb}")
                return fb
        
        # Hiç enabled model yoksa hata
        raise ValueError(f"Bu kategorideki tüm modeller kapatılmış! Lütfen admin panelden en az bir modeli açın.")
    
    # ===============================
    # SMART MODEL ROUTER
    # ===============================
    
    # Model fallback zincirleri — bir model başarısız olursa sıradaki denenir
    IMAGE_MODEL_CHAIN = [
        "fal-ai/nano-banana-pro",
        "fal-ai/nano-banana-2",
        "fal-ai/flux-2",
        "fal-ai/reve/text-to-image",
    ]
    
    VIDEO_MODEL_CHAIN = [
        {"i2v": "fal-ai/kling-video/v3/pro/image-to-video", "t2v": "fal-ai/kling-video/v3/pro/text-to-video"},
        {"i2v": "fal-ai/sora-2/image-to-video/pro", "t2v": "fal-ai/sora-2/text-to-video/pro"},
        {"i2v": "fal-ai/veo3.1/image-to-video", "t2v": "fal-ai/veo3.1/text-to-video"},
        {"i2v": "fal-ai/bytedance/seedance/v1.5/pro/image-to-video", "t2v": "fal-ai/bytedance/seedance/v1.5/pro/fast/text-to-video"},
        {"i2v": "fal-ai/minimax/hailuo-02/standard/image-to-video", "t2v": "fal-ai/minimax/hailuo-02/standard/text-to-video"},
    ]
    
    EDIT_MODEL_CHAIN = [
        "fal-ai/flux-kontext",
        "fal-ai/flux-pro/kontext",
        "fal-ai/qwen-image-edit",
        "fal-ai/omnigen-v1",
        "fal-ai/flux-general/inpainting",
    ]
    
    # Agent shortcode → endpoint mapping
    IMAGE_MODEL_MAP = {
        "nano_banana": "fal-ai/nano-banana-pro",
        "nano_banana_2": "fal-ai/nano-banana-2",
        "flux2": "fal-ai/flux-2",
        "flux2_max": "fal-ai/flux-2-max",
        "gpt_image": "fal-ai/gpt-image-1-mini",
        "reve": "fal-ai/reve/text-to-image",
        "seedream": "fal-ai/bytedance/seedream/v4.5/text-to-image",
        "recraft": "fal-ai/recraft/v3/text-to-image",
        "grok_imagine": "xai/grok-imagine-image",
    }
    
    VIDEO_MODEL_MAP = {
        "kling": {"i2v": "fal-ai/kling-video/v3/pro/image-to-video", "t2v": "fal-ai/kling-video/v3/pro/text-to-video"},
        "sora2": {"i2v": "fal-ai/sora-2/image-to-video/pro", "t2v": "fal-ai/sora-2/text-to-video/pro"},
        "veo": {"i2v": "fal-ai/veo3.1/fast/image-to-video", "t2v": "fal-ai/veo3.1/fast"},
        "veo_quality": {"i2v": "fal-ai/veo3.1/image-to-video", "t2v": "fal-ai/veo3.1"},
        "seedance": {"i2v": "fal-ai/bytedance/seedance/v1.5/pro/image-to-video", "t2v": "fal-ai/bytedance/seedance/v1.5/pro/fast/text-to-video"},
        "hailuo": {"i2v": "fal-ai/minimax/hailuo-02/standard/image-to-video", "t2v": "fal-ai/minimax/hailuo-02/standard/text-to-video"},
        "grok_imagine_video": {"i2v": "xai/grok-imagine-video/image-to-video", "t2v": "xai/grok-imagine-video/text-to-video"},
    }
    
    async def _select_image_model(self, prompt: str, agent_model: str = "auto") -> tuple[str, str | None]:
        """
        Smart Model Router — agent'ın model seçimini öncelikle kullan,
        yoksa prompt'a göre en iyi görsel modelini seç.
        Disabled modeller atlanır.
        Returns: (endpoint, disabled_warning_or_None)
        """
        disabled_warning = None
        
        # Agent belirli bir model seçtiyse → direkt kullan (disabled kontrolü ile)
        if agent_model and agent_model != "auto" and agent_model in self.IMAGE_MODEL_MAP:
            endpoint = self.IMAGE_MODEL_MAP[agent_model]
            if await self.is_model_enabled(agent_model):
                logger.info(f"🎯 Agent Model Seçimi: {agent_model} → {endpoint}")
                return endpoint, None
            else:
                # DB'den display name al
                db_name = self.SHORTCODE_TO_DB_NAME.get(agent_model, agent_model)
                disabled_warning = f"⚠️ '{db_name}' modeli admin panelinde devre dışı bırakılmış."
                logger.info(f"⛔ Agent Model {agent_model} disabled — smart router devralıyor")
        
        # Auto mod — prompt analizi ile seç
        prompt_lower = prompt.lower()
        
        # Anime/Ghibli/cartoon/illustration tarzı
        artistic_keywords = [
            "ghibli", "anime", "manga", "cartoon", "çizgi film",
            "illustration", "illüstrasyon", "watercolor", "sulu boya",
            "disney", "pixar", "comic", "chibi", "kawaii",
        ]
        
        if any(kw in prompt_lower for kw in artistic_keywords):
            ep = "fal-ai/gpt-image-1-mini"
            if await self.is_model_enabled(ep):
                logger.info("🎯 Smart Router: GPT Image 1 seçildi (artistic/anime)")
                return ep, disabled_warning
        
        # Metin/tipografi/logo gerektiren promptlar
        text_keywords = [
            "text", "logo", "typography", "yazı", "metin", "slogan",
            "poster", "banner", "afiş", "kart", "card", "title",
            "heading", "başlık", "label", "etiket", "sign", "tabela",
            "writing", "font", "letter", "harf",
        ]
        
        if any(kw in prompt_lower for kw in text_keywords):
            ep = "fal-ai/flux-2"
            if await self.is_model_enabled(ep):
                logger.info("🎯 Smart Router: Flux.2 seçildi (tipografi)")
                return ep, disabled_warning
        
        # Premium/detaylı istekler
        premium_keywords = [
            "ultra detailed", "hyper realistic", "4k", "8k",
            "premium", "maximum quality", "en yüksek kalite",
            "masterpiece", "profesyonel fotoğraf",
        ]
        
        if any(kw in prompt_lower for kw in premium_keywords):
            ep = "fal-ai/flux-2-max"
            if await self.is_model_enabled(ep):
                logger.info("🎯 Smart Router: Flux 2 Max seçildi (premium)")
                return ep, disabled_warning
        
        # Hızlı/draft/taslak istekler → Nano Banana 2 (hızlı + ucuz)
        fast_keywords = [
            "hızlı", "quick", "fast", "draft", "taslak",
            "deneme", "test", "sketch", "mockup",
            "toplu", "batch", "bulk", "sosyal medya", "social media",
        ]
        
        if any(kw in prompt_lower for kw in fast_keywords):
            ep = "fal-ai/nano-banana-2"
            if await self.is_model_enabled(ep):
                logger.info("🎯 Smart Router: Nano Banana 2 seçildi (hızlı/draft)")
                return ep, disabled_warning
        
        # Varsayılan: IMAGE_MODEL_CHAIN'den ilk enabled model
        for ep in self.IMAGE_MODEL_CHAIN:
            if await self.is_model_enabled(ep):
                logger.info(f"🎯 Smart Router: {ep} seçildi (varsayılan/fallback)")
                return ep, disabled_warning
        
        # Hiç enabled model yoksa hata
        raise ValueError("Tüm görsel modelleri kapatılmış! Admin panelden en az birini açın.")
    
    async def _select_video_model(self, prompt: str, has_image: bool, agent_model: str = "auto") -> tuple[str, str | None]:
        """
        Smart Video Model Router — agent'ın model seçimini öncelikle kullan,
        yoksa prompt'a göre en iyi video modelini seç.
        Disabled modeller atlanır.
        Returns: (endpoint, disabled_warning_or_None)
        """
        mode = "i2v" if has_image else "t2v"
        disabled_warning = None
        
        # Agent belirli bir model seçtiyse → direkt kullan (disabled kontrolü ile)
        if agent_model and agent_model != "auto" and agent_model in self.VIDEO_MODEL_MAP:
            endpoint = self.VIDEO_MODEL_MAP[agent_model][mode]
            if await self.is_model_enabled(agent_model):
                logger.info(f"🎯 Agent Model Seçimi: {agent_model} → {endpoint}")
                return endpoint, None
            else:
                db_name = self.SHORTCODE_TO_DB_NAME.get(agent_model, agent_model)
                disabled_warning = f"⚠️ '{db_name}' modeli admin panelinde devre dışı bırakılmış."
                logger.info(f"⛔ Agent Model {agent_model} disabled — smart router devralıyor")
        
        # Auto mod — prompt analizi ile seç
        prompt_lower = prompt.lower()
        
        # Uzun video / hikaye anlatımı → Sora 2
        long_keywords = [
            "uzun video", "long video", "hikaye", "story", "narrative",
            "sahne", "scene", "20 saniye", "20s", "15 saniye", "15s",
            "çoklu sahne", "multi scene", "multi-shot",
        ]
        
        if any(kw in prompt_lower for kw in long_keywords):
            endpoint = self.VIDEO_MODEL_MAP["sora2"][mode]
            if await self.is_model_enabled(endpoint):
                logger.info(f"🎯 Smart Router: Sora 2 seçildi (uzun/hikaye) — {endpoint}")
                return endpoint, disabled_warning
        
        # Yüksek kalite / profesyonel / premium → Veo 3.1 Quality
        quality_keywords = [
            "yüksek kalite", "high quality", "en iyi kalite", "best quality",
            "premium", "profesyonel", "professional", "ultra",
            "mükemmel", "perfect", "maximum quality", "max quality",
            "kaliteli", "4k video", "8k video", "hd video",
            "masterpiece", "showcase", "portfolio",
        ]
        
        if any(kw in prompt_lower for kw in quality_keywords):
            endpoint = self.VIDEO_MODEL_MAP["veo_quality"][mode]
            if await self.is_model_enabled(endpoint):
                logger.info(f"🎯 Smart Router: Veo 3.1 QUALITY seçildi (premium istek) — {endpoint}")
                return endpoint, disabled_warning
        
        # Sinematik/gerçekçi/fizik istekler → Veo 3.1 Fast
        cinematic_keywords = [
            "cinematic", "sinematik", "realistic", "gerçekçi",
            "film", "movie", "documentary", "belgesel",
            "slow motion", "yavaş çekim", "epic", "physics", "fizik",
        ]
        
        if any(kw in prompt_lower for kw in cinematic_keywords):
            endpoint = self.VIDEO_MODEL_MAP["veo"][mode]
            if await self.is_model_enabled(endpoint):
                logger.info(f"🎯 Smart Router: Veo 3.1 Fast seçildi (sinematik) — {endpoint}")
                return endpoint, disabled_warning
        
        # Kısa/hızlı/sosyal medya → Hailuo 02
        short_keywords = [
            "kısa", "short", "hızlı", "quick", "fast", "clip",
            "sosyal medya", "social media", "reels", "tiktok",
            "instagram", "story", "stories",
        ]
        
        if any(kw in prompt_lower for kw in short_keywords):
            endpoint = self.VIDEO_MODEL_MAP["hailuo"][mode]
            if await self.is_model_enabled(endpoint):
                logger.info(f"🎯 Smart Router: Hailuo 02 seçildi (kısa/hızlı) — {endpoint}")
                return endpoint, disabled_warning
        
        # Varsayılan: VIDEO_MODEL_CHAIN'den ilk enabled model
        for chain_item in self.VIDEO_MODEL_CHAIN:
            endpoint = chain_item[mode]
            if await self.is_model_enabled(endpoint):
                logger.info(f"🎯 Smart Router: {endpoint} seçildi (varsayılan/fallback)")
                return endpoint, disabled_warning
        
        raise ValueError("Tüm video modelleri kapatılmış! Admin panelden en az birini açın.")
    
    # ===============================
    # PRIVATE METHODS
    # ===============================
    
    async def _generate_image(self, params: dict) -> dict:
        """
        Akıllı Görsel Üretim — Smart Router + Auto-Retry Fallback.
        
        1. Smart Router prompt'a göre en iyi modeli seçer
        2. Başarısız olursa fallback zincirine geçer
        """
        prompt = params.get("prompt", "")
        aspect_ratio = params.get("aspect_ratio", "1:1")
        resolution = params.get("resolution", "1K")
        preferred_model = params.get("model", "auto")  # Agent model shortcode (nano_banana, flux2, gpt_image, etc.)
        
        # Resolution mapping
        resolution_map = {
            "1K": {"square": 1024, "landscape": (1280, 720), "portrait": (720, 1280)},
            "2K": {"square": 1536, "landscape": (1920, 1080), "portrait": (1080, 1920)},
            "4K": {"square": 2048, "landscape": (2560, 1440), "portrait": (1440, 2560)},
        }
        
        # Aspect ratio mapping
        aspect_map = {
            "1:1": "square", "16:9": "landscape", "9:16": "portrait",
            "4:3": "landscape", "3:4": "portrait",
        }
        
        aspect_type = aspect_map.get(aspect_ratio, "square")
        res_config = resolution_map.get(resolution, resolution_map["1K"])
        
        if aspect_type == "square":
            image_size = {"width": res_config["square"], "height": res_config["square"]}
        else:
            w, h = res_config[aspect_type]
            image_size = {"width": w, "height": h}
        
        # Smart Model Router: Agent seçimi veya prompt analizi
        selected_model, disabled_warning = await self._select_image_model(prompt, agent_model=preferred_model)
        
        # Auto-Retry Fallback zinciri oluştur
        models_to_try = [selected_model]
        for m in self.IMAGE_MODEL_CHAIN:
            if m not in models_to_try:
                models_to_try.append(m)
        
        last_error = None
        for model_id in models_to_try:
            try:
                logger.info(f"🖼️ Görsel üretim deneniyor: {model_id}")
                
                # FLUX 2 Flex farklı parametre yapısı kullanır
                if "flux-2" in model_id:
                    arguments = {
                        "prompt": prompt,
                        "image_size": image_size,
                        "num_images": 1,
                        "num_inference_steps": 30,
                        "guidance_scale": 5.0,
                        "output_format": "png",
                        "enable_safety_checker": False,
                    }
                else:
                    arguments = {
                        "prompt": prompt,
                        "image_size": image_size,
                        "num_images": 1,
                        "output_format": "png",
                        "enable_safety_checker": False,
                    }
                
                result = await fal_client.subscribe_async(
                    model_id,
                    arguments=arguments,
                    with_logs=True,
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    logger.info(f"✅ Görsel üretildi: {model_id}")
                    response = {
                        "success": True,
                        "image_url": result["images"][0]["url"],
                        "model": model_id.split("/")[-1],
                        "model_id": model_id,
                    }
                    if disabled_warning:
                        response["disabled_model_warning"] = disabled_warning
                    return response
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ {model_id} başarısız: {e}. Sonraki model deneniyor...")
                continue
        
        return {"success": False, "error": f"Tüm modeller başarısız. Son hata: {last_error}"}
    
    async def _generate_video(self, params: dict) -> dict:
        """
        Smart Multi-Model Video Generation — Agent Model Seçimi + Smart Router.
        """
        prompt = params.get("prompt", "")
        image_url = params.get("image_url")  # Opsiyonel - image-to-video
        duration = params.get("duration", "5")  
        agent_model = params.get("model", "auto")  # Agent shortcode: kling, sora2, veo, seedance, hailuo, auto
        
        has_image = bool(image_url)
        mode = "i2v" if has_image else "t2v"
        
        # Smart Router: Agent seçimi veya prompt analizi ile model belirle
        selected_endpoint, disabled_warning = await self._select_video_model(prompt, has_image, agent_model=agent_model)
        
        # Hangi model ailesine ait? (duration formatı için)
        model_family = agent_model if agent_model != "auto" else "kling"
        for family, endpoints in self.VIDEO_MODEL_MAP.items():
            if selected_endpoint in endpoints.values():
                model_family = family
                break
        
        logger.info(f"🎥 Video model seçildi: {model_family.upper()} ({selected_endpoint})")
        
        try:
            # Model-specific duration formatting
            dur_int = int(duration)
            
            if model_family in ("veo", "veo_quality"):
                # Veo uses durationSeconds (4-8 range)
                formatted_duration = max(4, min(8, dur_int))
            else:
                formatted_duration = duration
            
            # Model-specific arguments
            if model_family in ("veo", "veo_quality"):
                arguments = {
                    "prompt": prompt,
                    "durationSeconds": formatted_duration,
                    "aspectRatio": params.get("aspect_ratio", "16:9"),
                }
            else:
                arguments = {
                    "prompt": prompt,
                    "duration": formatted_duration,
                    "aspect_ratio": params.get("aspect_ratio", "16:9"),
                }
            
            if has_image:
                # Video API'leri (özellik Kling) için çözünürlük limitleri var. (örn: max 1280x720 civarı bir şeye sığmalı)
                try:
                    import httpx
                    import tempfile
                    import os as os_module
                    from PIL import Image
                    import base64
                    
                    max_dim = 1280
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(image_url)
                        resp.raise_for_status()
                    
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        tmp.write(resp.content)
                        tmp_path = tmp.name
                        
                    with Image.open(tmp_path) as img:
                        orig_w, orig_h = img.size
                        if orig_w > max_dim or orig_h > max_dim:
                            logger.info(f"Yüksek çözünürlüklü görsel saptandı ({orig_w}x{orig_h}). Video modeli için küçültülüyor...")
                            if orig_w > orig_h:
                                new_w = max_dim
                                new_h = int(orig_h * (max_dim / orig_w))
                            else:
                                new_h = max_dim
                                new_w = int(orig_w * (max_dim / orig_h))
                            
                            # Encode dimensions to multiples of 8
                            new_w = new_w - (new_w % 8)
                            new_h = new_h - (new_h % 8)
                            
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                                
                            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            img.save(tmp_path, format="JPEG", quality=95)
                            
                            # Yeniden yükle
                            with open(tmp_path, "rb") as f:
                                b64_data = base64.b64encode(f.read()).decode("utf-8")
                            
                            # Data URI oluşturup upload metodunu çağırıyoruz
                            upload_res = await self.upload_base64_image(f"data:image/jpeg;base64,{b64_data}")
                            if upload_res.get("success"):
                                image_url = upload_res.get("url")
                                logger.info(f"Optimize edilmiş görsel yüklendi: {image_url}")
                    
                    if os_module.path.exists(tmp_path):
                        os_module.remove(tmp_path)
                except Exception as resize_err:
                    logger.warning(f"Görsel boyutlandırma hatası, orijinali ile devam ediliyor: {resize_err}")

                arguments["image_url"] = image_url
            
            # Bazı modeller (Minimax) image_url kabul etmeyebilir veya farklı isimlendirmiş olabilir, 
            # ancak standart fal.ai wrapperları genelde image_url standardını destekliyor.
            
            logger.info(f"⏳ fal.ai video üretim başlatılıyor: {selected_endpoint}")
            
            # subprocess ile çağır — fal_client.subscribe_async uvicorn event loop'unda takılıyor
            import asyncio as _asyncio
            import sys as _sys
            import json as _json
            import tempfile as _tmpf
            import os as _os2
            import base64 as _b64
            from app.core.config import settings as _settings
            
            _fal_key = _settings.FAL_KEY or ""
            _args_b64 = _b64.b64encode(_json.dumps(arguments).encode()).decode()
            
            # Geçici Python dosyası oluştur (Base64 ile güvenli argüman aktarımı)
            _script_content = f"""import asyncio, os, json, sys, base64, time
os.environ["FAL_KEY"] = "{_fal_key}"

def log(msg):
    with open("/tmp/fal_subprocess_debug.log", "a") as f:
        f.write(f"{{time.strftime('%H:%M:%S')}} - {{msg}}\\n")

log("Subprocess started for endpoint: {selected_endpoint}")

try:
    import fal_client
    log("fal_client imported successfully")
except Exception as e:
    log(f"Failed to import fal_client: {{e}}")
    sys.exit(1)

async def run():
    args = json.loads(base64.b64decode("{_args_b64}").decode())
    try:
        log("Calling fal_client.submit_async...")
        handler = await fal_client.submit_async("{selected_endpoint}", arguments=args)
        request_id = handler.request_id
        log(f"Submitted. Request ID: {{request_id}}")
        
        loop_count = 0
        while True:
            loop_count += 1
            status = await fal_client.status_async("{selected_endpoint}", request_id, with_logs=True)
            
            # fal_client returns Queued(), InProgress(), Completed() objects.
            # Best way to check is stringifying and checking for Not-Completed states
            status_str = str(status).lower()
            
            if loop_count % 6 == 0:
                log(f"Polling status... Current: {{status_str[:50]}}")
            
            # Wait if it's queued, in progress, or waiting
            if "queue" in status_str or "progress" in status_str or "pend" in status_str or "run" in status_str:
                await asyncio.sleep(5)
                continue
                
            log(f"Final status reached: {{status_str[:50]}}")
            result = await fal_client.result_async("{selected_endpoint}", request_id)
            log("Result fetched successfully.")
            json.dump(result, sys.stdout)
            sys.stdout.flush()
            break
            
    except Exception as e:
        log(f"Error in submit-poll loop: {{e}}")
        raise e

log("Starting asyncio.run(run())")
try:
    asyncio.run(run())
    log("asyncio.run(run()) finished successfully")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
except Exception as e:
    log(f"asyncio.run() crashed: {{e}}")
    sys.stderr.flush()
    os._exit(1)
"""
            _tmp_script = _tmpf.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp')
            _tmp_script.write(_script_content)
            _tmp_script.close()
            _script_path = _tmp_script.name
            
            try:
                proc = await _asyncio.create_subprocess_exec(
                    _sys.executable, _script_path,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                
                try:
                    stdout, stderr = await _asyncio.wait_for(
                        proc.communicate(),
                        timeout=1200  # 20 dakika (uzun videolar ekstra uzun sürebilir)
                    )
                except _asyncio.TimeoutError:
                    proc.kill()
                    logger.error(f"⏱️ fal.ai video 20dk timeout! ({selected_endpoint})")
                    return {"success": False, "error": f"Video üretimi zaman aşımına uğradı (20dk). Model: {model_family}"}
                
                _stderr_text = stderr.decode().strip()
                if _stderr_text:
                    logger.warning(f"fal subprocess stderr:\\n{_stderr_text}")  # Truncate kaldırıldı
                
                _stdout_text = stdout.decode().strip()
                if not _stdout_text:
                    # Subprocess boş çıktı verdi — stderr'den hata detayını al
                    _stderr_short = _stderr_text[:300] if _stderr_text else "stderr de boş"
                    logger.error(f"fal subprocess boş çıktı. Exit: {proc.returncode}. Stderr:\n{_stderr_text}")
                    return {"success": False, "error": f"Video subprocess hatası (Exit {proc.returncode}): {_stderr_short}"}
                
                try:
                    result = _json.loads(_stdout_text)
                except _json.JSONDecodeError:
                    logger.error(f"fal subprocess JSON parse hatası: {_stdout_text[:500]}")
                    return {"success": False, "error": f"Video subprocess geçersiz yanıt"}
            finally:
                try:
                    _os2.unlink(_script_path)
                except:
                    pass
            
            logger.info(f"✅ fal.ai video yanıt alındı: {selected_endpoint}")
            
            if result and "video" in result:
                response = {
                    "success": True,
                    "video_url": result["video"]["url"],
                    "thumbnail_url": result["video"].get("thumbnail_url"),
                    "model": model_family,
                    "model_id": selected_endpoint,
                }
                if disabled_warning:
                    response["disabled_model_warning"] = disabled_warning
                return response
            else:
                return {"success": False, "error": f"API yanıtı geçersiz. Sonuç: {result}"}
                
        except Exception as e:
            logger.error(f"⚠️ {model_family} ({selected_endpoint}) video üretimi başarısız: {e}")
            return {"success": False, "error": f"Video generation failed: {str(e)}"}
    
    async def _edit_image(self, params: dict) -> dict:
        """
        Akıllı Görsel Düzenleme — FLUX Kontext + Auto-Retry.
        
        Sırasıyla dener:
        1. Object Removal (eğer "kaldır/sil" denildiyse)
        2. FLUX Kontext Pro (Akıllı lokal düzenleme — en iyi)
        3. OmniGen (Genel düzenleme)
        4. Flux Inpainting (Fallback)
        """
        original_prompt = params.get("prompt", "")
        image_url = params.get("image_url", "")
        
        try:
            # 1. Çeviri yap (İngilizce her zaman daha iyi çalışır)
            english_prompt = original_prompt
            try:
                from app.services.prompt_translator import translate_to_english
                english_prompt, _ = await translate_to_english(original_prompt)
                logger.info(f"🎨 Edit Prompt: '{original_prompt}' -> '{english_prompt}'")
            except Exception as trans_error:
                logger.warning(f"Prompt çeviri hatası: {trans_error}. Orijinal prompt kullanılıyor.")
            
            # 2. "Silme" isteği mi?
            removal_keywords = ["remove", "delete", "erase", "take off", "clear", "gone"]
            is_removal = any(kw in english_prompt.lower() for kw in removal_keywords)
            
            if is_removal:
                # Prompt'tan nesneyi çıkar (Basit keyword extraction)
                object_to_remove = english_prompt
                for word in ["remove", "delete", "erase", "take off", "the", "from", "image", "photo", "picture", "please"]:
                    object_to_remove = object_to_remove.lower().replace(word, "").strip()
                
                logger.info(f"🗑️ Object Removal deneniyor: '{object_to_remove}'")
                
                try:
                    result = await fal_client.subscribe_async(
                        "fal-ai/object-removal",
                        arguments={
                            "image_url": image_url,
                            "prompt": object_to_remove,
                        },
                        with_logs=True,
                    )
                    
                    if result and "image" in result:
                        return {
                            "success": True,
                            "image_url": result["image"]["url"],
                            "model": "object-removal",
                            "method_used": "object_removal"
                        }
                except Exception as e:
                    logger.warning(f"Object Removal hatası: {e}")

            # 3. FLUX Kontext Pro (Akıllı Lokal Düzenleme — en iyi)
            logger.info(f"🎯 FLUX Kontext deneniyor: '{english_prompt}'")
            try:
                result = await fal_client.subscribe_async(
                    "fal-ai/flux-pro/kontext",
                    arguments={
                        "prompt": english_prompt,
                        "image_url": image_url,
                        "guidance_scale": 3.5,
                    },
                    with_logs=True,
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    return {
                        "success": True,
                        "image_url": result["images"][0]["url"],
                        "model": "flux-kontext-pro",
                        "method_used": "kontext"
                    }
            except Exception as e:
                logger.warning(f"FLUX Kontext hatası: {e}")

            # 4. OmniGen (Instruction Based Fallback)
            logger.info(f"✨ OmniGen deneniyor: '{english_prompt}'")
            try:
                edit_prompt = f"<img><|image_1|></img> {english_prompt}"
                result = await fal_client.subscribe_async(
                    "fal-ai/omnigen-v1",
                    arguments={
                        "prompt": edit_prompt,
                        "input_image_urls": [image_url],
                        "num_images": 1,
                        "image_size": "square_hd",
                        "guidance_scale": 3.0,
                        "num_inference_steps": 50,
                    },
                    with_logs=True,
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    return {
                        "success": True,
                        "image_url": result["images"][0]["url"],
                        "model": "omnigen-v1",
                        "method_used": "omnigen"
                    }
            except Exception as e:
                logger.warning(f"OmniGen hatası: {e}")

            # 5. Fallback: Flux Inpainting
            logger.info("🔧 Flux Inpainting Fallback...")
            return await self._inpainting_flux(image_url, english_prompt if english_prompt else original_prompt)
                
        except Exception as e:
            logger.error(f"EDIT IMAGE KRİTİK HATA: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _outpaint_image(self, params: dict) -> dict:
        """
        Görseli genişletme (Outpainting) — Fallback zinciri ile.
        
        1. fal-ai/image-apps-v2/outpaint (native outpainting)
        2. Flux Kontext (edit ile format dönüşümü — fallback)
        """
        image_url = params.get("image_url", "")
        prompt = params.get("prompt", "")
        left = params.get("left", 0)
        right = params.get("right", 0)
        top = params.get("top", 0)
        bottom = params.get("bottom", 0)
        
        if left == 0 and right == 0 and top == 0 and bottom == 0:
            left = right = top = bottom = 256
        
        # Attempt 1: Native outpainting
        try:
            logger.info(f"🔲 Outpainting: L={left} R={right} T={top} B={bottom}")
            
            result = await fal_client.subscribe_async(
                "fal-ai/image-apps-v2/outpaint",
                arguments={
                    "image_url": image_url,
                    "prompt": prompt or "extend the image naturally, maintaining style and composition",
                    "left": left,
                    "right": right,
                    "top": top,
                    "bottom": bottom,
                },
                with_logs=True,
            )
            
            if result and "image" in result:
                return {
                    "success": True,
                    "image_url": result["image"]["url"],
                    "model": "outpaint",
                    "method_used": "outpainting"
                }
        except Exception as e:
            logger.warning(f"⚠️ Outpainting başarısız: {e}. Flux Kontext fallback deneniyor...")
        
        # Attempt 2: Flux Kontext fallback
        try:
            if (left + right) > (top + bottom):
                kontext_prompt = f"Extend this image to a wide landscape panoramic format. Add natural continuation of the scenery on both left and right sides. Keep the main subject exactly the same. {prompt}"
            elif (top + bottom) > (left + right):
                kontext_prompt = f"Extend this image to a tall portrait format. Add natural continuation above and below. Keep the main subject exactly the same. {prompt}"
            else:
                kontext_prompt = f"Extend this image outward in all directions. Add natural continuation of the scenery. Keep the main subject exactly the same. {prompt}"
            
            logger.info(f"🎯 Outpaint Fallback: Flux Kontext ile format dönüşümü")
            
            result = await fal_client.subscribe_async(
                "fal-ai/flux-pro/kontext",
                arguments={
                    "prompt": kontext_prompt,
                    "image_url": image_url,
                    "guidance_scale": 3.0,
                    "output_format": "png",
                },
                with_logs=True,
            )
            
            if result and "images" in result and len(result["images"]) > 0:
                return {
                    "success": True,
                    "image_url": result["images"][0]["url"],
                    "model": "flux-kontext-pro",
                    "method_used": "kontext_outpaint"
                }
        except Exception as e:
            logger.warning(f"⚠️ Kontext outpaint fallback hatası: {e}")
        
        return {"success": False, "error": "Outpainting başarısız. Hem native outpaint hem Kontext fallback çalışmadı."}
    
    async def _apply_style(self, params: dict) -> dict:
        """
        Sanatsal Stil Aktarımı (Style Transfer).
        
        Görsele artistik stil uygular:
        - Empresyonizm, kübizm, sürrealizm, anime, çizgi film...
        - Moodboard'dan stil aktarımı
        """
        image_url = params.get("image_url", "")
        style = params.get("style", "impressionism")  # Stil adı veya açıklaması
        prompt = params.get("prompt", "")
        
        # Style prompt oluştur
        style_prompt = prompt if prompt else f"Apply {style} art style to this image"
        
        try:
            logger.info(f"🎨 Style Transfer: '{style}' uygulanıyor")
            
            result = await fal_client.subscribe_async(
                "fal-ai/image-apps-v2/style-transfer",
                arguments={
                    "image_url": image_url,
                    "style": style,
                    "prompt": style_prompt,
                },
                with_logs=True,
            )
            
            if result and "image" in result:
                return {
                    "success": True,
                    "image_url": result["image"]["url"],
                    "model": "style-transfer",
                    "style_applied": style,
                    "method_used": "style_transfer"
                }
            else:
                return {"success": False, "error": "Stil aktarımı başarısız"}
                
        except Exception as e:
            logger.error(f"Style Transfer hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def _upscale_image(self, params: dict) -> dict:
        """Görsel upscale (Topaz)."""
        image_url = params.get("image_url", "")
        scale = params.get("scale", 2)
        
        try:
            result = await fal_client.subscribe_async(
                "fal-ai/topaz",
                arguments={
                    "image_url": image_url,
                    "scale": scale,
                    "model": "Standard V2",
                },
                with_logs=True,
            )
            
            if result and "image" in result:
                return {
                    "success": True,
                    "image_url": result["image"]["url"],
                    "model": "topaz",
                }
            else:
                return {"success": False, "error": "Upscale yapılamadı"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _upscale_video(self, params: dict) -> dict:
        """Video upscale."""
        video_url = params.get("video_url", "")
        
        try:
            result = await fal_client.subscribe_async(
                "fal-ai/video-upscaler",
                arguments={"video_url": video_url},
                with_logs=True,
            )
            
            if result and "video" in result:
                return {
                    "success": True,
                    "video_url": result["video"]["url"],
                    "model": "video-upscaler",
                }
            else:
                return {"success": False, "error": "Video upscale yapılamadı"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _remove_background(self, params: dict) -> dict:
        """Arka plan kaldır (BiRefNet V2 — transparent PNG)."""
        image_url = params.get("image_url", "")
        
        try:
            result = await fal_client.subscribe_async(
                "fal-ai/birefnet/v2",
                arguments={
                    "image_url": image_url,
                    "model": "General Use (Light)",
                    "operating_resolution": "1024x1024",
                    "output_format": "png",
                },
                with_logs=True,
            )
            
            if result and "image" in result:
                return {
                    "success": True,
                    "image_url": result["image"]["url"],
                    "model": "birefnet-v2",
                }
            else:
                return {"success": False, "error": "Arka plan kaldırılamadı"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _face_swap(self, params: dict) -> dict:
        """Yüz değiştirme."""
        base_image_url = params.get("base_image_url", "")
        swap_image_url = params.get("swap_image_url", "")
        
        try:
            result = await fal_client.subscribe_async(
                "fal-ai/face-swap",
                arguments={
                    "base_image_url": base_image_url,
                    "swap_image_url": swap_image_url,
                },
                with_logs=True,
            )
            
            if result and "image" in result:
                return {
                    "success": True,
                    "image_url": result["image"]["url"],
                    "model": "face-swap",
                }
            else:
                return {"success": False, "error": "Yüz değişimi yapılamadı"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _smart_generate_with_face(self, params: dict) -> dict:
        """
        Akıllı görsel üretim — yüz kimliği korumalı.
        
        Grid eklentisindeki kaliteyi chat'e taşıyan strateji:
        0. Arka Plan Kaldırma — Referans fotoğraftan arka planı temizle (kırmızı alan sızmasını önler)
        1. Nano Banana Pro Edit — Grid eklentisinin kullandığı model (en iyi fotorealizm)
        2. GPT Image 1 Edit — ChatGPT modeli (güçlü fallback)
        3. FLUX Kontext Pro — Son alternatif
        """
        import httpx
        import asyncio
        
        prompt = params.get("prompt", "")
        face_image_url = params.get("face_image_url", "")
        aspect_ratio = params.get("aspect_ratio", "1:1")
        resolution = params.get("resolution", "1K")
        
        attempts = []
        
        # ═══════════════════════════════════════════════════════════════
        # ÖN İŞLEM: Arka Plan Kaldırma (BiRefNet)
        # ═══════════════════════════════════════════════════════════════
        # Referans fotoğraftaki arka planı (kırmızı EMRE yazısı vs.) temizle.
        # Bu Gemini/ChatGPT'nin dahili olarak yaptığı işlemin aynısı.
        clean_face_url = face_image_url
        logger.info(f"🧹 Arka plan kaldırılıyor (BiRefNet)...")
        try:
            bg_result = await asyncio.wait_for(
                fal_client.subscribe_async(
                    "fal-ai/birefnet",
                    arguments={
                        "image_url": face_image_url,
                        "model": "General Use (Heavy)",
                        "operating_resolution": "1024x1024",
                        "output_format": "png",
                    },
                    with_logs=True,
                ),
                timeout=15  # 15 saniye limit
            )
            
            if bg_result and "image" in bg_result:
                clean_face_url = bg_result["image"]["url"]
                logger.info(f"✅ Arka plan kaldırıldı! Temiz referans görseli hazır.")
            else:
                logger.warning(f"⚠️ Arka plan kaldırma sonuç döndürmedi, orijinal görsel kullanılacak.")
        except Exception as e:
            logger.warning(f"⚠️ Arka plan kaldırma hatası: {e}. Orijinal görsel kullanılacak.")
        
        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 1: Nano Banana Pro Edit — Grid Eklentisinin Modeli
        # ═══════════════════════════════════════════════════════════════
        # Grid eklentisinde mükemmel sonuç veren aynı endpoint.
        # Temiz referans görseli + prompt gönderip fotorealistik sonuç alır.
        logger.info(f"🎯 Aşama 1: Nano Banana Pro Edit — Grid modeli ile üretim...")
        try:
            result = await asyncio.wait_for(
                fal_client.subscribe_async(
                    "fal-ai/nano-banana-pro/edit",
                    arguments={
                        "prompt": prompt,
                        "image_urls": [clean_face_url],
                        "num_images": 1,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "png",
                        "resolution": resolution or "1K",
                    },
                    with_logs=True,
                ),
                timeout=45
            )
            
            if result and "images" in result and len(result["images"]) > 0:
                image_url = result["images"][0]["url"]
                logger.info(f"✅ Nano Banana Pro Edit başarılı!")
                return {
                    "success": True,
                    "image_url": image_url,
                    "base_image_url": image_url,
                    "method_used": "nano_banana_pro_edit",
                    "quality_notes": "Nano Banana Pro Edit ile fotorealistik görsel üretildi.",
                    "model_display_name": "Nano Banana Pro",
                    "attempts": ["nano_banana_pro_edit (başarılı)"],
                }
        except Exception as e:
            logger.warning(f"⚠️ Nano Banana Pro Edit hatası: {e}")
            attempts.append(f"nano_banana_pro_edit ({str(e)[:80]})")
        
        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 2: GPT Image 1 Edit — ChatGPT Modeli (Fallback)
        # ═══════════════════════════════════════════════════════════════
        gpt_size_map = {
            "1:1": "1024x1024",
            "16:9": "1536x1024",
            "9:16": "1024x1536",
            "4:3": "1536x1024",
            "3:4": "1024x1536",
        }
        gpt_image_size = gpt_size_map.get(aspect_ratio, "1024x1024")
        
        logger.info(f"🖌️ Aşama 2: GPT Image 1 Edit — ChatGPT modeli ile üretim...")
        try:
            edit_prompt = f"Create a photorealistic photograph: {prompt}. The person in this photo must look exactly like the person in the reference image — same face, skin tone, hair, and features. IMPORTANT: Do NOT copy the framing, pose, or composition from the reference photo. Instead, create a completely new scene with natural composition matching the described scenario. Show the full body or environment as the scene requires, not just a close-up headshot. Discard the original background entirely."
            
            result = await asyncio.wait_for(
                fal_client.subscribe_async(
                    "fal-ai/gpt-image-1/edit-image",
                    arguments={
                        "prompt": edit_prompt,
                        "image_urls": [clean_face_url],
                        "image_size": gpt_image_size,
                        "quality": "high",
                        "input_fidelity": "low",
                        "num_images": 1,
                        "output_format": "png",
                    },
                    with_logs=True,
                ),
                timeout=60  # 60 saniye limit
            )
            
            if result and "images" in result and len(result["images"]) > 0:
                image_url = result["images"][0]["url"]
                logger.info(f"✅ GPT Image 1 Edit başarılı!")
                return {
                    "success": True,
                    "image_url": image_url,
                    "base_image_url": image_url,
                    "method_used": "gpt_image_1_edit",
                    "quality_notes": "GPT Image 1 (ChatGPT modeli) ile yüz kimliği korunarak fotorealistik görsel üretildi.",
                    "model_display_name": "GPT Image 1",
                    "attempts": attempts + ["gpt_image_1_edit (başarılı)"],
                }
        except Exception as e:
            logger.warning(f"⚠️ GPT Image 1 Edit hatası: {e}")
            attempts.append(f"gpt_image_1_edit (hata: {str(e)[:80]})")
        
        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 2: FLUX Kontext Pro — Yüz Kimliği Korumalı Dönüşüm
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"🖌️ Aşama 2: FLUX Kontext Pro ile yüz korumalı üretim...")
        try:
            kontext_prompt = f"Place this exact person in the following scene, keeping their face, identity, clothing and appearance exactly the same: {prompt}"
            
            result = await asyncio.wait_for(
                fal_client.subscribe_async(
                    "fal-ai/flux-pro/kontext",
                    arguments={
                        "prompt": kontext_prompt,
                        "image_url": clean_face_url,
                        "guidance_scale": 4.0,
                        "output_format": "png",
                    },
                    with_logs=True,
                ),
                timeout=45  # 45 saniye limit
            )
            
            if result and "images" in result and len(result["images"]) > 0:
                image_url = result["images"][0]["url"]
                logger.info(f"✅ FLUX Kontext Pro başarılı!")
                attempts.append("flux_kontext_pro (başarılı)")
                return {
                    "success": True,
                    "image_url": image_url,
                    "base_image_url": image_url,
                    "method_used": "flux_kontext_pro",
                    "quality_notes": "FLUX Kontext Pro ile yüz kimliği korunarak görsel üretildi.",
                    "model_display_name": "FLUX Kontext Pro",
                    "attempts": attempts + ["flux_kontext_pro (başarılı)"],
                }
        except Exception as e:
            logger.warning(f"⚠️ FLUX Kontext Pro hatası: {e}")
            attempts.append(f"flux_kontext_pro (hata: {str(e)[:80]})")
        
        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 3: Nano Banana Pro — Son Çare (Yüz kimliği korunmaz)
        # ═══════════════════════════════════════════════════════════════
        logger.info(f"🔄 Aşama 3: Nano Banana Pro — son çare...")
        try:
            result = await self._generate_image({
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            })
            
            if result.get("success"):
                logger.info(f"✅ Nano Banana Pro başarılı (yüz entegrasyonsuz)")
                return {
                    "success": True,
                    "image_url": result["image_url"],
                    "base_image_url": result["image_url"],
                    "method_used": "nano_banana_only",
                    "quality_notes": "GPT Image 1 ve FLUX Kontext başarısız oldu. Nano Banana Pro ile üretildi (yüz kimliği korunmadı).",
                    "model_display_name": "Nano Banana Pro",
                    "attempts": attempts + ["nano_banana_pro (başarılı)"],
                }
        except Exception as e:
            logger.warning(f"⚠️ Nano Banana Pro hatası: {e}")
            attempts.append(f"nano_banana_pro (hata: {str(e)[:80]})")
        
        return {
            "success": False,
            "error": "Tüm görsel üretim yöntemleri başarısız oldu.",
            "attempts": attempts,
        }


    async def _extract_frame(self, video_url: str) -> dict:
        """Video'dan ilk kareyi çıkar (FFmpeg)."""
        try:
            # fal-ai/ffmpeg-api kullanarak kare çıkar
            # -ss 00:00:01 : 1. saniyeden al (başlangıç bazen siyah olabilir)
            command = f"ffmpeg -i {video_url} -ss 00:00:01 -vframes 1 output.png"
            
            result = await fal_client.subscribe_async(
                "fal-ai/ffmpeg-api",
                arguments={"command": command},
                with_logs=True,
            )
            
            if result and "outputs" in result and len(result["outputs"]) > 0:
                return {
                    "success": True,
                    "image_url": result["outputs"][0]["url"],
                    "model": "ffmpeg-api"
                }
            return {"success": False, "error": "Kare çıkarılamadı"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _edit_video(self, params: dict) -> dict:
        """
        Akıllı Video Düzenleme (Smart Hybrid).
        
        Stratejiler:
        1. Flux Inpainting + Kling (Nesne kaldırma/değiştirme)
        2. Video-to-Video (Stil/Atmosfer değiştirme)
        3. OmniGen + Kling (Talimatlı düzenleme)
        """
        video_url = params.get("video_url", "")
        instruction = params.get("prompt", "")  # Talimat
        reference_image_url = params.get("image_url")  # Thumbnail/Reference frame
        
        # Eğer referans görsel YOKSA, video'dan çıkar!
        if not reference_image_url:
            print("⚠️ Video için referans görsel (thumbnail) yok. Çıkarılıyor...")
            extract_result = await self._extract_frame(video_url)
            if extract_result["success"]:
                reference_image_url = extract_result["image_url"]
                print(f"✅ Kare çıkarıldı: {reference_image_url[:60]}...")
            else:
                print("❌ Kare çıkarma başarısız. Video-to-Video fallback yapılacak.")
        
        instruction_lower = instruction.lower()
        
        # Strateji Belirleme
        if not reference_image_url:
             # Görsel yoksa mecburen V2V kullanmalıyız (Inpainting görsel ister)
             print("⚠️ Referans görsel yok, Strategy 2 (V2V) zorunlu seçiliyor.")
             strategy = "strategy_2"
        elif any(keyword in instruction_lower for keyword in ["stil", "style", "yap", "make", "filter", "convert", "transform", "anime", "cartoon"]):
            strategy = "strategy_2"  # Global Dönüşüm
        elif any(keyword in instruction_lower for keyword in ["kaldır", "remove", "sil", "delete", "yok et", "change", "değiştir", "replace"]):
            strategy = "strategy_1"  # Inpainting (Görsel var ise)
        else:
            strategy = "strategy_2"  # Varsayılan fallback

            
        print(f"🎬 Video Edit Stratejisi: {strategy} ({instruction})")
        
        try:
            # STRATEJİ 1: Hassas Nesne Kaldırma/Değiştirme (Inpainting Flow)
            if strategy == "strategy_1" and reference_image_url:
                # 1. Kareyi Düzenle (Smart Edit Image kullan - içinde translation ve keyword extraction var)
                print("   1. Adım: Kare Düzenleniyor (_edit_image)...")
                # _edit_image zaten "remove" keywordlerini algılayıp "Object Removal" modelini,
                # aksi halde OmniGen'i kullanıyor. Bu çok daha güvenli.
                edited_frame = await self._edit_image({
                    "image_url": reference_image_url,
                    "prompt": instruction
                })
                
                if not edited_frame["success"]:
                    print(f"❌ Kare düzenleme hatası: {edited_frame.get('error')}")
                    return edited_frame
                
                print(f"   ✅ Kare düzenlendi: {edited_frame['image_url'][:50]}... (Model: {edited_frame.get('model')})")
                
                # 2. Videoyu Yeniden Üret (Kling I2V)
                print("   2. Adım: Video Yeniden Üretiliyor (Kling)...")
                video_result = await self._generate_video({
                    "prompt": instruction, # Veya original prompt
                    "image_url": edited_frame["image_url"],
                    "duration": "5",
                    "aspect_ratio": "16:9" # Videodan alınmalı aslında
                })
                
                if video_result["success"]:
                    video_result["method_used"] = f"edit_frame_{edited_frame.get('model')}_plus_kling"
                return video_result

            # STRATEJİ 2: Video-to-Video
            elif strategy == "strategy_2":
                return await self._video_to_video(video_url, instruction)

            # STRATEJİ 3: OmniGen + Kling (Fallback)
            else:
                # Reference image varsa OmniGen, yoksa V2V fallback
                if reference_image_url:
                    print("   1. Adım: Kare Düzenleniyor (OmniGen)...")
                    edited_frame = await self._edit_image({
                        "image_url": reference_image_url,
                        "prompt": instruction
                    })
                    if not edited_frame["success"]:
                        return edited_frame
                        
                    print("   2. Adım: Video Yeniden Üretiliyor (Kling)...")
                    video_result = await self._generate_video({
                        "prompt": instruction,
                        "image_url": edited_frame["image_url"]
                    })
                    if video_result["success"]:
                        video_result["method_used"] = "omnigen_plus_kling"
                    return video_result
                else:
                    return await self._video_to_video(video_url, instruction)

        except Exception as e:
            return {"success": False, "error": f"Video düzenleme hatası: {str(e)}"}

    async def _inpainting_flux(self, image_url: str, prompt: str) -> dict:
        """Flux Inpainting ile görsel düzenle."""
        try:
            result = await fal_client.subscribe_async(
                "fal-ai/flux-general/inpainting",
                arguments={
                    "prompt": prompt,
                    "image_url": image_url,
                    "mask_strategy": "keyword", # Basit keyword bazlı maskeleme (örn: "cat")
                    "mask_keywords": prompt,    # Prompt'u keyword olarak kullan
                    "image_size": "landscape_4_3", 
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "strength": 1.0 # Tam inpainting
                },
                with_logs=True,
            )
            
            if result and "images" in result and len(result["images"]) > 0:
                return {
                    "success": True,
                    "image_url": result["images"][0]["url"],
                    "model": "flux-inpainting"
                }
            return {"success": False, "error": "Inpainting başarısız"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _video_to_video(self, video_url: str, prompt: str) -> dict:
        """
        Video-to-Video Fallback.
        1. LTX-Video (Genel endpoint)
        2. Başarısız olursa: İlk kareyi al -> Yeni video üret (Loop)
        """
        print(f"🔥🔥 LIVE DEBUG: _video_to_video called with url={video_url}, prompt={prompt}")
        try:
            # 1. LTX-Video (Genel Endpoint - subpath olmadan)
            print("🎥 Video-to-Video: LTX deneniyor...")
            try:
                result = await fal_client.subscribe_async(
                    "fal-ai/ltx-video", # Doğrudan model ID
                    arguments={
                        "video_url": video_url,
                        "prompt": prompt,
                        "resolution": "1280x720"
                    },
                    with_logs=True,
                )
                print(f"🔥🔥 LIVE DEBUG: LTX Result: {result}")
                if result and "video" in result:
                    return {
                        "success": True,
                        "video_url": result["video"]["url"],
                        "model": "ltx-video",
                        "method_used": "video_to_video_ltx"
                    }
            except Exception as e:
                print(f"⚠️ LTX V2V başarısız ({e}), fallback yapılıyor...")
                print(f"🔥🔥 LIVE DEBUG: LTX Exception: {e}")

            # 2. ULTIMATE FALLBACK: Extract Frame + Generate Video
            # Hiçbir V2V çalışmazsa, videonun ilk karesini alıp yeniden üretiriz.
            # Bu işlem asla çökmemeli.
            print("🔄 V2V Fallback: Kare yakala + Yeniden üret...")
            extract_res = await self._extract_frame(video_url)
            print(f"🔥🔥 LIVE DEBUG: Extract Frame Result: {extract_res}")
            
            if extract_res["success"]:
                # Kling ile I2V yap
                return await self._generate_video({
                    "prompt": prompt,
                    "image_url": extract_res["image_url"],
                    "duration": "5",
                    "aspect_ratio": "16:9"
                })
            else:
                return {"success": False, "error": "Video karesi alınamadı, düzenleme iptal."}

        except Exception as e:
            return {"success": False, "error": f"Video edit kritik hata: {str(e)}"}

    # ===============================
    # TEXT-TO-SPEECH (TTS)
    # ===============================
    
    async def _text_to_speech(self, params: dict) -> dict:
        """
        Metin-Sesendirme — ElevenLabs TTS → MiniMax Speech fallback.
        """
        text = params.get("text", "")
        voice = params.get("voice", "default")
        
        if not text:
            return {"success": False, "error": "Metin gerekli."}
        
        # Model zinciri: ElevenLabs Turbo → MiniMax Speech
        tts_chain = [
            ("ElevenLabs TTS Turbo v2.5", "fal-ai/elevenlabs/tts/turbo-v2.5"),
            ("MiniMax Speech-02", "fal-ai/minimax/speech-02-turbo"),
        ]
        
        for model_name, endpoint in tts_chain:
            try:
                logger.info(f"🎙️ TTS: {model_name} ile seslendirme...")
                
                input_data = {"text": text}
                if voice and voice != "default":
                    input_data["voice"] = voice
                
                result = await fal_client.run_async(endpoint, arguments=input_data)
                
                audio_url = None
                for key in ["audio", "audio_url", "output"]:
                    val = result.get(key)
                    if val:
                        audio_url = val.get("url") if isinstance(val, dict) else val
                        if audio_url:
                            break
                
                if audio_url:
                    logger.info(f"✅ TTS başarılı: {model_name}")
                    return {
                        "success": True,
                        "audio_url": audio_url,
                        "model": model_name,
                    }
                    
            except Exception as e:
                logger.warning(f"⚠️ {model_name} hatası: {e}")
                continue
        
        return {"success": False, "error": "TTS modelleri başarısız oldu."}
    
    # ===============================
    # VIDEO-TO-AUDIO (SFX)
    # ===============================
    
    async def _video_to_audio(self, params: dict) -> dict:
        """
        Videodan ses efekti üretimi — Mirelo SFX v1.5.
        Videonun içeriğine uygun ses efektleri ve müzik üretir.
        """
        video_url = params.get("video_url", "")
        
        if not video_url:
            return {"success": False, "error": "Video URL gerekli."}
        
        try:
            logger.info(f"🔊 SFX: Mirelo ile video ses efekti üretiliyor...")
            
            result = await fal_client.run_async(
                "mirelo-ai/sfx-v1.5/video-to-audio",
                arguments={"video_url": video_url}
            )
            
            audio_url = None
            for key in ["audio", "audio_url", "output"]:
                val = result.get(key)
                if val:
                    audio_url = val.get("url") if isinstance(val, dict) else val
                    if audio_url:
                        break
            
            if audio_url:
                logger.info("✅ SFX başarılı")
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "model": "Mirelo SFX v1.5",
                }
            else:
                return {"success": False, "error": "SFX audio URL alınamadı.", "raw": result}
                
        except Exception as e:
            return {"success": False, "error": f"SFX hatası: {str(e)}"}

    # ===============================
    # PUBLIC COMPATIBILITY WRAPPERS
    # ===============================

    async def smart_generate_with_face(self, prompt: str, face_image_url: str, aspect_ratio: str = "1:1", resolution: str = "1K") -> dict:
        """AgentOrchestrator uyumluluğu için wrapper."""
        return await self._smart_generate_with_face({
            "prompt": prompt,
            "face_image_url": face_image_url,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution
        })

    async def upload_base64_image(self, base64_data: str) -> dict:
        """
        Base64 encoded görseli fal.ai storage'a yükle.
        AgentOrchestrator tarafından direkt çağrılır.
        """
        import base64
        import tempfile
        import os as os_module
        
        try:
            # Data URI prefix'ini temizle
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]
            
            # Base64 decode
            image_bytes = base64.b64decode(base64_data)
            
            # Extension belirle
            if base64_data.startswith("iVBORw"): extension = ".png"
            elif base64_data.startswith("/9j/"): extension = ".jpg"
            elif base64_data.startswith("UklGR"): extension = ".webp"
            else: extension = ".png"
            
            # Temp dosyaya yaz
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
                tmp_file.write(image_bytes)
                tmp_path = tmp_file.name
            
            try:
                # fal.ai storage'a yükle
                url = fal_client.upload_file(tmp_path)
                return {"success": True, "url": url}
            finally:
                if os_module.path.exists(tmp_path):
                    os_module.remove(tmp_path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _resize_image(self, params: dict) -> dict:
        """
        Tek Görsel Birçok Boyut — Nano Banana 2 Edit ile AI-powered aspect ratio dönüşümü.
        
        Görseli kırpmadan, kenarları AI ile doğal doldurarak farklı formatlara çevirir.
        Birden fazla hedef boyut verilirse paralel üretim yapar.
        """
        image_url = params.get("image_url", "")
        target_ratios = params.get("target_ratios", ["16:9"])
        prompt = params.get("prompt", "")
        resolution = params.get("resolution", "1K")
        
        if not image_url:
            return {"success": False, "error": "image_url gerekli"}
        
        # Aspect ratio isimleri (kullanıcı-dostu)
        ratio_names = {
            "21:9": "Ultra Geniş (21:9)",
            "16:9": "Yatay / YouTube (16:9)",
            "3:2": "Fotoğraf Yatay (3:2)",
            "4:3": "Klasik Yatay (4:3)",
            "5:4": "Kare-Yatay (5:4)",
            "1:1": "Kare (1:1)",
            "4:5": "Instagram Post (4:5)",
            "3:4": "Klasik Dikey (3:4)",
            "2:3": "Fotoğraf Dikey (2:3)",
            "9:16": "Dikey / Story (9:16)",
        }
        
        async def _generate_single_ratio(ratio: str) -> dict:
            """Tek bir aspect ratio için üretim yap."""
            try:
                fill_prompt = prompt or f"Resize this image to {ratio} aspect ratio. Extend the canvas naturally, maintaining the original subject and style. Fill any new areas with contextually appropriate content."
                
                result = await fal_client.subscribe_async(
                    "fal-ai/nano-banana-2/edit",
                    arguments={
                        "prompt": fill_prompt,
                        "image_urls": [image_url],
                        "aspect_ratio": ratio,
                        "output_format": "png",
                        "resolution": resolution,
                        "num_images": 1,
                        "limit_generations": True,
                        "safety_tolerance": "6",
                    },
                    with_logs=True,
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    return {
                        "success": True,
                        "ratio": ratio,
                        "ratio_name": ratio_names.get(ratio, ratio),
                        "image_url": result["images"][0]["url"],
                    }
                else:
                    return {"success": False, "ratio": ratio, "error": "API yanıtı boş"}
            except Exception as e:
                logger.warning(f"⚠️ Resize {ratio} başarısız: {e}")
                return {"success": False, "ratio": ratio, "error": str(e)}
        
        # Paralel üretim
        logger.info(f"🔲 Resize Image: {len(target_ratios)} boyut üretiliyor — {target_ratios}")
        tasks = [_generate_single_ratio(r) for r in target_ratios]
        results = await asyncio.gather(*tasks)
        
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        
        if not successful:
            return {"success": False, "error": f"Tüm boyut dönüşümleri başarısız: {failed}"}
        
        return {
            "success": True,
            "images": successful,
            "total": len(successful),
            "failed": len(failed),
            "model": "nano-banana-2-edit",
        }

# Backward compatibility için singleton instance
fal_plugin_v2 = FalPluginV2()
