"""
Akıllı Model Seçici.

Görev türüne göre en uygun fal.ai modelini seçer.
Agent'ın karar mekanizmasının temelini oluşturur.
"""

import re
from typing import Optional
from dataclasses import dataclass

from app.services.plugins.fal_models import (
    FalModel,
    ModelCategory,
    Priority,
    ALL_MODELS,
    get_primary_model,
    get_face_supporting_models,
)


@dataclass
class TaskAnalysis:
    """Görev analizi sonucu."""
    task_type: str
    category: ModelCategory
    requires_face: bool = False
    requires_reference: bool = False
    requires_video: bool = False
    requires_upscale: bool = False
    requires_edit: bool = False
    keywords: list[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


@dataclass
class ModelRecommendation:
    """Model önerisi."""
    primary_model: FalModel
    fallback_model: Optional[FalModel] = None
    use_face_swap: bool = False
    use_upscale: bool = False
    reasoning: str = ""


class SmartModelSelector:
    """
    Görev türüne göre en uygun fal.ai modelini seçen akıllı sistem.
    
    Analiz Kriterleri:
    - Kullanıcı mesajındaki anahtar kelimeler
    - Entity'de referans görsel olup olmadığı
    - Video/görsel/düzenleme isteği
    - Kalite gereksinimleri
    """
    
    # Anahtar kelime haritaları
    VIDEO_KEYWORDS = [
        "video", "animasyon", "hareket", "klip", "film",
        "animation", "motion", "clip", "movie"
    ]
    
    EDIT_KEYWORDS = [
        "düzenle", "değiştir", "edit", "modify", "change",
        "arka plan", "background", "stil", "style", "dönüştür"
    ]
    
    UPSCALE_KEYWORDS = [
        "kalite", "upscale", "büyüt", "artır", "enhance",
        "yüksek çözünürlük", "4k", "hd", "quality"
    ]
    
    FACE_KEYWORDS = [
        "yüz", "portre", "face", "portrait", "kişi", "person",
        "karakter", "character"
    ]
    
    VECTOR_KEYWORDS = [
        "vektör", "logo", "tipografi", "vector", "typography",
        "marka", "brand", "ikon", "icon"
    ]
    
    def analyze_task(
        self,
        message: str,
        has_face_reference: bool = False,
        has_image_reference: bool = False,
    ) -> TaskAnalysis:
        """
        Kullanıcı mesajını analiz et ve görev türünü belirle.
        
        Args:
            message: Kullanıcı mesajı
            has_face_reference: Entity'de yüz referansı var mı
            has_image_reference: Düzenlenecek görsel var mı
        
        Returns:
            TaskAnalysis: Görev analizi sonucu
        """
        message_lower = message.lower()
        keywords_found = []
        
        # Video kontrolü
        is_video = any(kw in message_lower for kw in self.VIDEO_KEYWORDS)
        if is_video:
            keywords_found.extend([kw for kw in self.VIDEO_KEYWORDS if kw in message_lower])
        
        # Düzenleme kontrolü
        is_edit = any(kw in message_lower for kw in self.EDIT_KEYWORDS) or has_image_reference
        if is_edit:
            keywords_found.extend([kw for kw in self.EDIT_KEYWORDS if kw in message_lower])
        
        # Upscale kontrolü
        is_upscale = any(kw in message_lower for kw in self.UPSCALE_KEYWORDS)
        if is_upscale:
            keywords_found.extend([kw for kw in self.UPSCALE_KEYWORDS if kw in message_lower])
        
        # Yüz kontrolü
        requires_face = has_face_reference or any(kw in message_lower for kw in self.FACE_KEYWORDS)
        if requires_face:
            keywords_found.extend([kw for kw in self.FACE_KEYWORDS if kw in message_lower])
        
        # Vektör/logo kontrolü
        is_vector = any(kw in message_lower for kw in self.VECTOR_KEYWORDS)
        
        # Kategori belirleme
        if is_video:
            category = ModelCategory.VIDEO_GENERATION
            task_type = "video_generation"
        elif is_upscale:
            category = ModelCategory.UPSCALING
            task_type = "upscaling"
        elif is_edit and has_image_reference:
            category = ModelCategory.IMAGE_EDITING
            task_type = "image_editing"
        else:
            category = ModelCategory.IMAGE_GENERATION
            task_type = "image_generation"
        
        return TaskAnalysis(
            task_type=task_type,
            category=category,
            requires_face=requires_face,
            requires_reference=has_image_reference,
            requires_video=is_video,
            requires_upscale=is_upscale,
            requires_edit=is_edit,
            keywords=keywords_found
        )
    
    def recommend_model(
        self,
        message: str,
        has_face_reference: bool = False,
        has_image_reference: bool = False,
    ) -> ModelRecommendation:
        """
        Görev için en uygun modeli öner.
        
        Args:
            message: Kullanıcı mesajı
            has_face_reference: Entity'de yüz referansı var mı
            has_image_reference: Düzenlenecek görsel var mı
        
        Returns:
            ModelRecommendation: Model önerisi
        """
        analysis = self.analyze_task(message, has_face_reference, has_image_reference)
        
        # Ana model seç
        primary = get_primary_model(analysis.category)
        fallback = None
        use_face_swap = False
        reasoning_parts = []
        
        # Video üretimi
        if analysis.requires_video:
            if has_image_reference:
                # Image-to-video
                primary = self._get_model_by_endpoint("fal-ai/minimax/hailuo-02/standard/image-to-video")
                if primary:
                    reasoning_parts.append("Görsel referanslı video için maliyet odaklı Hailuo 02 seçildi")
            else:
                # Text-to-video
                primary = self._get_model_by_endpoint("fal-ai/minimax/hailuo-02/standard/text-to-video")
                if primary:
                    reasoning_parts.append("Metinden video için maliyet odaklı Hailuo 02 seçildi")
        
        # Upscaling
        elif analysis.requires_upscale:
            if analysis.requires_video:
                primary = self._get_model_by_endpoint("fal-ai/topaz/upscale/video")
                reasoning_parts.append("Video upscale için Topaz seçildi")
            elif analysis.requires_face:
                primary = self._get_model_by_endpoint("fal-ai/crystal-upscaler")
                fallback = self._get_model_by_endpoint("fal-ai/topaz/upscale/image")
                reasoning_parts.append("Yüz detayları için Crystal Upscaler seçildi")
            else:
                primary = self._get_model_by_endpoint("fal-ai/topaz/upscale/image")
                reasoning_parts.append("Görsel upscale için Topaz seçildi")
        
        # Görsel düzenleme
        elif analysis.requires_edit and has_image_reference:
            primary = self._get_model_by_endpoint("fal-ai/nano-banana-pro/edit")
            fallback = self._get_model_by_endpoint("bria/fibo-edit/edit")
            reasoning_parts.append("Görsel düzenleme için Nano Banana Edit seçildi")
        
        # Görsel üretimi (varsayılan)
        else:
            # Vektör/logo için Recraft
            if any(kw in message.lower() for kw in self.VECTOR_KEYWORDS):
                primary = self._get_model_by_endpoint("fal-ai/recraft/v3/text-to-image")
                reasoning_parts.append("Vektör/tipografi için Recraft V3 seçildi")
            else:
                primary = self._get_model_by_endpoint("fal-ai/nano-banana-pro")
                reasoning_parts.append("Yüksek kalite için Nano Banana Pro seçildi")
            
            # Yüz referansı varsa face swap ekle
            if has_face_reference:
                use_face_swap = True
                reasoning_parts.append("Yüz referansı algılandı, Face Swap eklenecek")
        
        # Primary bulunamazsa fallback kullan
        if primary is None:
            primary = get_primary_model(analysis.category)
            reasoning_parts.append(f"Varsayılan {analysis.category.value} modeli kullanılıyor")
        
        return ModelRecommendation(
            primary_model=primary,
            fallback_model=fallback,
            use_face_swap=use_face_swap,
            use_upscale=analysis.requires_upscale,
            reasoning=" | ".join(reasoning_parts)
        )
    
    def _get_model_by_endpoint(self, endpoint: str) -> Optional[FalModel]:
        """Endpoint'e göre model bul."""
        for category_models in ALL_MODELS.values():
            for model in category_models:
                if model.endpoint == endpoint:
                    return model
        return None


# Singleton instance
model_selector = SmartModelSelector()
