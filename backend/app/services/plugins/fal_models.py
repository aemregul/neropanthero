"""
fal.ai Model Tanımları.

Tüm fal.ai modelleri, yetenekleri ve öncelikleri.
Agent bu bilgileri kullanarak en uygun modeli seçer.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ModelCategory(str, Enum):
    """Model kategorileri."""
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    FACE_CONSISTENCY = "face_consistency"
    VIDEO_GENERATION = "video_generation"
    VIDEO_EDITING = "video_editing"
    AUDIO_GENERATION = "audio_generation"
    SPEECH = "speech"
    UPSCALING = "upscaling"
    UTILITY = "utility"


class Priority(str, Enum):
    """Model önceliği."""
    PRIMARY = "primary"      # Ana tercih
    ALTERNATIVE = "alternative"  # Alternatif
    SPECIALIZED = "specialized"  # Özel durumlar


@dataclass
class FalModel:
    """fal.ai model tanımı."""
    name: str
    endpoint: str
    category: ModelCategory
    priority: Priority
    description: str
    best_for: list[str]
    supports_reference: bool = False
    supports_face: bool = False
    estimated_cost: float = 0.01  # USD per request


# ===============================
# GÖRSEL ÜRETİM MODELLERİ
# ===============================

IMAGE_GENERATION_MODELS = [
    FalModel(
        name="Nano Banana Pro",
        endpoint="fal-ai/nano-banana-pro",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.PRIMARY,
        description="Google'ın en gelişmiş görsel üretim modeli. Yüksek kalite ve yüz tutarlılığı.",
        best_for=["portrait", "realistic", "face_consistency", "high_quality"],
        supports_face=True,
        estimated_cost=0.01
    ),
    FalModel(
        name="Flux.2",
        endpoint="fal-ai/flux-2",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.PRIMARY,
        description="Flux serisinin en yenisi. 3x hızlı, gelişmiş metin render ve prompt takibi.",
        best_for=["fast", "text_render", "general", "high_volume"],
        estimated_cost=0.008
    ),
    FalModel(
        name="Flux 2 Max",
        endpoint="fal-ai/flux-2-max",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Flux 2'nin maksimum kalite versiyonu. Edit desteği var.",
        best_for=["maximum_quality", "detailed", "premium"],
        estimated_cost=0.02
    ),
    FalModel(
        name="GPT Image 1",
        endpoint="fal-ai/gpt-image-1-mini",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.SPECIALIZED,
        description="OpenAI'ın görsel modeli. Ghibli, anime, illüstrasyon stillerinde viral kalite.",
        best_for=["ghibli", "anime", "illustration", "cartoon", "artistic", "stylized"],
        estimated_cost=0.02
    ),
    FalModel(
        name="Reve",
        endpoint="fal-ai/reve/text-to-image",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="Yeni nesil görsel üretim, fal.ai'da en popüler modellerden.",
        best_for=["creative", "artistic", "concept_art"],
        estimated_cost=0.01
    ),
    FalModel(
        name="Seedream 4.5",
        endpoint="fal-ai/bytedance/seedream/v4.5/text-to-image",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="ByteDance'ın en yeni modeli. Hızlı, düşük maliyetli, yüksek kalite.",
        best_for=["fast", "cost_effective", "general"],
        estimated_cost=0.006
    ),
    FalModel(
        name="Flux Pro Kontext",
        endpoint="fal-ai/flux-pro/kontext",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="Referans görsel ile hedefli düzenleme ve dönüşüm.",
        best_for=["reference_based", "editing", "transformation"],
        supports_reference=True,
        estimated_cost=0.02
    ),
    FalModel(
        name="Recraft V3",
        endpoint="fal-ai/recraft/v3/text-to-image",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Vektör, tipografi ve marka stili için en iyi.",
        best_for=["vector", "typography", "brand_style", "logo"],
        estimated_cost=0.01
    ),
    FalModel(
        name="Flux Schnell",
        endpoint="fal-ai/flux/schnell",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Hızlı görsel üretim için optimize edilmiş.",
        best_for=["fast", "prototype", "quick_preview"],
        estimated_cost=0.005
    ),
    FalModel(
        name="Grok Imagine 1.0",
        endpoint="xai/grok-imagine-image",
        category=ModelCategory.IMAGE_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="xAI'ın görsel üretim modeli. Yüksek estetik, hassas metin render, geniş stil yelpazesi.",
        best_for=["aesthetic", "text_render", "realistic", "artistic", "versatile"],
        estimated_cost=0.02
    ),
]


# ===============================
# GÖRSEL DÜZENLEME MODELLERİ
# ===============================

IMAGE_EDITING_MODELS = [
    FalModel(
        name="Nano Banana Edit",
        endpoint="fal-ai/nano-banana-pro/edit",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.PRIMARY,
        description="Güçlü görsel düzenleme, Google Gemini tabanlı.",
        best_for=["general_editing", "inpainting", "transformation"],
        supports_reference=True,
        estimated_cost=0.015
    ),
    FalModel(
        name="Flux Kontext",
        endpoint="fal-ai/flux-kontext",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.PRIMARY,
        description="İlk dedicated edit modeli. Karakter tutarlılığı, stil transferi, lokal düzenleme.",
        best_for=["character_consistency", "style_transfer", "local_edit", "fast_edit"],
        supports_reference=True,
        estimated_cost=0.02
    ),
    FalModel(
        name="Qwen Image Edit",
        endpoint="fal-ai/qwen-image-edit",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.ALTERNATIVE,
        description="Açık kaynak edit modeli, LoRA desteği. Geliştirici dostu.",
        best_for=["open_source", "lora", "fine_tunable"],
        supports_reference=True,
        estimated_cost=0.01
    ),
    FalModel(
        name="Qwen Image Max Edit",
        endpoint="fal-ai/qwen-image-max/edit",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.ALTERNATIVE,
        description="Qwen'in maksimum kalite edit modeli.",
        best_for=["high_quality_edit", "detailed_edit"],
        supports_reference=True,
        estimated_cost=0.015
    ),
    FalModel(
        name="Seedream 4.5 Edit",
        endpoint="fal-ai/bytedance/seedream/v4.5/edit",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.SPECIALIZED,
        description="ByteDance'ın en yeni stil dönüşüm ve edit modeli.",
        best_for=["style_transfer", "artistic", "fast_edit"],
        estimated_cost=0.012
    ),
    FalModel(
        name="Fibo Edit",
        endpoint="bria/fibo-edit/edit",
        category=ModelCategory.IMAGE_EDITING,
        priority=Priority.SPECIALIZED,
        description="JSON + Mask ile hassas kontrol.",
        best_for=["precise_editing", "mask_based", "controlled"],
        supports_reference=True,
        estimated_cost=0.02
    ),
]


# ===============================
# YÜZ TUTARLILIĞI MODELLERİ
# ===============================

FACE_CONSISTENCY_MODELS = [
    FalModel(
        name="Face Swap",
        endpoint="fal-ai/face-swap",
        category=ModelCategory.FACE_CONSISTENCY,
        priority=Priority.PRIMARY,
        description="Yüz değiştirme, en güvenilir yüz tutarlılığı.",
        best_for=["face_swap", "identity_preservation"],
        supports_face=True,
        estimated_cost=0.02
    ),
    FalModel(
        name="Easel Advanced Face Swap",
        endpoint="fal-ai/easel/advanced-face-swap",
        category=ModelCategory.FACE_CONSISTENCY,
        priority=Priority.ALTERNATIVE,
        description="Detaylı yüz swap, daha fazla kontrol.",
        best_for=["detailed_face_swap", "multi_face"],
        supports_face=True,
        estimated_cost=0.025
    ),
    FalModel(
        name="Face Swap Video",
        endpoint="fal-ai/face-swap-video",
        category=ModelCategory.FACE_CONSISTENCY,
        priority=Priority.SPECIALIZED,
        description="Video içinde yüz değiştirme.",
        best_for=["video_face_swap"],
        supports_face=True,
        estimated_cost=0.10
    ),
]


# ===============================
# VİDEO ÜRETİM MODELLERİ
# ===============================

VIDEO_GENERATION_MODELS = [
    FalModel(
        name="Kling 3.0 Pro (Image-to-Video)",
        endpoint="fal-ai/kling-video/v3/pro/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.PRIMARY,
        description="En güvenilir video modeli. Sinematik kalite, çoklu sahne, ses desteği.",
        best_for=["image_to_video", "cinematic", "professional", "high_quality", "multi_scene"],
        supports_reference=True,
        estimated_cost=0.15
    ),
    FalModel(
        name="Kling 3.0 Pro (Text-to-Video)",
        endpoint="fal-ai/kling-video/v3/pro/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.PRIMARY,
        description="Metinden video — çoklu sahne ve ses desteği.",
        best_for=["text_to_video", "animation", "creative", "multi_scene"],
        estimated_cost=0.15
    ),
    FalModel(
        name="Sora 2 (Image-to-Video)",
        endpoint="fal-ai/sora-2/image-to-video/pro",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.PRIMARY,
        description="OpenAI Sora 2. ~20 saniyelik uzun video, çoklu sahne, sesli. En uzun süre.",
        best_for=["long_video", "multi_scene", "audio", "storytelling", "narrative"],
        supports_reference=True,
        estimated_cost=0.20
    ),
    FalModel(
        name="Sora 2 (Text-to-Video)",
        endpoint="fal-ai/sora-2/text-to-video/pro",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.PRIMARY,
        description="OpenAI Sora 2. Metinden ~20 saniyelik uzun video.",
        best_for=["long_video", "text_to_video", "storytelling"],
        estimated_cost=0.20
    ),
    FalModel(
        name="Veo 3.1 (Image-to-Video)",
        endpoint="fal-ai/veo3.1/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Google DeepMind. En iyi fizik simülasyonu, 1080p, ses desteği.",
        best_for=["physics", "realistic", "documentary", "cinematic", "high_fidelity"],
        supports_reference=True,
        estimated_cost=0.12
    ),
    FalModel(
        name="Veo 3.1 (Text-to-Video)",
        endpoint="fal-ai/veo3.1/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Google DeepMind. Metinden gerçekçi video, fizik doğruluğu.",
        best_for=["physics", "realistic", "text_to_video"],
        estimated_cost=0.12
    ),
    FalModel(
        name="Seedance 1.5 Pro (Image-to-Video)",
        endpoint="fal-ai/bytedance/seedance/v1.5/pro/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="ByteDance. Hızlı ve ucuz, iyi kalite.",
        best_for=["fast_video", "cost_effective", "image_to_video"],
        supports_reference=True,
        estimated_cost=0.07
    ),
    FalModel(
        name="Seedance 1.5 Pro (Text-to-Video)",
        endpoint="fal-ai/bytedance/seedance/v1.5/pro/fast/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="ByteDance. Hızlı ve ucuz metin-video.",
        best_for=["fast_text_to_video", "cost_effective"],
        estimated_cost=0.07
    ),
    FalModel(
        name="Hailuo 02 (Image-to-Video)",
        endpoint="fal-ai/minimax/hailuo-02/standard/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="MiniMax. En hızlı video (~5s içerik), kısa ve etkileyici.",
        best_for=["short_video", "quick_clip", "social_media", "fast"],
        supports_reference=True,
        estimated_cost=0.06
    ),
    FalModel(
        name="Hailuo 02 (Text-to-Video)",
        endpoint="fal-ai/minimax/hailuo-02/standard/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="MiniMax. En hızlı metin-video.",
        best_for=["short_video", "quick_clip", "fast", "text_to_video"],
        estimated_cost=0.06
    ),
    FalModel(
        name="Kling 2.5 Turbo Pro (Image-to-Video)",
        endpoint="fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="Hızlı image-to-video, dengeli kalite/hız.",
        best_for=["fast_video", "turbo"],
        supports_reference=True,
        estimated_cost=0.10
    ),
    FalModel(
        name="Kling 2.5 Turbo Pro (Text-to-Video)",
        endpoint="fal-ai/kling-video/v2.5-turbo/pro/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="Hızlı metinden video üretimi.",
        best_for=["fast_text_to_video"],
        estimated_cost=0.10
    ),
    FalModel(
        name="Kling O1 (Reference-to-Video)",
        endpoint="fal-ai/kling-video/o1/reference-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Karmaşık çok adımlı video düzenleme talimatları. Referans ile.",
        best_for=["video_editing", "multi_step", "complex_instructions"],
        supports_reference=True,
        estimated_cost=0.15
    ),
    FalModel(
        name="LTX-2 19B",
        endpoint="fal-ai/ltx-2-19b/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Sesli video üretimi.",
        best_for=["video_with_audio", "sound"],
        supports_reference=True,
        estimated_cost=0.08
    ),
    FalModel(
        name="PixVerse V5",
        endpoint="fal-ai/pixverse/v5/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.SPECIALIZED,
        description="Stilize video dönüşümü, efektler.",
        best_for=["stylized", "effects", "artistic_video"],
        supports_reference=True,
        estimated_cost=0.08
    ),
    FalModel(
        name="Grok Imagine Video (Image-to-Video)",
        endpoint="xai/grok-imagine-video/image-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="xAI sinematik video. Senkronize ses, fizik simülasyonu, 720p, 10s.",
        best_for=["cinematic", "audio_sync", "physics", "image_to_video"],
        supports_reference=True,
        estimated_cost=0.10
    ),
    FalModel(
        name="Grok Imagine Video (Text-to-Video)",
        endpoint="xai/grok-imagine-video/text-to-video",
        category=ModelCategory.VIDEO_GENERATION,
        priority=Priority.ALTERNATIVE,
        description="xAI metin-video. Senkronize ses, sinematik kalite.",
        best_for=["cinematic", "audio_sync", "text_to_video"],
        estimated_cost=0.10
    ),
]

# ===============================
# VİDEO DÜZENLEME MODELLERİ (YENİ)
# ===============================

VIDEO_EDITING_MODELS = [
    FalModel(
        name="Flux Inpainting (Flow)",
        endpoint="fal-ai/flux-general/inpainting",
        category=ModelCategory.VIDEO_EDITING,
        priority=Priority.PRIMARY,
        description="Nesne kaldırma ve değiştirme için profesyonel Flow modeli (Kling ile birleşir).",
        best_for=["inpainting", "remove_object", "replace", "fix"],
        supports_reference=True,
        estimated_cost=0.03
    ),
    FalModel(
        name="LTX-Video (V2V)",
        endpoint="fal-ai/ltx-video/video-to-video",
        category=ModelCategory.VIDEO_EDITING,
        priority=Priority.PRIMARY,
        description="Videonun stilini ve atmosferini değiştirmek için (Video-to-Video).",
        best_for=["style_transfer", "filter", "atmosphere", "transform"],
        supports_reference=True,
        estimated_cost=0.10
    ),
    FalModel(
        name="OmniGen (Instruction)",
        endpoint="fal-ai/omnigen-v1",
        category=ModelCategory.VIDEO_EDITING,
        priority=Priority.ALTERNATIVE,
        description="Basit talimatlarla kare düzenleme.",
        best_for=["instruction", "simple_edit"],
        estimated_cost=0.02
    ),
]




# ===============================
# UPSCALING MODELLERİ
# ===============================

UPSCALING_MODELS = [
    FalModel(
        name="Topaz Image Upscale",
        endpoint="fal-ai/topaz/upscale/image",
        category=ModelCategory.UPSCALING,
        priority=Priority.PRIMARY,
        description="Profesyonel görsel kalite artırma.",
        best_for=["image_upscale", "detail_enhancement"],
        estimated_cost=0.05
    ),
    FalModel(
        name="Crystal Upscaler",
        endpoint="fal-ai/crystal-upscaler",
        category=ModelCategory.UPSCALING,
        priority=Priority.SPECIALIZED,
        description="Yüz detayları için özelleşmiş, 200x upscale.",
        best_for=["face_upscale", "portrait_enhancement"],
        supports_face=True,
        estimated_cost=0.06
    ),
    FalModel(
        name="Topaz Video Upscale",
        endpoint="fal-ai/topaz/upscale/video",
        category=ModelCategory.UPSCALING,
        priority=Priority.PRIMARY,
        description="Profesyonel video kalite artırma.",
        best_for=["video_upscale", "4k_conversion"],
        estimated_cost=0.15
    ),
]


# ===============================
# YARDIMCI ARAÇLAR
# ===============================

UTILITY_MODELS = [
    FalModel(
        name="Bria Background Remove",
        endpoint="fal-ai/bria/background/remove",
        category=ModelCategory.UTILITY,
        priority=Priority.PRIMARY,
        description="Görsel arka plan kaldırma.",
        best_for=["background_removal", "transparent"],
        estimated_cost=0.01
    ),
    FalModel(
        name="Video Background Remove",
        endpoint="bria/video/background-removal",
        category=ModelCategory.UTILITY,
        priority=Priority.PRIMARY,
        description="Video arka plan kaldırma.",
        best_for=["video_background_removal"],
        estimated_cost=0.08
    ),
    FalModel(
        name="NSFW Filter",
        endpoint="fal-ai/x-ailab/nsfw",
        category=ModelCategory.UTILITY,
        priority=Priority.PRIMARY,
        description="NSFW içerik tespiti.",
        best_for=["content_moderation", "safety"],
        estimated_cost=0.001
    ),
]


# ===============================
# SES & KONUŞMA MODELLERİ (YENİ)
# ===============================

AUDIO_MODELS = [
    FalModel(
        name="Mirelo SFX v1.5",
        endpoint="mirelo-ai/sfx-v1.5/video-to-audio",
        category=ModelCategory.AUDIO_GENERATION,
        priority=Priority.PRIMARY,
        description="Videodan otomatik ses efekti ve müzik üretimi. Senkronize.",
        best_for=["video_sfx", "sound_effects", "video_to_audio", "foley"],
        estimated_cost=0.03
    ),
]

SPEECH_MODELS = [
    FalModel(
        name="ElevenLabs TTS Turbo v2.5",
        endpoint="fal-ai/elevenlabs/tts/turbo-v2.5",
        category=ModelCategory.SPEECH,
        priority=Priority.PRIMARY,
        description="En hızlı TTS (~250ms). Profesyonel seslendirme kalitesi.",
        best_for=["text_to_speech", "narration", "voiceover", "fast_tts"],
        estimated_cost=0.01
    ),
    FalModel(
        name="MiniMax Speech-02",
        endpoint="fal-ai/minimax/speech-02-turbo",
        category=ModelCategory.SPEECH,
        priority=Priority.ALTERNATIVE,
        description="32 dil desteği, %99 insan sesi doğallığı.",
        best_for=["multilingual", "natural_voice", "turkish", "diverse_languages"],
        estimated_cost=0.01
    ),
    FalModel(
        name="Kokoro TTS",
        endpoint="fal-ai/kokoro/american-english",
        category=ModelCategory.SPEECH,
        priority=Priority.SPECIALIZED,
        description="Açık kaynak, 82M parametre, üretim kalitesi TTS.",
        best_for=["open_source", "english_tts", "cost_effective"],
        estimated_cost=0.002
    ),
    FalModel(
        name="Whisper v3 (STT)",
        endpoint="fal-ai/wizper",
        category=ModelCategory.SPEECH,
        priority=Priority.PRIMARY,
        description="Konuşmadan metne dönüşüm. Çoklu dil desteği.",
        best_for=["speech_to_text", "transcription", "subtitle"],
        estimated_cost=0.005
    ),
]


# ===============================
# TÜM MODELLERİ BİRLEŞTİR
# ===============================

ALL_MODELS = {
    ModelCategory.IMAGE_GENERATION: IMAGE_GENERATION_MODELS,
    ModelCategory.IMAGE_EDITING: IMAGE_EDITING_MODELS,
    ModelCategory.FACE_CONSISTENCY: FACE_CONSISTENCY_MODELS,
    ModelCategory.VIDEO_GENERATION: VIDEO_GENERATION_MODELS,
    ModelCategory.VIDEO_EDITING: VIDEO_EDITING_MODELS,
    ModelCategory.AUDIO_GENERATION: AUDIO_MODELS,
    ModelCategory.SPEECH: SPEECH_MODELS,
    ModelCategory.UPSCALING: UPSCALING_MODELS,
    ModelCategory.UTILITY: UTILITY_MODELS,
}


def get_models_by_category(category: ModelCategory) -> list[FalModel]:
    """Kategoriye göre modelleri getir."""
    return ALL_MODELS.get(category, [])


def get_primary_model(category: ModelCategory) -> Optional[FalModel]:
    """Kategorinin ana modelini getir."""
    models = get_models_by_category(category)
    for model in models:
        if model.priority == Priority.PRIMARY:
            return model
    return models[0] if models else None


def get_model_by_endpoint(endpoint: str) -> Optional[FalModel]:
    """Endpoint'e göre model bul."""
    for category_models in ALL_MODELS.values():
        for model in category_models:
            if model.endpoint == endpoint:
                return model
    return None


def get_face_supporting_models() -> list[FalModel]:
    """Yüz desteği olan modelleri getir."""
    result = []
    for category_models in ALL_MODELS.values():
        for model in category_models:
            if model.supports_face:
                result.append(model)
    return result
