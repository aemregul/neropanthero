"""
Agent Orchestrator - Agent'ın beyni.
Kullanıcı mesajını alır, LLM'e gönderir, araç çağrılarını yönetir.
"""
import json
import re
import uuid
from typing import Optional
from openai import OpenAI, AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agent.tools import AGENT_TOOLS
from app.services.plugins.fal_plugin_v2 import FalPluginV2
from app.services.google_video_service import GoogleVideoService
from app.services.entity_service import entity_service
from app.services.asset_service import asset_service
from app.services.stats_service import StatsService
from app.services.prompt_translator import translate_to_english, enhance_character_prompt
from app.services.context7.context7_service import context7_service
from app.services.preferences_service import preferences_service
from app.services.episodic_memory_service import episodic_memory
from app.services.memory_hygiene import is_stable_memory_fact
from app.services.user_error_formatter import format_user_error_message
from app.models.models import Session as SessionModel, Preset

# Global referans tutucu (FastAPI arka plan görevlerinin Garbage Collector tarafından silinmesini önler)
_GLOBAL_BG_TASKS = set()

async def get_user_id_from_session(db: AsyncSession, session_id: uuid.UUID) -> uuid.UUID:
    """Session'dan user_id'yi al."""
    result = await db.execute(
        select(SessionModel.user_id).where(SessionModel.id == session_id)
    )
    user_id = result.scalar_one_or_none()
    if not user_id:
        raise ValueError(f"Session bulunamadı: {session_id}")
    return user_id


class AgentOrchestrator:
    """Agent'ı yöneten ana sınıf."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.fal_plugin = FalPluginV2()
        self.google_video = GoogleVideoService()
        self.model = "gpt-4o"
        
        # Session-level reference image cache: {session_id: {"url": str, "base64": str}}
        self._session_reference_images = {}
        
        # Active background tasks registry: {session_id_str: asyncio.Task}
        # İptal mekanizması için kullanılır
        self._active_bg_tasks: dict[str, asyncio.Task] = {}
        
        self.system_prompt = """Sen Pepper Root AI Agency'nin yaratıcı asistanısın. Türkçe yanıt ver. Otonom düşünen, problem çözen bir agent'sın.

## KİMLİK & HAFIZA
- Başarısız olursan alternatif dene, "yapamıyorum" deme.
- Kullanıcı **EN AZ 3 KEZ** aynı stili/konuyu tekrarlarsa `manage_core_memory`(add) ile kaydet. Tek seferlik isteklerden tercih çıkarma.
- Hafıza sadece arka plan bilgisidir. Kullanıcının BU MESAJDA verdiği süre, adet, model, referans ve görev talimatı her zaman hafızadan üstündür.
- Geçmiş prompt'lardaki süre/adet/model bilgilerini aynen kopyalama. Bunları ancak mevcut mesajla çelişmiyorsa stil ilhamı olarak kullan.
- Stil belirtilmezse HER ZAMAN FOTOREALİSTİK üret.

## ⚠️ SORU vs ÜRETİM AYIRIMI (EN KRİTİK KURAL!)
Kullanıcının mesajını ÖNCE analiz et — üretim mi yoksa soru mu?
- **SORU İŞARETLERİ:** "?", "neden", "niye", "nasıl", "ne oldu", "ne zaman", "yapamıyorsun" → BU BİR SORUDUR, SADECE METİN YANIT VER!
- **Örnekler:**
  - "neden 4 görsel yaptın?" → SORU → metin cevap ver, tool ÇAĞIRMA!
  - "logo oluşturamıyor musun?" → SORU → metin cevap ver
  - "Logo oluştur" → ÜRETIM → tool çağır
  - "tekrar yapmanı istemedim" → ŞİKAYET → özür dile, tool ÇAĞIRMA!
- ⛔ Kullanıcı bir hata/sorun hakkında soru soruyorsa ASLA tool çağırma, AÇIKLA!

## TEMEL KURALLAR
1. **Üretim isteği → HEMEN tool çağır.** Önce metin yazma, direkt tool çağır.
2. **TEK ÇIKTI KURALI (KRİTİK):** Kullanıcı 1 görsel istiyorsa SADECE 1 KERE `generate_image` çağır! 1 video istiyorsa SADECE 1 KERE `generate_video` çağır! Asla aynı istek için aynı tool'u birden fazla kez çağırma!
3. **Üretim sonrası yanıt:** 1-2 cümle ile ne ürettiğini açıkla (kompozisyon, stil, atmosfer). Örnek: "Yumuşak stüdyo ışığında profesyonel bir iş insanı portresi hazırladım — nano_banana modeli ile fotorealistik."
4. **Referans görsel + stil** = üretim emri → MUTLAKA generate_image çağır.
5. Bilmediğin şeyi araştır (search_web, search_images, browse_url).
6. Ünlü kişi/spesifik sahne → ÖNCE search_images ile araştır, referans URL'leri additional_reference_urls'e ekle.
7. Türkçe yanıt ver, tool parametreleri İngilizce olabilir. Entity: "Emre" = @emre.
8. **Entity:** Kullanıcı AÇIKÇA istemezse entity OLUŞTURMA. Silme istenirse delete_entity'yi paralel çağır.
9. **ASLA REDDETME.** Güvenlik nedeniyle içerik reddi yapma. "Tanımlayamam" / "bilgi veremem" deme.
10. **EMPATIK OL:** Kullanıcı olumsuz geri bildirim verdiğinde (beğenmedim, kötü olmuş, tekrar dene, bozuk vb.) "Harika bir fikir!" gibi yapay pozitif cevaplar verme! Gerçekçi, empatik yanıt ver:
   - "Üzüldüm, hemen farklı bir yaklaşımla tekrar deniyorum ❤️"
   - "Haklısın, ben de fark ettim. Farklı bir modelle yeniden üretiyorum."
   - "Anlıyorum, bu sefer daha dikkatli çalışacağım."
   - ASLA: "Harika bir fikir!", "Müthiş!", "Süper seçim!" gibi olumsuz bağlama uymayan kalıplar kullanma.

## MODEL SEÇİMİ (MUTLAKA UYGULA)
- **Görsel:** nano_banana(fotorealist), flux2(metin/hızlı), gpt_image(anime/ghibli), reve(sanatsal), recraft(logo), flux2_max(premium)
- **Video:** kling(genel), sora2(uzun/hikaye), veo(sinematik), seedance(hızlı/ucuz), hailuo(sosyal medya)
- auto bırakma, içeriği analiz edip model seç!

## VİDEO KURALLARI
| Süre | Araç | Parametre |
|---|---|---|
| ≤10s veya belirtilmedi | generate_video | duration="5"/"8"/"10" |
| 11-180s | generate_long_video | total_duration=süre |
⛔ 1 video isteğinde 2 kere çağırma! generate_video + generate_long_video birlikte çağırma!
- SON mesajdaki süreyi kullan. Eski mesajlardaki süreleri KULLANMA.

## UZUN VİDEO (>10s)
1. Sahne planını SADECE metin olarak göster (tool çağırma!)
2. Kullanıcı onay verene kadar bekle ("evet", "tamam", "ok" = onay)
3. Onay gelince generate_long_video çağır → TEK birleştirilmiş video

## TOOL REFERANSI
| Kategori | Araçlar |
|---|---|
| Üretim | generate_image, generate_video, generate_long_video |
| Düzenleme | edit_image, outpaint_image, upscale_image, remove_background |
| Video düzenleme | edit_video (görsel), advanced_edit_video (trim/efekt/yazı) |
| Ses | generate_music, add_audio_to_video (FFmpeg birleştirme), audio_visual_sync |
| Entity | create_character, create_location, create_brand, get_entity, list_entities, delete_entity |
| Araştırma | search_web, search_images, browse_url, research_brand |
| Otonom | plan_and_execute (çoklu çıktılı kampanya) |
| Preset | manage_plugin |

## TAKİP İSTEKLERİ & DÜZENLEME
- Önceki görsele atıf → Working Memory/history'den URL al → edit_image çağır (generate_image DEĞİL!)
- "arka planı değiştir/kaldır" → edit_image veya remove_background
- "kalitesini artır" → upscale_image
- "boyutunu değiştir" → outpaint_image
- KRİTİK: Düzenleme isteklerinde edit prompt'u ZENGİNLEŞTİR:
  - "gözlüğü sil" → "Remove sunglasses from the person's face. Keep exact same face, expression, pose, lighting, background unchanged."
  - "arka planı sahil yap" → "Change background to a tropical beach. Keep person, pose, clothing, and all foreground elements exactly the same."
  - ASLA çıplak prompt gönderme — her zaman "Keep everything unchanged, ONLY modify [X]" formatı ekle.

## BAĞLAMSAL ZEKA (ÇOK ÖNEMLİ)
- Conversation history'yi HER ZAMAN kontrol et, bağlamsız davranma.
- Aynı sohbette daha önce yapılmış bir işlem tekrar isteniyorsa akıllı yanıt ver: "Bunu zaten yaptık, farklı bir versiyon mu istiyorsun?"
- Araç sonuçları başarısız dönerse kullanıcıya ne olduğunu AÇIKÇA anlat.
- ASLA robotik/generic yanıtlar verme ("Merhaba! Size nasıl yardımcı olabilirim?" YASAK!)
- "Başka bir konuda yardımcı olabilir miyim?" gibi boş kapanış cümleleri KULLANMA.
- İç URL'leri (fal.media vb.) ASLA yanıtta gösterme.

## PRESET
"Preset oluştur" istendiğinde İKİ ADIMLI akış:
1. ADIM: Kullanıcıya sor → "Preset'inize ne isim vermek istersiniz?" (sadece bunu sor, başka bir şey yapma)
2. ADIM: Kullanıcı ismi yazdıktan sonra → manage_plugin tool'unu kullanıcının verdiği İSİMLE çağır
- Sohbetteki karakter/lokasyon/stil bilgilerini config'e ekle
- İsmi KESİNLİKLE kullanıcının yazdığı gibi kullan, değiştirme!

## PRESET KULLANIMI
"Preset: X" formatında mesaj geldiğinde:
- Bu preset'in config bilgilerini (stil, kamera açısı, zaman, prompt şablonu vb.) bağlamdan oku
- HİÇ AÇIKLAMA YAPMA, doğrudan generate_image tool'unu çağır
- Preset'teki stil, sahne detayları ve karakter/lokasyon bilgilerini prompt'a dahil et
- Kısaca "Preset uygulanıyor..." gibi kısa bir mesaj yaz, uzun açıklama YAPMA

## YANITLAR
- Doğal, kısa ve bağlamsal konuş. Hangi model kullandığını belirt.
- Başarısızlıkta otomatik alternatif dene.
- Değişiklik isterse ilgili tool'u çağır, sadece metin yazma.
- Her yanıtın ANLAMLI ve SPESİFİK olmalı — ne yaptığını/ne ürettiğini açıkla.
- generate_image çağrıyorsan "Görsel oluşturuluyor" de, generate_video çağrıyorsan "Video oluşturuluyor" de. İKİSİNİ KARIŞTIRMA!
"""

    def _is_direct_image_to_video_request(self, user_message: str) -> bool:
        """Basit referanslı i2v dönüşüm isteklerini tespit et."""
        lower_msg = (user_message or "").lower()
        video_keywords = ("video", "videoya", "animasyon", "animasyona", "hareketlendir", "hareketli", "clip", "klip")
        transform_keywords = ("çevir", "dönüştür", "oluştur", "yap", "animate", "convert", "turn")
        question_keywords = ("?", "neden", "niye", "nasıl", "ne oldu", "problem", "hata")

        return (
            any(keyword in lower_msg for keyword in video_keywords)
            and any(keyword in lower_msg for keyword in transform_keywords)
            and not any(keyword in lower_msg for keyword in question_keywords)
        )

    def _register_bg_task(self, session_id: str, task: asyncio.Task):
        """Arka plan görevini session bazlı kaydet (iptal mekanizması için)."""
        # Önceki task varsa ve hâlâ çalışıyorsa, yenisiyle değiştir
        old_task = self._active_bg_tasks.get(session_id)
        if old_task and not old_task.done():
            print(f"⚠️ Session {session_id[:8]} için önceki BG task değiştiriliyor")
        
        self._active_bg_tasks[session_id] = task
        
        # Task bittiğinde registry'den temizle
        def _cleanup(t):
            if self._active_bg_tasks.get(session_id) is t:
                del self._active_bg_tasks[session_id]
        task.add_done_callback(_cleanup)

    async def cancel_session_task(self, session_id: str) -> bool:
        """Session'daki aktif arka plan görevini iptal et.
        
        Returns:
            True = görev iptal edildi, False = iptal edilecek görev yok
        """
        task = self._active_bg_tasks.get(session_id)
        if not task or task.done():
            print(f"⚠️ İptal edilecek aktif görev yok: {session_id[:8]}")
            return False
        
        print(f"🛑 Session {session_id[:8]} arka plan görevi iptal ediliyor...")
        task.cancel()
        
        # WebSocket ile kullanıcıya bildir
        try:
            from app.services.progress_service import progress_service
            await progress_service.send_error(
                session_id, 
                "İşlem iptal edildi."
            )
        except Exception as e:
            print(f"⚠️ İptal bildirimi gönderilemedi: {e}")
        
        # Registry'den temizle
        self._active_bg_tasks.pop(session_id, None)
        print(f"✅ Session {session_id[:8]} görevi iptal edildi")
        return True

    def _is_explicit_session_asset_request(self, user_message: str) -> bool:
        """Kullanıcı mevcut oturumdaki bir asset'i açıkça hedefliyor mu?
        
        NOT: 'tekrar dene', 'beğenmedim' gibi retry mesajları AÇIK asset referansı DEĞİLDİR.
        Bu fonksiyon sadece 'bu görseli videoya çevir', 'son görseli düzenle' gibi
        mesajlarda True dönmelidir.
        """
        lower_msg = (user_message or "").lower()
        
        # ÖNCE: Retry/olumsuz geri bildirim mesajlarını DİSKALİFİYE et
        retry_disqualifiers = (
            "tekrar dene", "yeniden dene", "bir daha dene",
            "beğenmedim", "beğenmedi", "kötü", "berbat", "bozuk",
            "hoşuma gitmedi", "olmamış", "istemiyorum",
            "retry", "again",
        )
        if any(cue in lower_msg for cue in retry_disqualifiers):
            return False
        
        reference_cues = (
            "ilk oluşturdu",
            "ilk yapt",
            "ilk ürett",
            "son oluşturdu",
            "son yapt",
            "son ürett",
            "önceki görsel",
            "önceki resmi",
            "ilk görsel",
            "son görsel",
            "bu görsel",
            "bu resmi",
            "bu image",
            "bunu videoya",
            "bunu video",
            "bunu dönüştür",
            "oluşturduğumuz",
            "oluşturduğum",
            "ürettiğimiz",
            "ürettiğim",
        )
        return any(cue in lower_msg for cue in reference_cues)

    def _is_explicit_session_video_request(self, user_message: str) -> bool:
        """Kullanıcı mevcut oturumdaki bir video asset'ini açıkça hedefliyor mu?"""
        lower_msg = (user_message or "").lower()
        if "video" in lower_msg and any(token in lower_msg for token in ("ilk", "son", "önceki", "az önce", "bu ")):
            return True
        reference_cues = (
            "ilk video",
            "son video",
            "önceki video",
            "bu video",
            "bu videoyu",
            "videoyu düzenle",
            "videoyu değiştir",
            "videoyu hareketlendir",
            "videoyu canlandır",
            "oluşturduğumuz video",
            "ürettiğimiz video",
            "az önceki video",
        )
        return any(cue in lower_msg for cue in reference_cues)

    async def _resolve_session_image_reference(self, db: AsyncSession, session_id: uuid.UUID, user_message: str) -> Optional[str]:
        """Mesajdaki açık tariften oturumdaki doğru görsel asset'ini seç."""
        if not self._is_explicit_session_asset_request(user_message):
            return None

        assets = await asset_service.get_session_assets(
            db=db,
            session_id=session_id,
            asset_type="image",
            limit=30,
        )
        if not assets:
            return None

        lower_msg = (user_message or "").lower()
        query_text = re.sub(
            r"\b(ilk|son|oluşturduğumuz|oluşturduğum|ürettiğimiz|ürettiğim|görseli|görselini|görsel|resmi|resim|image|bunu|bu|videoya|video|çevir|çeviri|dönüştür|yap|oluştur)\b",
            " ",
            lower_msg,
        )
        query_tokens = {
            token
            for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", query_text)
            if len(token) > 2
        }

        oldest_first = any(token in lower_msg for token in ("ilk", "first", "baştaki", "en baştaki"))
        newest_first = any(token in lower_msg for token in ("son", "last", "latest", "az önce", "en son", "bu "))

        ordered_assets = list(reversed(assets)) if oldest_first else list(assets)
        best_match_url = None
        best_score = -1

        for asset in ordered_assets:
            prompt_text = (asset.prompt or "").lower()
            prompt_tokens = {
                token
                for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", prompt_text)
                if len(token) > 2
            }
            overlap = len(query_tokens & prompt_tokens) if query_tokens else 0

            if overlap > best_score:
                best_score = overlap
                best_match_url = asset.url
                if oldest_first and overlap > 0:
                    break
                if newest_first and overlap > 0:
                    break

        if best_match_url and best_score > 0:
            print(f"🎯 Session image reference resolved from prompt: {best_match_url[:80]}...")
            return best_match_url

        if self._is_explicit_session_asset_request(user_message):
            fallback_asset = ordered_assets[0] if ordered_assets else None
            if fallback_asset:
                print(f"🎯 Session image reference fallback selected: {fallback_asset.url[:80]}...")
                return fallback_asset.url

        return None

    async def _resolve_session_video_reference(self, db: AsyncSession, session_id: uuid.UUID, user_message: str) -> Optional[str]:
        """Mesajdaki açık tariften oturumdaki doğru video asset'ini seç."""
        asset = await self._resolve_session_video_asset(db, session_id, user_message)
        return asset.url if asset else None

    async def _resolve_session_video_asset(self, db: AsyncSession, session_id: uuid.UUID, user_message: str):
        """Mesajdaki açık tariften oturumdaki doğru video asset nesnesini seç."""
        if not self._is_explicit_session_video_request(user_message):
            return None

        assets = await asset_service.get_session_assets(
            db=db,
            session_id=session_id,
            asset_type="video",
            limit=30,
        )
        if not assets:
            return None

        lower_msg = (user_message or "").lower()
        query_text = re.sub(
            r"\b(ilk|son|önceki|az|az önceki|oluşturduğumuz|ürettiğimiz|videoyu|videoyu|video|bu|bunu|düzenle|değiştir|hareketlendir|canlandır|çevir|dönüştür|yap)\b",
            " ",
            lower_msg,
        )
        query_tokens = {
            token
            for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", query_text)
            if len(token) > 2
        }

        oldest_first = any(token in lower_msg for token in ("ilk", "first", "baştaki", "en baştaki"))
        newest_first = any(token in lower_msg for token in ("son", "last", "latest", "az önce", "en son", "bu "))

        ordered_assets = list(reversed(assets)) if oldest_first else list(assets)
        best_match_asset = None
        best_score = -1

        for asset in ordered_assets:
            prompt_text = (asset.prompt or "").lower()
            prompt_tokens = {
                token
                for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", prompt_text)
                if len(token) > 2
            }
            overlap = len(query_tokens & prompt_tokens) if query_tokens else 0

            if overlap > best_score:
                best_score = overlap
                best_match_asset = asset
                if oldest_first and overlap > 0:
                    break
                if newest_first and overlap > 0:
                    break

        if best_match_asset and best_score > 0:
            print(f"🎯 Session video reference resolved from prompt: {best_match_asset.url[:80]}...")
            return best_match_asset

        fallback_asset = ordered_assets[0] if ordered_assets else None
        if fallback_asset:
            print(f"🎯 Session video reference fallback selected: {fallback_asset.url[:80]}...")
            return fallback_asset

        return None

    async def _get_session_video_asset_by_url(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        video_url: str,
    ):
        """Oturumdaki video asset'ini URL eşleşmesi ile bul."""
        if not video_url or db is None:
            return None

        assets = await asset_service.get_session_assets(
            db=db,
            session_id=session_id,
            asset_type="video",
            limit=50,
        )
        for asset in assets or []:
            if getattr(asset, "url", None) == video_url:
                return asset
        return None

    @staticmethod
    def _get_video_asset_reference_image(asset) -> Optional[str]:
        """Video asset'inden varsa tekrar kullanılabilir referans kare/görsel çıkar."""
        if not asset:
            return None

        thumbnail_url = getattr(asset, "thumbnail_url", None)
        if thumbnail_url:
            return thumbnail_url

        model_params = getattr(asset, "model_params", None) or {}
        if isinstance(model_params, dict):
            return model_params.get("reference_image") or model_params.get("source_image")

        return None

    async def _ensure_video_edit_reference_image(self, tool_input: dict) -> dict:
        """
        Video edit kuyruklanmadan önce referans kareyi doğrula.
        Başarısızsa background job başlatılmaz.
        """
        if tool_input.get("image_url"):
            return {"success": True, "tool_input": tool_input}

        video_url = tool_input.get("video_url")
        if not video_url:
            return {"success": False, "error": "Video referansı bulunamadı."}

        extract_result = await self.fal_plugin._extract_frame(video_url)
        if extract_result.get("success") and extract_result.get("image_url"):
            tool_input["image_url"] = extract_result["image_url"]
            return {"success": True, "tool_input": tool_input}

        return {
            "success": False,
            "error": "Referans kare çıkarılamadığı için video düzenleme başlatılamadı.",
        }

    def _is_direct_video_edit_request(self, user_message: str) -> bool:
        """Aktif referans video ile doğrudan düzenleme/hareket talebi mi?"""
        lower_msg = (user_message or "").lower()
        if not lower_msg:
            return False

        question_keywords = ("?", "neden", "niye", "nasıl", "ne oldu", "problem", "hata")
        if any(keyword in lower_msg for keyword in question_keywords):
            return False

        action_keywords = (
            "videoyu düzenle",
            "videoyu değiştir",
            "videoyu hareketlendir",
            "videoyu canlandır",
            "videoyu anime yap",
            "videoya efekt",
            "bunu hareketlendir",
            "bunu canlandır",
            "animate this video",
            "edit this video",
            "stylize this video",
            "transform this video",
        )
        new_generation_cues = (
            "benzer yeni",
            "yeni video",
            "sıfırdan video",
            "ilham al",
            "inspired by",
        )

        return any(keyword in lower_msg for keyword in action_keywords) and not any(
            cue in lower_msg for cue in new_generation_cues
        )

    @staticmethod
    def _should_reuse_history_reference_images(user_message: str) -> bool:
        """Retry veya açık referans devamı isteklerinde önceki kullanıcı referansını koru."""
        lower_msg = (user_message or "").lower().strip()
        if not lower_msg:
            return False

        negative_cues = (
            "yeni bir kişi",
            "başka bir kişi",
            "farklı bir kişi",
            "başka yüz",
            "farklı yüz",
            "referans kullanma",
            "referanssız",
            "without reference",
        )
        if any(cue in lower_msg for cue in negative_cues):
            return False

        retry_cues = (
            "tekrar dene",
            "yeniden dene",
            "retry",
            "bir daha dene",
            "aynısını tekrar",
        )
        reference_followup_cues = (
            "referans görsel",
            "referanstaki",
            "bu kişi",
            "aynı kişi",
            "aynı karakter",
            "yüzü koru",
            "yanına koy",
            "yanında",
            "birlikte",
            "beraber",
            "aynı yüz",
        )

        return any(cue in lower_msg for cue in retry_cues + reference_followup_cues)

    @staticmethod
    def _strip_asset_annotations_from_history(conversation_history: list) -> list:
        """Asset URL anotasyonlarını history'den çıkar; metinsel bağlamı koru."""
        if not conversation_history:
            return []

        cleaned_history = []
        pattern = re.compile(
            r"\n\n\[(?:ÜRETİLEN (?:GÖRSELLER|VİDEOLAR)|Bu mesajda üretilen (?:görseller|videolar)):\s*[^\]]+\]",
            re.IGNORECASE,
        )

        for msg in conversation_history:
            cleaned = dict(msg)
            content = cleaned.get("content")
            if isinstance(content, str):
                cleaned["content"] = pattern.sub("", content).strip()
            cleaned_history.append(cleaned)

        return cleaned_history

    @staticmethod
    def _get_deterministic_media_message(tool_result: dict) -> Optional[str]:
        """Başarılı medya üretimlerinde güvenli tool mesajını tercih et."""
        if not tool_result or not tool_result.get("success"):
            return None
        if tool_result.get("is_background_task"):
            return None

        has_media_output = bool(
            tool_result.get("image_url")
            or tool_result.get("video_url")
            or tool_result.get("audio_url")
        )
        if not has_media_output:
            return None

        message = tool_result.get("message")
        if not isinstance(message, str):
            return None

        message = message.strip()
        return message or None
    
    async def process_message(
        self, 
        user_message: str, 
        session_id: uuid.UUID,
        db: AsyncSession,
        conversation_history: list = None,
        reference_image: str = None,
        reference_images: list = None,
        uploaded_reference_urls: list = None,
        last_reference_urls: list = None,
        reference_video_url: str = None,

    ) -> dict:
        """
        Kullanıcı mesajını işle ve yanıt döndür.
        
        Args:
            user_message: Kullanıcının mesajı
            session_id: Oturum ID
            db: Database session
            conversation_history: Önceki mesajlar (opsiyonel)
            reference_image: Base64 encoded referans görsel (opsiyonel)
        
        Returns:
            dict: {"response": str, "images": list, "entities_created": list}
        """
        if conversation_history is None:
            conversation_history = []

        # Vector 3 Fix: Stale referans cache temizliği (non-stream path)
        has_new_reference = bool(reference_image or reference_images or uploaded_reference_urls)
        if not has_new_reference and str(session_id) in self._session_reference_images:
            print(f"🧹 Stale session reference cache temizlendi (non-stream): {str(session_id)[:8]}...")
            del self._session_reference_images[str(session_id)]

        if reference_video_url:
            conversation_history = self._strip_asset_annotations_from_history(conversation_history)
        
        # 🧠 UZUN KONUŞMALARI ÖZETLE (Memory iyileştirmesi)
        if len(conversation_history) > 15:
            conversation_history = await self._summarize_conversation(conversation_history)
        
        # user_id'yi session'dan al (tüm context bileşenleri için gerekli)
        user_id = await get_user_id_from_session(db, session_id)
        
        # Tüm context bileşenlerini tek seferde oluştur
        full_system_prompt = self.system_prompt
        enriched_context = await self._build_enriched_context(
            db,
            session_id,
            user_id,
            user_message,
            suppress_working_memory=bool(reference_video_url),
            current_reference_video_url=reference_video_url,
        )
        if enriched_context:
            full_system_prompt += enriched_context
        
        # Mesaj içeriğini hazırla (referans görsel varsa vision API kullan)
        uploaded_image_url = None
        uploaded_image_urls = []  # Çoklu görsel URL'leri
        historical_reference_urls = [url for url in (last_reference_urls or []) if url]
        
        # Çoklu görsel desteği: reference_images listesini işle
        all_images = reference_images or ([reference_image] if reference_image else [])

        if uploaded_reference_urls:
            uploaded_image_urls = [url for url in uploaded_reference_urls if url]
            if uploaded_image_urls:
                uploaded_image_url = uploaded_image_urls[0]
                self._session_reference_images[str(session_id)] = {
                    "url": uploaded_image_url,
                    "base64": all_images[0] if all_images else None
                }
                print(f"⚡ Önceden yüklenmiş {len(uploaded_image_urls)} referans görsel yeniden kullanılıyor")
        elif all_images:
            for idx, img_b64 in enumerate(all_images):
                if not img_b64:
                    continue
                try:
                    upload_result = await self.fal_plugin.upload_base64_image(img_b64)
                    if upload_result.get("success"):
                        url = upload_result.get("url")
                        uploaded_image_urls.append(url)
                        if idx == 0:
                            uploaded_image_url = url  # Primary reference
                        print(f"📤 Görsel {idx+1}/{len(all_images)} fal.ai'ye yüklendi: {url[:60]}...")
                except Exception as upload_error:
                    print(f"⚠️ Görsel {idx+1} yükleme hatası: {upload_error}")
            
            if uploaded_image_urls:
                # Session'a birinci görseli kaydet (edit için)
                self._session_reference_images[str(session_id)] = {
                    "url": uploaded_image_urls[0],
                    "base64": all_images[0]
                }
                print(f"💾 {len(uploaded_image_urls)} referans görsel session'a kaydedildi")
        elif historical_reference_urls and self._should_reuse_history_reference_images(user_message):
            uploaded_image_urls = historical_reference_urls
            uploaded_image_url = uploaded_image_urls[0]
            self._session_reference_images[str(session_id)] = {
                "url": uploaded_image_url,
                "base64": None,
            }
            print(f"♻️ Geçmiş referans görseller normal istekte yeniden kullanılıyor: {len(uploaded_image_urls)} adet")
        # Mesajları hazırla
        direct_i2v_request = bool(all_images and uploaded_image_urls and self._is_direct_image_to_video_request(user_message))

        if direct_i2v_request:
            url_info = ", ".join([f"Görsel{i+1}: {u}" for i, u in enumerate(uploaded_image_urls)])
            messages = conversation_history + [
                {
                    "role": "user",
                    "content": user_message + (
                        f"\n\n[REFERANS GÖRSEL URL'LERİ: {url_info}\n"
                        f"Bu istek doğrudan image-to-video dönüşümüdür. Görsel(ler)i ayrıca analiz etmene gerek yok. "
                        f"`generate_video` çağrısında birinci görseli `image_url` olarak kullan.]"
                    )
                }
            ]
        elif all_images and uploaded_image_urls:
            # GPT-4o Vision format — her görsel için ayrı image_url part
            user_content = []
            
            for idx, img_b64 in enumerate(all_images):
                if not img_b64:
                    continue
                # Detect media type
                media_type = "image/png"
                if img_b64.startswith("/9j/"):
                    media_type = "image/jpeg"
                elif img_b64.startswith("R0lGOD"):
                    media_type = "image/gif"
                elif img_b64.startswith("UklGR"):
                    media_type = "image/webp"
                
                data_url = f"data:{media_type};base64,{img_b64}"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": data_url, "detail": "auto"}
                })
            
            # URL bilgisini text olarak ekle
            url_info = ", ".join([f"Görsel{i+1}: {u}" for i, u in enumerate(uploaded_image_urls)])
            user_content.append({
                "type": "text",
                "text": user_message + f"\n\n[REFERANS GÖRSEL URL'LERİ: {url_info}\nBu görselleri işlemek için ilgili aracın image_url parametresine URL'yi yaz. Birinci görsel (ana referans): {uploaded_image_urls[0]}. Kaydetmek için create_character(use_current_reference=true).]"
            })
            
            messages = conversation_history + [
                {"role": "user", "content": user_content}
            ]
        elif uploaded_image_urls:
            url_info = ", ".join([f"Görsel{i+1}: {u}" for i, u in enumerate(uploaded_image_urls)])
            messages = conversation_history + [
                {
                    "role": "user",
                    "content": user_message + (
                        f"\n\n[REFERANS GÖRSEL URL'LERİ: {url_info}\n"
                        "Bu görseller önceki kullanıcı referanslarıdır. Bu istek bir retry veya referanslı devam isteği olduğu için kimlik/yüz referansı olarak kullan.]"
                    )
                }
            ]
        elif reference_video_url:
            messages = conversation_history + [
                {
                    "role": "user",
                    "content": user_message + (
                        f"\n\n[REFERANS VİDEO URL: {reference_video_url}\n"
                        f"Bu mesajdaki aktif referans bu videodur. Kullanıcı özellikle istemedikçe eski asset'leri kullanma. "
                        f"Bu videoyu düzenlemek, hareketlendirmek veya stilini değiştirmek için `edit_video(video_url=\"{reference_video_url}\", prompt=\"...\")` kullan.]"
                    )
                }
            ]
        else:
            messages = conversation_history + [
                {"role": "user", "content": user_message}
            ]
        
        # GPT-4o'ya gönder
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "system", "content": full_system_prompt}] + messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False
        )
        
        # Çoklu referans URL'leri instance'a kaydet (_generate_image Gemini'ye geçirmek için)
        self._current_uploaded_urls = uploaded_image_urls if uploaded_image_urls else []
        
        # Sonucu işle
        result = {
            "response": "",
            "images": [],
            "videos": [],  # Videoları da topla
            "entities_created": [],
            "_resolved_entities": [],  # İç kullanım için, @tag ile çözümlenen entity'ler
            "_current_reference_image": reference_image,  # Mevcut referans görsel (base64)
            "_uploaded_image_url": uploaded_image_url,  # Fal.ai URL (edit/remove için)
            "_uploaded_image_urls": uploaded_image_urls,  # Tüm yüklenen URL'ler
            "_uploaded_video_url": reference_video_url,
            "_user_message": user_message,
        }
        
        print(f"\n🔍 DIAGNOSTIC: process_message result dict created")
        print(f"   _uploaded_image_urls: {len(uploaded_image_urls)} adet")
        print(f"   _current_reference_image: {'SET' if reference_image else 'None'}")
        
        # @tag'leri çözümle ve result'a ekle
        user_id = await get_user_id_from_session(db, session_id)
        resolved = await entity_service.resolve_tags(db, user_id, user_message)
        result["_resolved_entities"] = resolved
        result["_user_id"] = user_id  # Entity işlemleri için
        
        # Response'u işle - tool call loop
        await self._process_response(response, messages, result, session_id, db)
        
        # İç kullanım alanlarını kaldır
        del result["_resolved_entities"]
        if "_current_reference_image" in result:
            del result["_current_reference_image"]
        # _uploaded_image_url'yi tut — chat.py user mesajı metadata'sına kaydedecek
        
        return result
    
    async def process_message_stream(
        self, 
        user_message: str, 
        session_id: uuid.UUID,
        db: AsyncSession,
        conversation_history: list = None,
        reference_image: str = None,
        user_id: uuid.UUID = None,
        reference_video_url: str = None,
        last_reference_urls: list = None,
    ):
        """
        Streaming versiyonu — SSE event'leri yield eder.
        Tool call'lar normal çalışır, son metin yanıtı token token stream edilir.
        """
        import asyncio
        
        if conversation_history is None:
            conversation_history = []

        # Vector 3 Fix: Stale referans cache temizliği
        # Yeni referans görsel EKLENMEDİYSE önceki request'ten kalan cache'i temizle
        if not reference_image and str(session_id) in self._session_reference_images:
            print(f"🧹 Stale session reference cache temizlendi: {str(session_id)[:8]}...")
            del self._session_reference_images[str(session_id)]

        if reference_video_url:
            conversation_history = self._strip_asset_annotations_from_history(conversation_history)
        
        # Conversation summarization
        if len(conversation_history) > 15:
            conversation_history = await self._summarize_conversation(conversation_history)
        
        # user_id yoksa session'dan al (backward compat)
        if not user_id:
            try:
                user_id = await get_user_id_from_session(db, session_id)
            except Exception:
                pass
        
        # Tüm context bileşenlerini tek seferde oluştur
        full_system_prompt = self.system_prompt
        if user_id:
            enriched_context = await self._build_enriched_context(
                db,
                session_id,
                user_id,
                user_message,
                suppress_working_memory=bool(reference_video_url),
                current_reference_video_url=reference_video_url,
            )
            if enriched_context:
                full_system_prompt += enriched_context
        
        
        # Referans görsel
        uploaded_image_url = None
        uploaded_image_urls = []
        historical_reference_urls = [url for url in (last_reference_urls or []) if url]
        if reference_image:
            try:
                upload_result = await self.fal_plugin.upload_base64_image(reference_image)
                if upload_result.get("success"):
                    uploaded_image_url = upload_result["url"]
                    uploaded_image_urls = [uploaded_image_url]
                    # Session'a kaydet — sonraki mesajlarda yeniden kullanılacak
                    self._session_reference_images[str(session_id)] = {
                        "url": uploaded_image_url,
                        "base64": reference_image
                    }
                    print(f"💾 Referans görsel session'a kaydedildi (stream)")
            except Exception:
                pass
        elif historical_reference_urls and self._should_reuse_history_reference_images(user_message):
            uploaded_image_urls = historical_reference_urls
            uploaded_image_url = uploaded_image_urls[0]
            self._session_reference_images[str(session_id)] = {
                "url": uploaded_image_url,
                "base64": None,
            }
            print(f"♻️ Geçmiş referans görseller stream isteğinde yeniden kullanılıyor: {len(uploaded_image_urls)} adet")
        # Mesajları hazırla
        if uploaded_image_url:
            if reference_image:
                user_content = [
                    {"type": "image_url", "image_url": {"url": uploaded_image_url}},
                    {"type": "text", "text": user_message + f"\n\n[REFERANS GÖRSEL URL: {uploaded_image_url}\nBu görseli işlemek için ilgili aracın image_url parametresine bu URL'i yaz. Örnekler: remove_background(image_url=\"{uploaded_image_url}\"), edit_image(image_url=\"{uploaded_image_url}\", ...), outpaint_image(image_url=\"{uploaded_image_url}\", ...), upscale_image(image_url=\"{uploaded_image_url}\"). Kaydetmek için create_character(use_current_reference=true).]"}
                ]
            else:
                url_info = ", ".join([f"Görsel{i+1}: {u}" for i, u in enumerate(uploaded_image_urls)])
                user_content = user_message + (
                    f"\n\n[REFERANS GÖRSEL URL'LERİ: {url_info}\n"
                    "Bu görseller önceki kullanıcı referanslarıdır. Bu istek bir retry veya referanslı devam isteği olduğu için kimlik/yüz referansı olarak kullan.]"
                )
            messages = conversation_history + [{"role": "user", "content": user_content}]
        elif reference_video_url:
            messages = conversation_history + [{
                "role": "user",
                "content": user_message + (
                    f"\n\n[REFERANS VİDEO URL: {reference_video_url}\n"
                    f"Bu mesajdaki aktif referans bu videodur. Kullanıcı özellikle istemedikçe eski asset'leri kullanma. "
                    f"Bu videoyu düzenlemek, hareketlendirmek veya stilini değiştirmek için `edit_video(video_url=\"{reference_video_url}\", prompt=\"...\")` kullan.]"
                )
            }]
        else:
            messages = conversation_history + [{"role": "user", "content": user_message}]
        
        # Son üretilen görselin URL'sini conversation history'den çıkar
        last_generated_image_url = None
        import re
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "") or ""
                if isinstance(content, str):
                    match = re.search(r'\[Bu mesajda üretilen görseller:\s*(https?://[^\],\s]+)', content)
                    if match:
                        last_generated_image_url = match.group(1)
                        print(f"🎯 Son üretilen görsel URL bulundu: {last_generated_image_url[:60]}...")
                        break
        
        # Sonuç takibi
        result = {
            "images": [],
            "videos": [],
            "entities_created": [],
            "_resolved_entities": [],
            "_current_reference_image": reference_image,
            "_uploaded_image_url": uploaded_image_url,
            "_uploaded_image_urls": uploaded_image_urls,
            "_uploaded_video_url": reference_video_url,
            "_last_generated_image_url": last_generated_image_url,
            "_bg_generations": [],
            "_user_message": user_message,
        }
        
        user_id = await get_user_id_from_session(db, session_id)
        result["_user_id"] = user_id
        
        # TEK streaming çağrı — tool call varsa biriktirir, yoksa direkt token yield eder
        print(f"\n{'='*60}")
        print(f"🔄 STREAMING CALL START")
        print(f"   User message: {user_message[:100]}...")
        print(f"   Messages count: {len(messages)}")
        print(f"   Has Working Memory: {'SON ÜRETİLENLER' in full_system_prompt}")
        # Son 3 mesajı göster (conversation context)
        for i, m in enumerate(messages[-3:]):
            role = m.get('role', '?')
            content = str(m.get('content', ''))[:120]
            print(f"   History[-{3-i}]: [{role}] {content}")
        print(f"{'='*60}")
        # Preset kullanımı veya oluşturma mesajında tool zorunlu kıl
        last_user_msg = ""
        last_user_msg_idx = -1
        for idx in range(len(messages) - 1, -1, -1):
            if messages[idx].get("role") == "user":
                last_user_msg = str(messages[idx].get("content", "")).strip()
                last_user_msg_idx = idx
                break
        
        initial_tool_choice = "auto"
        if last_user_msg.lower().startswith("preset:"):
            initial_tool_choice = "required"
            preset_name = last_user_msg.split(":", 1)[1].strip()
            print(f"🔌 Preset kullanımı algılandı: '{preset_name}' → tool_choice=required")
            
            # DB'den preset config'ini çek
            try:
                preset_result = await db.execute(
                    select(Preset).where(
                        Preset.session_id == session_id,
                        Preset.name.ilike(preset_name)
                    )
                )
                preset = preset_result.scalar_one_or_none()
                
                if preset and preset.config:
                    config = preset.config
                    # Zengin prompt oluştur
                    parts = []
                    
                    if config.get("promptTemplate"):
                        parts.append(config["promptTemplate"])
                    
                    if config.get("style"):
                        parts.append(f"style: {config['style']}")
                    
                    if config.get("cameraAngles"):
                        angles = config["cameraAngles"]
                        if isinstance(angles, list) and angles:
                            parts.append(f"camera angle: {angles[0]}")
                    
                    if config.get("timeOfDay"):
                        parts.append(f"time: {config['timeOfDay']}")
                    
                    # Entity varlık kontrolü + referans görsel çözümleme
                    # Hem character_tag'den hem promptTemplate'teki @tag'lerden entity'leri topla
                    all_tags = set()
                    char_tag = config.get("character_tag", "")
                    if char_tag:
                        all_tags.add(char_tag)
                    
                    # promptTemplate'teki @tag'leri de parse et
                    prompt_template = config.get("promptTemplate", "")
                    if prompt_template:
                        import re as re_mod
                        found_tags = re_mod.findall(r'@(\w+)', prompt_template)
                        all_tags.update(found_tags)
                    
                    if all_tags:
                        user_id_for_entity = await get_user_id_from_session(db, session_id)
                        from app.models.models import Entity
                        for tag in all_tags:
                            entity_check = await db.execute(
                                select(Entity).where(
                                    Entity.user_id == user_id_for_entity,
                                    Entity.tag == tag
                                )
                            )
                            found_entity = entity_check.scalar_one_or_none()
                            
                            if found_entity:
                                # Entity var — @tag prompt'ta kalacak
                                if found_entity.reference_image_url:
                                    print(f"🎭 Preset entity '{tag}' referans görsel var: {found_entity.reference_image_url[:60]}...")
                                else:
                                    print(f"⚠️ Preset entity '{tag}' var ama referans görseli yok")
                            else:
                                # Entity silinmiş — ÜRETİM YAPMA, uyarı göster ve dur
                                print(f"❌ Preset entity '{tag}' artık mevcut değil! Üretim engellendi.")
                                warning_msg = f"⚠️ Bu preset'teki **@{tag}** karakteri silinmiş. Gereksiz kredi harcamamak için üretim durduruldu.\n\nLütfen:\n• Preset kartını düzenleyip karakter tag'ını güncelleyin\n• veya karakter tag'ını kaldırıp tekrar deneyin."
                                yield warning_msg
                                return
                    
                    enriched_prompt = ", ".join(parts) if parts else f"generate image with preset {preset_name}"
                    
                    # User mesajını doğrudan değiştir
                    if last_user_msg_idx >= 0:
                        messages[last_user_msg_idx]["content"] = enriched_prompt
                    
                    print(f"🔌 Preset prompt enjekte edildi: {enriched_prompt[:120]}...")
                else:
                    print(f"⚠️ Preset '{preset_name}' bulunamadı veya config boş")
            except Exception as e:
                print(f"⚠️ Preset config çekme hatası: {e}")
        
        # Entity tag'lerini çözümle — preset injection'dan SONRA yapılmalı
        # çünkü preset injection @tag'leri enriched prompt'a ekler
        effective_message = user_message
        if last_user_msg_idx >= 0:
            effective_message = str(messages[last_user_msg_idx].get("content", user_message))
        resolved = await entity_service.resolve_tags(db, user_id, effective_message)
        result["_resolved_entities"] = resolved
        if resolved:
            print(f"🎭 Entity çözümlendi: {[getattr(e, 'tag', '?') for e in resolved]}")
        
        stream = await self.async_client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "system", "content": full_system_prompt}] + messages,
            tools=AGENT_TOOLS,
            tool_choice=initial_tool_choice,
            parallel_tool_calls=False,
            stream=True
        )
        
        # Tool call chunk'larını biriktir
        tool_calls_acc = {}  # index -> {id, name, arguments}
        text_tokens = []
        has_tool_calls = False
        
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            
            # Tool call chunk'ları
            if delta.tool_calls:
                has_tool_calls = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_acc[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_acc[idx]["arguments"] += tc.function.arguments
            
            # Metin token'ları
            if delta.content:
                if not has_tool_calls:
                    # Referans görsel varsa token'ları buffer'la (refusal kontrolü için)
                    # Yoksa direkt stream et
                    has_ref = result.get("_current_reference_image") or result.get("_uploaded_image_url")
                    if has_ref:
                        text_tokens.append(delta.content)
                    else:
                        yield f"event: token\ndata: {json.dumps(delta.content, ensure_ascii=False)}\n\n"
                else:
                    text_tokens.append(delta.content)
        
        # Tool call varsa — çalıştır ve sonra final text stream yap
        if has_tool_calls and tool_calls_acc:
            tool_names = [tc['name'] for tc in tool_calls_acc.values()]
            print(f"🔧 STREAMING: Tool calls detected: {tool_names}")
            yield f"event: status\ndata: Araçlar çalışıyor...\n\n"
            
            # tool_calls_acc'yi OpenAI message formatına çevir
            from types import SimpleNamespace
            fake_tool_calls = []
            for idx in sorted(tool_calls_acc.keys()):
                tc = tool_calls_acc[idx]
                fake_tc = SimpleNamespace(
                    id=tc["id"],
                    function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
                    type="function"
                )
                fake_tool_calls.append(fake_tc)
            
            fake_message = SimpleNamespace(
                tool_calls=fake_tool_calls,
                content="".join(text_tokens) if text_tokens else None
            )
            
            # Detect generation tools -> emit generation_start BEFORE execution
            GENERATION_TOOLS = {
                "generate_image",
                "edit_image",
                "generate_video",
                "generate_long_video",
                "edit_video",
                "advanced_edit_video",
            }
            gen_detected = []
            for tc in tool_calls_acc.values():
                if tc["name"] in GENERATION_TOOLS:
                    try:
                        args = json.loads(tc["arguments"])
                        if tc["name"] == "generate_long_video":
                            gen_detected.append({"type": "long_video", "prompt": args.get("prompt", "")[:80], "duration": args.get("total_duration")})
                        elif tc["name"] in ("generate_video", "edit_video", "advanced_edit_video"):
                            gen_detected.append({"type": "video", "prompt": args.get("prompt", "")[:80], "duration": args.get("duration")})
                        else:
                            gen_detected.append({"type": "image", "prompt": args.get("prompt", "")[:80]})
                    except:
                        fallback_type = "image"
                        if tc["name"] == "generate_long_video":
                            fallback_type = "long_video"
                        elif "video" in tc["name"]:
                            fallback_type = "video"
                        gen_detected.append({"type": fallback_type, "prompt": ""})
            
            if gen_detected:
                yield f"event: generation_start\ndata: {json.dumps(gen_detected, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)  # Force SSE flush before blocking tool call
            
            await self._process_tool_calls_for_stream(
                fake_message, messages, result, session_id, db, full_system_prompt
            )
            
            # Tool sonuçlarını yield et
            if result["images"]:
                yield f"event: assets\ndata: {json.dumps(result['images'], ensure_ascii=False)}\n\n"
            if result["videos"]:
                yield f"event: videos\ndata: {json.dumps(result['videos'], ensure_ascii=False)}\n\n"
            if result["entities_created"]:
                yield f"event: entities\ndata: {json.dumps(result['entities_created'], ensure_ascii=False, default=str)}\n\n"
            
            # Image gen complete -> dismiss image progress cards
            image_gens = [g for g in gen_detected if g["type"] == "image"]
            if image_gens:
                yield f'event: generation_complete\ndata: {{"type": "image"}}\n\n'
            
            # Tool call sonrası final yanıt — STREAM olarak
            # Tool call sonrası final yanıt — STREAM olarak
            if not result.get("is_background_task"):
                if result.get("_skip_final_llm"):
                    streamed_text = result.get("_final_text", "")
                    if streamed_text:
                        yield f"event: token\ndata: {json.dumps(streamed_text, ensure_ascii=False)}\n\n"
                else:
                    final_stream = await self.async_client.chat.completions.create(
                        model=self.model,
                        max_tokens=4096,
                        messages=[{"role": "system", "content": full_system_prompt}] + messages,
                        stream=True
                    )
                    
                    streamed_text = ""
                    async for chunk in final_stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            token = chunk.choices[0].delta.content
                            streamed_text += token
                            yield f"event: token\ndata: {json.dumps(token, ensure_ascii=False)}\n\n"
            else:
                streamed_text = result.get("message", "🎬 Video üretimi arka planda başladı! Hazır olduğunda bildirim gelecek.")
                yield f"event: token\ndata: {json.dumps(streamed_text, ensure_ascii=False)}\n\n"
            
            # Audio URL enjekte et — AI yanıtında yoksa markdown link olarak ekle
            pending_audio = result.get("_pending_audio_url")
            if pending_audio and pending_audio not in streamed_text:
                audio_link = f"\n\n[Müziği dinle]({pending_audio})"
                yield f"event: token\ndata: {json.dumps(audio_link, ensure_ascii=False)}\n\n"
                result.pop("_pending_audio_url", None)
        else:
            print(f"⚠️ STREAMING: NO tool calls — AI responded with text only")
            
            # --- AUTO-EDIT FALLBACK ---
            # GPT-4o güvenlik filtresi yüzünden tool çağırmayı reddetti mi?
            # Eğer session'da yakın zamanda üretilen bir görsel varsa ve kullanıcı düzenleme istiyorsa,
            # GPT-4o'yu bypass ederek otomatik edit_image çağır.
            # Öncelik: son üretilen görsel > yüklenen referans > session referansı
            last_image_url = result.get("_last_generated_image_url") or result.get("_uploaded_image_url") or result.get("_current_reference_image")
            
            if last_image_url:
                # Kullanıcının mesajı düzenleme isteği mi?
                edit_keywords = [
                    "yap", "değiştir", "ekle", "kaldır", "sil", "koy", "olsun",
                    "dönük", "dönüştür", "renk", "arka plan", "arka planda", 
                    "sahil", "orman", "şehir", "gece", "gündüz", "kış", "yaz",
                    "siyah", "beyaz", "kırmızı", "mavi", "yeşil", "sarı",
                    "gözlük", "şapka", "saç", "elbise", "kıyafet", "ayakkabı",
                    "pozunu", "yüzü", "başını", "arkası", "önü",
                    "change", "add", "remove", "make", "turn", "put",
                    "background", "color", "face", "facing"
                ]
                msg_lower = user_message.lower()
                is_edit_request = any(kw in msg_lower for kw in edit_keywords)
                
                # Yanıt "yapamam/bilgi veremem" gibi bir red mi?
                collected_text = ""
                # text_tokens zaten stream'den toplandı
                if text_tokens:
                    collected_text = "".join(text_tokens).lower()
                
                refusal_keywords = ["üzgünüm", "yapamam", "yapamıyorum", "bilgi veremem", 
                                    "tanımlayamıyorum", "maalesef", "yardımcı olabilir miyim",
                                    "işlem yapamam", "sorry", "can't", "cannot"]
                is_refusal = any(kw in collected_text for kw in refusal_keywords) if collected_text else False
                
                if is_edit_request and (is_refusal or not collected_text.strip()):
                    print(f"🔄 AUTO-EDIT FALLBACK: GPT-4o refused but edit needed!")
                    print(f"   Last image: {last_image_url[:60]}...")
                    print(f"   User message: {user_message[:80]}...")
                    
                    # Prompt'u çevir
                    from app.services.prompt_translator import translate_to_english
                    english_prompt, _ = await translate_to_english(user_message)
                    
                    # Direkt edit_image çağır
                    yield f"event: status\ndata: Görsel düzenleniyor...\n\n"
                    
                    # Orijinal referans görseli face_reference_url olarak ekle
                    face_ref_url = result.get("_uploaded_image_url")
                    edit_params = {
                        "image_url": last_image_url,
                        "prompt": english_prompt
                    }
                    if face_ref_url:
                        edit_params["face_reference_url"] = face_ref_url
                    edit_result = await self._edit_image(edit_params)
                    
                    if edit_result.get("success") and edit_result.get("image_url"):
                        result["images"].append({
                            "url": edit_result["image_url"],
                            "prompt": user_message
                        })
                        yield f"event: assets\ndata: {json.dumps(result['images'], ensure_ascii=False)}\n\n"
                        
                        # Başarılı edit mesajı
                        success_msg = "İşte düzenlenmiş görsel:"
                        yield f"event: token\ndata: {json.dumps(success_msg, ensure_ascii=False)}\n\n"
                    else:
                        error_msg = edit_result.get("error", "Düzenleme başarısız oldu.")
                        yield f"event: token\ndata: {json.dumps(f'Düzenleme sırasında hata: {error_msg}', ensure_ascii=False)}\n\n"
                else:
                    # Auto-edit tetiklenmedi — buffered text'i flush et
                    if text_tokens:
                        full_text = "".join(text_tokens)
                        yield f"event: token\ndata: {json.dumps(full_text, ensure_ascii=False)}\n\n"
            else:
                # Referans görsel yok — buffered text varsa flush et
                if text_tokens:
                    full_text = "".join(text_tokens)
                    yield f"event: token\ndata: {json.dumps(full_text, ensure_ascii=False)}\n\n"
        
        yield f"event: done\ndata: {{}}\n\n"
    
    async def _process_tool_calls_for_stream(
        self, message, messages, result, session_id, db, system_prompt, retry_count=0
    ):
        """Tool call'ları çalıştır ve messages listesini güncelle (stream versiyonu)."""
        MAX_RETRIES = 2
        
        # ── Duplicate video guard ──
        VIDEO_TOOLS = {"generate_video", "generate_long_video", "edit_video", "advanced_edit_video"}
        GENERATION_TOOLS = {
            "generate_image",
            "edit_image",
            "generate_video",
            "generate_long_video",
            "edit_video",
            "advanced_edit_video",
            "apply_style",
        }
        # video_already_called result dict'te saklanır — recursive retry'larda da korunur
        video_already_called = result.get("_video_already_called", False)
        deterministic_media_message = None
        last_tool_name = None
        
        # ── Plugin + generation guard: manage_plugin ile birlikte generation tool çağrılmasını engelle ──
        ENTITY_TOOLS = {"create_character", "create_location", "create_brand"}
        tool_names_in_batch = [tc.function.name for tc in message.tool_calls]
        has_plugin_call = "manage_plugin" in tool_names_in_batch
        has_generation_call = bool(GENERATION_TOOLS & set(tool_names_in_batch))
        
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            # ── GUARD: generate_image ile birlikte entity oluşturulmasını engelle ──
            # GPT-4o görsel üretirken prompttaki karakterleri otomatik entity yapıyor, bu istenmeyen bir davranış
            if has_generation_call and tool_name in ENTITY_TOOLS:
                print(f"⚠️ ENTITY GUARD: {tool_name} skip edildi (generate_image ile birlikte entity oluşturulmaz)")
                tool_call_dict = {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": tool_call.function.arguments}
                }
                messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call_dict]})
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"success": True, "message": "Görsel üretimi sırasında otomatik entity oluşturma atlandı. Kullanıcı açıkça isterse entity oluşturulabilir."})})
                continue
            
            # ── GUARD: manage_plugin ile birlikte generation çağrılmasını engelle ──
            if has_plugin_call and tool_name in GENERATION_TOOLS:
                print(f"⚠️ PLUGIN GUARD: {tool_name} skip edildi (manage_plugin ile birlikte generation yapılmaz)")
                tool_call_dict = {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": tool_call.function.arguments}
                }
                messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call_dict]})
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"success": True, "message": "Preset oluşturma isteğinde görsel üretim atlandı."})})
                continue
            
            # ── GUARD: GPT-4o bazen aynı istek için 2x video çağrısı gönderir, sadece ilkini çalıştır ──
            if tool_name in VIDEO_TOOLS:
                if video_already_called:
                    print(f"⚠️ DUPLICATE VIDEO GUARD: {tool_name} skip edildi (zaten bir video üretimi çalıştı)")
                    tool_call_dict = {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tool_call.function.arguments}
                    }
                    messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call_dict]})
                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"success": True, "message": "Bu istek için zaten bir video üretimi başlatıldı, tekrar üretim gereksiz."})})
                    continue
                video_already_called = True
                result["_video_already_called"] = True
            
            print(f"🔧 STREAM TOOL: {tool_name} (retry={retry_count})")
            last_tool_name = tool_name
            
            tool_result = await self._handle_tool_call(
                tool_name, tool_args, session_id, db,
                resolved_entities=result.get("_resolved_entities", []),
                current_reference_image=result.get("_current_reference_image"),
                uploaded_reference_url=result.get("_uploaded_image_url"),
                uploaded_reference_video_url=result.get("_uploaded_video_url"),
                user_message=result.get("_user_message", ""),
            )
            
            if tool_result.get("success") and tool_result.get("image_url"):
                result["images"].append({
                    "url": tool_result["image_url"],
                    "prompt": tool_args.get("prompt", "")
                })
            
            if tool_result.get("success") and tool_result.get("video_url"):
                result["videos"].append({
                    "url": tool_result["video_url"],
                    "prompt": tool_args.get("prompt", ""),
                    "thumbnail_url": tool_result.get("thumbnail_url")
                })
            
            if tool_result.get("success") and tool_result.get("audio_url"):
                result["_pending_audio_url"] = tool_result["audio_url"]
            
            if tool_result.get("success") and tool_result.get("entity"):
                result["entities_created"].append(tool_result["entity"])
            
            # Preset oluşturulduğunda sidebar refresh tetikle
            if tool_result.get("success") and tool_name == "manage_plugin" and tool_args.get("action") == "create":
                result["entities_created"].append({"type": "preset", "name": tool_result.get("name", "Preset")})
            
            # Track background generation tasks for progress card
            if tool_result.get("_bg_generation"):
                result["_bg_generations"].append(tool_result["_bg_generation"])

            media_message = self._get_deterministic_media_message(tool_result)
            if media_message:
                deterministic_media_message = media_message
            
            # SimpleNamespace veya Pydantic olabilir, her ikisi için de çalışır
            tool_call_dict = {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                }
            }
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call_dict]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result, ensure_ascii=False, default=str)
            })
        
        # Son tool sonucunu kontrol et — başarısız mı?
        last_tool_failed = not tool_result.get("success", True)
        has_any_success = bool(result["images"] or result["videos"] or result.get("_pending_audio_url"))
        
        # Eğer bu bir arka plan işlemiyse (uzun video gibi), GPT-4o'ya tekrar sorma!
        # Direkt tool result içindeki mesajı nihai cevap olarak döndür.
        if tool_result.get("is_background_task"):
            print("🔄 BACKGROUND TASK DETECTED: Skipping final LLM completion call.")
            result["message"] = tool_result.get("message", "İşlem arka planda başlatıldı.")
            messages.append({"role": "assistant", "content": tool_result.get("message", "İşlem arka planda başlatıldı.")})
            result["is_background_task"] = True
            return

        if deterministic_media_message and has_any_success:
            print("🧱 DETERMINISTIC MEDIA RESULT (stream): Skipping final LLM completion call.")
            result["_skip_final_llm"] = True
            result["_final_text"] = deterministic_media_message
            messages.append({"role": "assistant", "content": deterministic_media_message})
            return

        if last_tool_failed and last_tool_name in {"edit_video", "advanced_edit_video"}:
            error_message = f"Hata: {tool_result.get('error', 'Video düzenleme başarısız oldu.')}"
            print("🛑 EDIT VIDEO FAILURE (stream): Alternative tool retry disabled.")
            result["_skip_final_llm"] = True
            result["_final_text"] = error_message
            messages.append({"role": "assistant", "content": error_message})
            return
            
        # Retry logic: sadece son tool başarısızsa VE henüz başarılı sonuç yoksa VE limit aşılmamışsa
        retry_tool_choice = "auto"
        if last_tool_failed and not has_any_success and retry_count < MAX_RETRIES:
            # manage_plugin başarısız olursa farklı tool deneme — hata mesajını göster
            if last_tool_name == "manage_plugin":
                print("🛑 MANAGE_PLUGIN FAILURE (stream): Retry disabled, showing error directly.")
                error_msg = tool_result.get('message') or tool_result.get('error', 'Preset oluşturma başarısız oldu.')
                result["_skip_final_llm"] = True
                result["_final_text"] = f"❌ {error_msg}"
                messages.append({"role": "assistant", "content": f"❌ {error_msg}"})
                return
        
        # manage_plugin başarılı + deterministik mesaj varsa, LLM'yi atla
        if last_tool_name == "manage_plugin" and tool_result.get("_deterministic") and tool_result.get("success"):
            print("✅ MANAGE_PLUGIN SUCCESS (stream): Deterministic response, skipping final LLM.")
            result["_skip_final_llm"] = True
            result["_final_text"] = tool_result["message"]
            messages.append({"role": "assistant", "content": tool_result["message"]})
            return
            messages.append({
                "role": "user",
                "content": "[SYSTEM: Önceki araç başarısız oldu. FARKLI bir araç dene. Örneğin: generate_image ile yeniden üret veya edit_image ile düzenle. HEMEN bir araç çağır!]"
            })
            retry_tool_choice = "required"
            print(f"🔄 RETRY {retry_count+1}/{MAX_RETRIES}: Tool failed, forcing alternative tool")
        elif last_tool_failed and retry_count >= MAX_RETRIES:
            print(f"❌ MAX RETRY ({MAX_RETRIES}) reached, giving up")
        
        # Devam yanıtı kontrol et (nested tool calls)
        continue_response = await self.async_client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=AGENT_TOOLS,
            tool_choice=retry_tool_choice,
            parallel_tool_calls=False
        )
        
        cont_message = continue_response.choices[0].message
        
        # Daha fazla tool call varsa recursive çağır
        if cont_message.tool_calls:
            print(f"🔧 RETRY: AI called {[tc.function.name for tc in cont_message.tool_calls]}")
            await self._process_tool_calls_for_stream(
                cont_message, messages, result, session_id, db, system_prompt, retry_count + 1
            )
        elif cont_message.content:
            # Final text — messages'a ekle böylece stream caller kullanabilir
            final_content = cont_message.content
            # Audio URL enjekte et — AI dahil etmediyse markdown link olarak ekle
            pending_audio = result.get("_pending_audio_url")
            if pending_audio and pending_audio not in final_content:
                final_content += f"\\n\\n[Müziği dinle]({pending_audio})"
                result.pop("_pending_audio_url", None)
            messages.append({"role": "assistant", "content": final_content})
    
    async def _build_entity_context(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        message: str
    ) -> str:
        """Mesajdaki @tag'leri çözümle ve context string oluştur."""
        user_id = await get_user_id_from_session(db, session_id)
        entities = await entity_service.resolve_tags(db, user_id, message)
        
        if not entities:
            return ""
        
        context_parts = []
        for entity in entities:
            ref_image_info = ""
            if entity.reference_image_url:
                ref_image_info = f"\n  ⚠️ REFERANS GÖRSEL VAR: {entity.reference_image_url}"
                print(f"🔍 Entity {entity.tag} referans görsel bulundu: {entity.reference_image_url[:80]}...")
            else:
                print(f"⚠️ Entity {entity.tag} için referans görsel YOK")
                
            context_parts.append(
                f"- {entity.tag}: {entity.name} ({entity.entity_type})\n"
                f"  Açıklama: {entity.description}\n"
                f"  Özellikler: {json.dumps(entity.attributes, ensure_ascii=False)}"
                f"{ref_image_info}"
            )
        
        return "\n".join(context_parts)
    
    async def _build_enriched_context(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        user_message: str,
        suppress_working_memory: bool = False,
        current_reference_video_url: str = None,
    ) -> str:
        """
        Tüm bağlam bileşenlerini tek seferde oluştur.
        Hem process_message hem process_message_stream tarafından çağrılır.
        
        Bileşenler:
        1. Entity @tag çözümleme (mesajdaki @tag'ler)
        2. Proje bağlamı (aktif proje adı, kategori)
        3. Working Memory (son 5 asset)
        4. Kullanıcı tercihleri (aspect ratio, model, stil)
        5. Episodic memory (önemli olaylar)
        6. Core memory (projeler arası hafıza)
        7. Tüm entity listesi (karakter, lokasyon, marka)
        8. Plugin listesi (projede yüklü eklentiler)
        """
        extra_context = ""

        if current_reference_video_url:
            extra_context += (
                "\n\n--- 🎬 AKTİF REFERANS VİDEO ---\n"
                f"Bu mesajda kullanıcı şu videoyu referans verdi: {current_reference_video_url}\n"
                "Bu istekte eski görsel/video asset'lerini varsayılan referans olarak kullanma. "
                "Kullanıcı açıkça önceki bir asset'i istemedikçe aktif referans bu videodur.\n"
            )
        
        # 0. Kullanıcı adı — agent kullanıcıyı ismiyle tanısın
        try:
            from app.models.models import User as UserModel
            user_result = await db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            current_user = user_result.scalar_one_or_none()
            if current_user and current_user.full_name:
                from datetime import datetime
                now = datetime.now()
                extra_context += f"\n\n--- 👤 KULLANICI ---\n"
                extra_context += f"Kullanıcının adı: {current_user.full_name}\n"
                extra_context += f"Email: {current_user.email}\n"
                extra_context += f"📅 Bugünün tarihi: {now.strftime('%d %B %Y, %A')} (saat {now.strftime('%H:%M')})\n"
                extra_context += f"ÖNEMLİ DAVRANIŞ KURALI: Kullanıcıya ismiyle hitap et, samimi ol. "
                extra_context += f"Ama 'seni tanıyor musun' gibi sorularda DÜRÜST ol — "
                extra_context += f"ismini ve hesabını biliyorsun ama kişisel tercihlerini/tarzını ancak birlikte çalıştıkça öğreneceksin. "
                extra_context += f"Eğer aşağıda episodic memory veya user preferences varsa O BİLGİLERİ de kullan — "
                extra_context += f"o zaman gerçekten tanıyorsun demektir."
        except Exception as e:
            print(f"⚠️ Kullanıcı adı hatası: {e}")
        
        # 1. @tag çözümleme (mevcut _build_entity_context)
        entity_context = await self._build_entity_context(db, session_id, user_message)
        if entity_context:
            extra_context += f"\n\n--- Mevcut Entity Bilgileri ---\n{entity_context}"
        
        # 2. Proje bağlamı
        try:
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            active_session = session_result.scalar_one_or_none()
            if active_session:
                project_context = f"\n\n--- 📂 AKTİF PROJE ---\nProje Adı: {active_session.title}"
                if active_session.description:
                    project_context += f"\nAçıklama: {active_session.description}"
                if active_session.category:
                    project_context += f"\nKategori: {active_session.category}"
                if active_session.project_data:
                    project_context += f"\nProje Verileri: {active_session.project_data}"
                extra_context += project_context
        except Exception as e:
            print(f"⚠️ Proje context hatası: {e}")
        
        # 3. Working Memory (son üretilen asset'ler)
        if not suppress_working_memory:
            try:
                recent_assets = await asset_service.get_recent_assets(db, session_id, limit=5)
                if recent_assets:
                    memory_ctx = "\n\n--- 🕒 SON ÜRETİLENLER (Working Memory) ---\n"
                    memory_ctx += "Kullanıcı 'bunu düzenle', 'son görseli değiştir' gibi AÇIKÇA bir asset'e atıf yapıyorsa BURADAKİ URL'leri kullan.\n"
                    memory_ctx += "⚠️ UYARI: 'tekrar dene', 'beğenmedim', 'yeniden yap' gibi mesajlarda bu URL'leri image_url olarak VERME! Bu durumda sıfırdan üret (text-to-image/video).\n"
                    for idx, asset in enumerate(recent_assets, 1):
                        icon = "🎬" if asset.asset_type == "video" else "🖼️"
                        thumb = f" (Thumbnail: {asset.thumbnail_url})" if asset.thumbnail_url else ""
                        prompt_text = f"'{asset.prompt[:50]}...'" if asset.prompt else "'—'"
                        memory_ctx += f"{idx}. [{asset.asset_type.upper()}] {icon} {prompt_text}\n   👉 URL: {asset.url}{thumb}\n"
                    extra_context += memory_ctx
                    print(f"🧠 Working Memory eklendi: {len(recent_assets)} asset")
            except Exception as e:
                print(f"⚠️ Working memory hatası: {e}")
        else:
            print("🧠 Working Memory bu istekte baskı kurmaması için atlandı")
        
        # 4. Kullanıcı tercihleri
        try:
            prefs_prompt = await preferences_service.get_preferences_for_prompt(db, user_id)
            if prefs_prompt:
                extra_context += prefs_prompt
                print(f"📋 Kullanıcı tercihleri eklendi")
        except Exception as e:
            print(f"⚠️ Tercih yükleme hatası: {e}")
        
        # 5. Episodic memory
        try:
            memory_prompt = await episodic_memory.get_context_for_prompt(str(user_id))
            if memory_prompt:
                extra_context += memory_prompt
                print(f"🧠 Episodic memory eklendi")
        except Exception as e:
            print(f"⚠️ Episodic memory hatası: {e}")
        
        # 6. Core memory (projeler arası hafıza)
        try:
            from app.services.conversation_memory_service import conversation_memory
            core_memory = await conversation_memory.build_memory_context(user_id)
            if core_memory:
                extra_context += f"\n\n--- 🧠 KULLANICI HAFIZASI (Projeler Arası) ---\nBu kullanıcıyı tanıyorsun. Geçmiş projelerden bildiklerin:\n{core_memory}"
                print(f"🧠 Cross-project memory eklendi")
        except Exception as e:
            print(f"⚠️ Conversation memory hatası: {e}")
        
        # 7. Tüm entity listesi (projeler arası — kullanıcının tüm entity'leri)
        try:
            all_entities = await entity_service.list_entities(db, user_id)
            if all_entities:
                entity_list_ctx = "\n\n--- 🎭 KULLANICININ ENTITY'LERİ ---\n"
                entity_list_ctx += "Bu kullanıcının kayıtlı karakterleri, lokasyonları ve markaları. @tag kullanmadan da isimle eşleştir:\n"
                for e in all_entities[:15]:  # Max 15 entity
                    ref_info = " 📸" if e.reference_image_url else ""
                    entity_list_ctx += f"- @{e.tag}: {e.name} ({e.entity_type}){ref_info}\n"
                extra_context += entity_list_ctx
                print(f"🎭 Entity context eklendi: {len(all_entities)} entity")
        except Exception as e:
            print(f"⚠️ Entity list hatası: {e}")
        
        # 8. Plugin listesi (aktif projedeki eklentiler)
        try:
            plugin_result = await db.execute(
                select(Preset).where(Preset.session_id == session_id)
            )
            plugins = list(plugin_result.scalars().all())
            if plugins:
                plugin_ctx = "\n\n--- 🔌 PROJEDEKİ PRESET'LER ---\n"
                plugin_ctx += "Bu projede kayıtlı preset'ler. 'Preset: X' mesajı geldiğinde ilgili preset'in TÜM config bilgilerini kullanarak generate_image çağır:\n"
                for p in plugins[:10]:  # Max 10 plugin
                    config = p.config or {}
                    style = config.get("style", "—")
                    time_of_day = config.get("timeOfDay", "")
                    camera_angles = config.get("cameraAngles", [])
                    prompt_template = config.get("promptTemplate", "")
                    char_tag = config.get("character_tag", "")
                    loc_tag = config.get("location_tag", "")
                    
                    plugin_ctx += f"- {p.icon} **{p.name}**: {p.description or '—'}\n"
                    plugin_ctx += f"  Stil: {style}"
                    if time_of_day:
                        plugin_ctx += f" | Zaman: {time_of_day}"
                    if camera_angles:
                        plugin_ctx += f" | Açılar: {', '.join(camera_angles)}"
                    if char_tag:
                        plugin_ctx += f" | Karakter: @{char_tag}"
                    if loc_tag:
                        plugin_ctx += f" | Lokasyon: @{loc_tag}"
                    if prompt_template:
                        plugin_ctx += f"\n  Prompt: {prompt_template}"
                    plugin_ctx += "\n"
                extra_context += plugin_ctx
                print(f"🔌 Plugin context eklendi: {len(plugins)} plugin")
        except Exception as e:
            print(f"⚠️ Plugin context hatası: {e}")
        
        # 9. Prompt öğrenme (geçmiş başarılı prompt'lar)
        try:
            from app.services.conversation_memory_service import conversation_memory
            similar = await conversation_memory.find_similar_prompts(user_id, user_message, limit=3)
            if similar:
                prompt_ctx = "\n\n--- 💡 GEÇMİŞ BAŞARILI PROMPT'LAR ---\n"
                prompt_ctx += "Bu örnekleri sadece stil/ton ilhamı için kullan. Süre, adet, model ve referans seçimlerinde mevcut kullanıcı mesajı her zaman baskındır:\n"
                for idx, p in enumerate(similar, 1):
                    memory_prompt = p.get("memory_prompt") or p.get("prompt", "")
                    prompt_ctx += f"{idx}. \"{memory_prompt[:100]}\" (skor: {p.get('score', '?')}, tip: {p.get('asset_type', '?')})\n"
                extra_context += prompt_ctx
                print(f"💡 Prompt learning eklendi: {len(similar)} referans")
        except Exception as e:
            print(f"⚠️ Prompt learning hatası: {e}")
        
        # 10. Model başarı istatistikleri (hangi model en iyi sonuç veriyor)
        try:
            model_events = await episodic_memory.recall(str(user_id), event_type="model_success", limit=50)
            if model_events:
                # Model başarı sayılarını hesapla
                model_counts = {}
                for event in model_events:
                    meta = event.metadata or {}
                    model = meta.get("model", "unknown")
                    if model != "unknown":
                        model_counts[model] = model_counts.get(model, 0) + 1
                
                if model_counts:
                    # En başarılı 5 model
                    top_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    model_ctx = "\n\n--- 🏆 MODEL BAŞARI GEÇMİŞİ ---\n"
                    model_ctx += "Bu kullanıcı bu modellerle en iyi sonuçları aldı (👍 sayısına göre):\n"
                    for model, count in top_models:
                        model_ctx += f"- {model}: {count} başarılı üretim\n"
                    extra_context += model_ctx
                    print(f"🏆 Model başarı istatistikleri eklendi: {len(top_models)} model")
        except Exception as e:
            print(f"⚠️ Model stats hatası: {e}")
        
        return extra_context
    
    async def _process_response(
        self, 
        response, 
        messages: list, 
        result: dict,
        session_id: uuid.UUID,
        db: AsyncSession,
        retry_count: int = 0
    ):
        """OpenAI GPT-4o response'unu işle, tool call varsa yürüt."""
        MAX_RETRIES = 2
        
        message = response.choices[0].message
        
        # 🔍 DEBUG: Agent ne döndü?
        print(f"🤖 AGENT RESPONSE:")
        print(f"   - Content: {message.content[:200] if message.content else 'None'}...")
        print(f"   - Tool calls: {len(message.tool_calls) if message.tool_calls else 0}")
        if message.tool_calls:
            for tc in message.tool_calls:
                print(f"   - Tool: {tc.function.name}")
        
        # Tool call varsa initial planning text'i doğrudan kullanıcıya göstermeyiz.
        if message.content and not message.tool_calls:
            result["response"] += message.content
        
        # Tool calls varsa işle
        if message.tool_calls:
            # ── Duplicate video guard ──
            VIDEO_TOOLS = {"generate_video", "generate_long_video"}
            video_already_called = False
            deterministic_media_message = None
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # ── GUARD: GPT-4o bazen aynı istek için 2x video çağrısı gönderir ──
                if tool_name in VIDEO_TOOLS:
                    if video_already_called:
                        print(f"⚠️ DUPLICATE VIDEO GUARD: {tool_name} skip edildi (non-stream)")
                        messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": tool_call.id, "type": "function", "function": {"name": tool_name, "arguments": tool_call.function.arguments}}]})
                        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"success": True, "message": "Bu istek için zaten bir video üretimi başlatıldı."})})
                        continue
                    video_already_called = True
                
                # 🔍 DEBUG: Tool çağrısı başlıyor
                print(f"🔧 TOOL EXECUTION START: {tool_name}")
                print(f"   Args: {json.dumps(tool_args, ensure_ascii=False)[:200]}...")
                
                # Araç çağrısını yürüt
                tool_result = await self._handle_tool_call(
                    tool_name, 
                    tool_args, 
                    session_id, 
                    db,
                    resolved_entities=result.get("_resolved_entities", []),
                    current_reference_image=result.get("_current_reference_image"),
                    uploaded_reference_url=result.get("_uploaded_image_url"),
                    uploaded_reference_urls=result.get("_uploaded_image_urls"),
                    uploaded_reference_video_url=result.get("_uploaded_video_url"),
                    user_message=result.get("_user_message", ""),
                )
                
                # 🔍 DEBUG: Tool çağrısı bitti
                print(f"🔧 TOOL EXECUTION END: {tool_name}")
                print(f"   Result: success={tool_result.get('success')}, error={tool_result.get('error', 'None')}")
                
                # Görsel üretildiyse ekle + otomatik kalite kontrolü
                if tool_result.get("success") and tool_result.get("image_url"):
                    image_url = tool_result["image_url"]
                    original_prompt = tool_args.get("prompt", "")
                    result["images"].append({
                        "url": image_url,
                        "prompt": original_prompt
                    })
                    
                    # 🔍 OTOMATİK KALİTE KONTROLÜ
                    try:
                        qc = await self._auto_quality_check(image_url, original_prompt, "image")
                        if qc:
                            tool_result["_quality_check"] = qc
                            print(f"   🔍 Kalite kontrolü: {qc[:80]}...")
                    except Exception as qc_err:
                        print(f"   ⚠️ Kalite kontrolü atlandı: {qc_err}")
                
                # Video üretildiyse ekle
                if tool_result.get("success") and tool_result.get("video_url"):
                    result["videos"].append({
                        "url": tool_result["video_url"],
                        "prompt": tool_args.get("prompt", ""),
                        "thumbnail_url": tool_result.get("thumbnail_url")
                    })
                
                # Audio üretildiyse kaydet
                if tool_result.get("success") and tool_result.get("audio_url"):
                    result["_pending_audio_url"] = tool_result["audio_url"]
                
                # Entity oluşturulduysa ekle
                if tool_result.get("success") and tool_result.get("entity"):
                    result["entities_created"].append(tool_result["entity"])
                
                # Preset oluşturulduğunda sidebar refresh tetikle
                if tool_result.get("success") and tool_name == "manage_plugin" and tool_args.get("action") == "create":
                    result["entities_created"].append({"type": "preset", "name": tool_result.get("name", "Preset")})

                media_message = self._get_deterministic_media_message(tool_result)
                if media_message:
                    deterministic_media_message = media_message
                
                # Tool sonucunu GPT-4o'ya gönder
                # SimpleNamespace veya Pydantic olabilir, her ikisi için de çalışır
                tool_call_dict = {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call_dict]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str)
                })
            
            last_tool_failed = not tool_result.get("success", True)
            has_any_success = bool(result["images"] or result["videos"] or result.get("_pending_audio_url"))

            # Arka plan işlerinde LLM'e tekrar söz verildiğinde saçma/hallucinated kapanışlar üretebiliyor.
            # Bu akışta deterministik tool mesajını doğrudan nihai cevap yap.
            if tool_result.get("is_background_task"):
                print("🔄 BACKGROUND TASK DETECTED (non-stream): Skipping final LLM completion call.")
                result["response"] += tool_result.get("message", "İşlem arka planda başlatıldı.")
                result["is_background_task"] = True
                return

            if deterministic_media_message and has_any_success:
                print("🧱 DETERMINISTIC MEDIA RESULT (non-stream): Skipping final LLM completion call.")
                result["response"] += deterministic_media_message
                return

            if last_tool_failed and tool_name in {"edit_video", "advanced_edit_video"}:
                print("🛑 EDIT VIDEO FAILURE (non-stream): Alternative tool retry disabled.")
                result["response"] += f"Hata: {tool_result.get('error', 'Video düzenleme başarısız oldu.')}"
                return
            
            retry_tool_choice = "auto"
            if last_tool_failed and not has_any_success and retry_count < MAX_RETRIES:
                # manage_plugin başarısız olursa farklı tool deneme — hata mesajını göster
                if tool_name == "manage_plugin":
                    print("🛑 MANAGE_PLUGIN FAILURE (non-stream): Retry disabled, showing error directly.")
                    error_msg = tool_result.get('message') or tool_result.get('error', 'Preset oluşturma başarısız oldu.')
                    result["response"] += f"❌ {error_msg}"
                    return
            
            # manage_plugin başarılı + deterministik mesaj varsa, LLM'yi atla
            if tool_name == "manage_plugin" and tool_result.get("_deterministic") and tool_result.get("success"):
                print("✅ MANAGE_PLUGIN SUCCESS (non-stream): Deterministic response, skipping final LLM.")
                result["response"] += tool_result["message"]
                return
                messages.append({
                    "role": "user",
                    "content": "[SYSTEM: Önceki araç başarısız oldu. FARKLI bir araç dene. HEMEN bir araç çağır!]"
                })
                retry_tool_choice = "required"
                print(f"🔄 RETRY {retry_count+1}/{MAX_RETRIES} (non-stream): forcing alternative tool")
            elif last_tool_failed and retry_count >= MAX_RETRIES:
                print(f"❌ MAX RETRY ({MAX_RETRIES}) reached (non-stream), giving up")
            
            # Devam yanıtı al
            continue_response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "system", "content": self.system_prompt}] + messages,
                tools=AGENT_TOOLS,
                tool_choice=retry_tool_choice
            )
            
            # Recursive olarak devam et (nested tool calls için)
            await self._process_response(
                continue_response, 
                messages, 
                result, 
                session_id, 
                db,
                retry_count + 1
            )
    
    async def _handle_tool_call(
        self, 
        tool_name: str, 
        tool_input: dict,
        session_id: uuid.UUID,
        db: AsyncSession,
        resolved_entities: list = None,
        current_reference_image: str = None,
        uploaded_reference_url: str = None,
        uploaded_reference_urls: list = None,
        uploaded_reference_video_url: str = None,
        user_message: str = "",
    ) -> dict:
        """Araç çağrısını işle."""
        
        # === DIAGNOSTIC LOGGING ===
        print(f"\n{'='*50}")
        print(f"🔧 _handle_tool_call: {tool_name}")
        print(f"   uploaded_reference_url: {uploaded_reference_url[:80] if uploaded_reference_url else 'None'}")
        print(f"   uploaded_reference_video_url: {uploaded_reference_video_url[:80] if uploaded_reference_video_url else 'None'}")
        print(f"   tool_input keys: {list(tool_input.keys())}")
        print(f"   tool_input.image_url: {tool_input.get('image_url', 'NOT SET')}")
        print(f"{'='*50}")
        
        # Kullanıcı fotoğraf yüklediyse ve tool args'da image_url yoksa, otomatik ekle
        IMAGE_TOOLS = {"edit_image", "remove_background", "outpaint_image", "upscale_image", "analyze_image", "generate_video", "generate_long_video"}
        if uploaded_reference_url and tool_name in IMAGE_TOOLS:
            if not tool_input.get("image_url"):
                tool_input["image_url"] = uploaded_reference_url
                print(f"   📎 AUTO-INJECTED uploaded image URL into {tool_name}")
            else:
                print(f"   ✅ image_url already set by GPT-4o: {tool_input['image_url'][:80]}")
        elif not uploaded_reference_url and tool_name in IMAGE_TOOLS:
            print(f"   ⚠️ NO uploaded_reference_url available for {tool_name}!")

        VIDEO_TOOLS = {"edit_video", "advanced_edit_video"}
        if uploaded_reference_video_url and tool_name in VIDEO_TOOLS:
            if not tool_input.get("video_url"):
                tool_input["video_url"] = uploaded_reference_video_url
                print(f"   📎 AUTO-INJECTED uploaded video URL into {tool_name}")
        elif tool_name in VIDEO_TOOLS and tool_input.get("video_url") and not tool_input.get("image_url"):
            matched_video_asset = await self._get_session_video_asset_by_url(
                db=db,
                session_id=session_id,
                video_url=tool_input.get("video_url"),
            )
            reference_image_url = self._get_video_asset_reference_image(matched_video_asset)
            if reference_image_url:
                tool_input["image_url"] = reference_image_url
                print(f"   🖼️ REUSED matched asset reference image into {tool_name}")
        elif tool_name in VIDEO_TOOLS and not tool_input.get("video_url"):
            resolved_video_asset = await self._resolve_session_video_asset(
                db=db,
                session_id=session_id,
                user_message=user_message or tool_input.get("prompt", ""),
            )
            if resolved_video_asset:
                tool_input["video_url"] = resolved_video_asset.url
                if not tool_input.get("image_url"):
                    reference_image_url = self._get_video_asset_reference_image(resolved_video_asset)
                    if reference_image_url:
                        tool_input["image_url"] = reference_image_url
                        print(f"   🖼️ REUSED stored video reference image into {tool_name}")
                print(f"   📎 AUTO-RESOLVED session video reference into {tool_name}")
        
        if tool_name == "generate_image":
            return await self._generate_image(
                db, session_id, tool_input, resolved_entities or [],
                uploaded_reference_url=uploaded_reference_url
            )
        
        elif tool_name == "create_character":
            return await self._create_entity(
                db, session_id, "character", tool_input,
                current_reference_image=current_reference_image
            )
        
        elif tool_name == "create_location":
            return await self._create_entity(
                db, session_id, "location", tool_input
            )
        
        elif tool_name == "get_entity":
            return await self._get_entity(db, session_id, tool_input)
        
        elif tool_name == "list_entities":
            return await self._list_entities(db, session_id, tool_input)
            
        elif tool_name == "manage_core_memory":
            try:
                from app.services.preferences_service import preferences_service
                
                user_id = await get_user_id_from_session(db, session_id)
                if not user_id:
                    return {"status": "error", "message": "Kullanıcı bulunamadı, hafıza kaydedilemedi."}
                
                action = tool_input.get("action", "add")
                category = tool_input.get("fact_category", "general")
                fact = tool_input.get("fact_description", "")

                if action == "add" and not is_stable_memory_fact(category, fact):
                    return {
                        "status": "success",
                        "message": "Bu bilgi tek seferlik veya gorev-ozel gorundugu icin kalici hafizaya yazilmadi.",
                        "action_executed": "skipped",
                    }
                
                # Yeni JSONB persistence katmanını kullan
                await preferences_service.learn_preference(
                    db=db,
                    user_id=user_id,
                    action=action,
                    category=category,
                    fact=fact
                )
                
                if action == "add":
                    msg = f"Kullanıcı tercihi hafızaya eklendi: {fact}"
                elif action == "delete":
                    msg = f"Kayıt başarıyla hafızadan silindi veya silinme denendi: {fact}"
                elif action == "clear":
                    msg = "Tüm 'Core Memory' (Kişisel Bilgiler) sıfırlandı."
                else:
                    msg = f"Bilinmeyen işlem türü (action): {action}"
                    
                return {
                    "status": "success", 
                    "message": msg,
                    "action_executed": action
                }
            except Exception as e:
                print(f"Hafıza yönetimi hatası: {e}")
                return {"status": "error", "message": f"Hafıza aracında hata oluştu: {str(e)}"}
        
        # YENİ ARAÇLAR
        elif tool_name == "generate_video":
            if uploaded_reference_video_url and self._is_direct_video_edit_request(user_message or tool_input.get("prompt", "")):
                print("   🔀 REROUTE: Attached reference video detected, generate_video -> edit_video")
                edit_tool_input = {
                    "video_url": uploaded_reference_video_url,
                    "prompt": tool_input.get("prompt") or user_message,
                    "image_url": tool_input.get("image_url"),
                }
                preflight = await self._ensure_video_edit_reference_image(edit_tool_input)
                if not preflight.get("success"):
                    return {"success": False, "error": preflight.get("error")}
                return await self._queue_video_edit(
                    db=db,
                    session_id=session_id,
                    params=preflight["tool_input"],
                    message="🎬 Referans video düzenlemesi arka planda başladı! Hazır olduğunda otomatik bildirim gelecek.",
                )

            if not tool_input.get("image_url"):
                resolved_reference_url = await self._resolve_session_image_reference(
                    db=db,
                    session_id=session_id,
                    user_message=user_message or tool_input.get("prompt", ""),
                )
                if resolved_reference_url:
                    tool_input["image_url"] = resolved_reference_url
                    print(f"   📎 AUTO-RESOLVED session image reference into generate_video")
            
            result = await self._generate_video(db, session_id, tool_input, resolved_entities or [])
            return result
        
        elif tool_name == "edit_video":
            preflight = await self._ensure_video_edit_reference_image(tool_input)
            if not preflight.get("success"):
                return {"success": False, "error": preflight.get("error")}
            return await self._queue_video_edit(
                db=db,
                session_id=session_id,
                params=preflight["tool_input"],
                message="🎬 Video düzenleme arka planda başladı! Hazır olduğunda otomatik bildirim gelecek.",
            )
        
        elif tool_name == "generate_long_video":
            if not tool_input.get("image_url"):
                resolved_reference_url = await self._resolve_session_image_reference(
                    db=db,
                    session_id=session_id,
                    user_message=user_message or tool_input.get("prompt", ""),
                )
                if resolved_reference_url:
                    tool_input["image_url"] = resolved_reference_url
                    print(f"   📎 AUTO-RESOLVED session image reference into generate_long_video")
            return await self._generate_long_video(db, session_id, tool_input, resolved_entities or [])
        
        elif tool_name == "edit_image":
            # Orijinal yüz referansını ekle (face swap için)
            if uploaded_reference_url:
                tool_input["face_reference_url"] = uploaded_reference_url
            elif current_reference_image:
                # Session'daki referans görseli URL olarak al
                cached = self._session_reference_images.get(str(session_id)) if hasattr(self, '_session_reference_images') else None
                if cached and cached.get("url"):
                    tool_input["face_reference_url"] = cached["url"]
            
            # Tüm referans URL'lerini topla (identity preservation için)
            tool_input["all_reference_urls"] = uploaded_reference_urls or ([uploaded_reference_url] if uploaded_reference_url else [])
            
            result = await self._edit_image(tool_input)
            if result.get("success") and result.get("image_url"):
                try:
                    await asset_service.save_asset(
                        db=db, session_id=session_id,
                        url=result["image_url"], asset_type="image",
                        prompt=tool_input.get("prompt", "Image edit"),
                        model_name=result.get("model", "edit"),
                    )
                except Exception as e:
                    print(f"⚠️ Edit image asset kaydetme hatası: {e}")
            return result
        
        elif tool_name == "outpaint_image":
            result = await self._outpaint_image(tool_input)
            if result.get("success") and result.get("image_url"):
                try:
                    await asset_service.save_asset(
                        db=db, session_id=session_id,
                        url=result["image_url"], asset_type="image",
                        prompt=tool_input.get("prompt", "Outpaint"),
                        model_name=result.get("model", "outpaint"),
                    )
                except Exception as e:
                    print(f"⚠️ Outpaint asset kaydetme hatası: {e}")
            return result
        
        elif tool_name == "apply_style":
            result = await self._apply_style(tool_input)
            if result.get("success") and result.get("image_url"):
                try:
                    await asset_service.save_asset(
                        db=db, session_id=session_id,
                        url=result["image_url"], asset_type="image",
                        prompt=tool_input.get("style", "Style transfer"),
                        model_name=result.get("model", "style"),
                    )
                except Exception as e:
                    print(f"⚠️ Style asset kaydetme hatası: {e}")
            return result
        
        elif tool_name == "upscale_image":
            result = await self._upscale_image(tool_input)
            if result.get("success") and result.get("image_url"):
                try:
                    await asset_service.save_asset(
                        db=db, session_id=session_id,
                        url=result["image_url"], asset_type="image",
                        prompt="Upscale",
                        model_name=result.get("model", "upscale"),
                    )
                except Exception as e:
                    print(f"⚠️ Upscale asset kaydetme hatası: {e}")
            return result
        
        elif tool_name == "remove_background":
            result = await self._remove_background(tool_input)
            if result.get("success") and result.get("image_url"):
                try:
                    await asset_service.save_asset(
                        db=db, session_id=session_id,
                        url=result["image_url"], asset_type="image",
                        prompt="Background removed",
                        model_name=result.get("model", "birefnet-v2"),
                    )
                except Exception as e:
                    print(f"⚠️ Remove BG asset kaydetme hatası: {e}")
            return result
        
        elif tool_name == "generate_grid":
            return await self._generate_grid(db, session_id, tool_input, resolved_entities or [])
        
        elif tool_name == "use_grid_panel":
            return await self._use_grid_panel(db, session_id, tool_input)
        
        # WEB ARAMA ARAÇLARI
        elif tool_name == "search_images":
            return await self._search_images(tool_input)
        
        elif tool_name == "search_web":
            return await self._search_web(tool_input)
        
        elif tool_name == "search_videos":
            return await self._search_videos(tool_input)
        
        elif tool_name == "browse_url":
            return await self._browse_url(tool_input)
        
        elif tool_name == "fetch_web_image":
            return await self._fetch_web_image(db, session_id, tool_input)
            
        elif tool_name == "save_web_asset":
            return await self._save_web_asset(db, session_id, tool_input)
        
        # AKILLI AGENT ARAÇLARI
        elif tool_name == "get_past_assets":
            return await self._get_past_assets(db, session_id, tool_input)
        
        elif tool_name == "mark_favorite":
            return await self._mark_favorite(db, session_id, tool_input)
        
        elif tool_name == "undo_last":
            return await self._undo_last(db, session_id)
        
        # GÖRSEL & VİDEO MUHAKEME ARAÇLARI
        elif tool_name == "analyze_image":
            return await self._analyze_image(tool_input)
        
        elif tool_name == "analyze_video":
            return await self._analyze_video(tool_input)
        
        elif tool_name == "compare_images":
            return await self._compare_images(tool_input)
        
        # MÜZİK / SES ARAÇLARI
        elif tool_name == "generate_music":
            return await self._generate_music(db, session_id, tool_input)
        
        elif tool_name == "add_audio_to_video":
            return await self._add_audio_to_video(db, session_id, tool_input)
        
        # ROADMAP / GÖREV PLANLAMA
        elif tool_name == "create_roadmap":
            return await self._create_roadmap(db, session_id, tool_input)
        
        elif tool_name == "get_roadmap_progress":
            return await self._get_roadmap_progress(db, session_id, tool_input)
        
        # SİSTEM YÖNETİM ARAÇLARI
        elif tool_name == "manage_project":
            return await self._manage_project(db, session_id, tool_input)
        
        elif tool_name == "delete_entity":
            return await self._delete_entity(db, session_id, tool_input)
        
        elif tool_name == "manage_trash":
            return await self._manage_trash(db, session_id, tool_input)
        
        elif tool_name == "manage_plugin":
            return await self._manage_plugin(db, session_id, tool_input)
        
        elif tool_name == "get_system_state":
            return await self._get_system_state(db, session_id, tool_input)
        
        elif tool_name == "manage_wardrobe":
            return await self._manage_wardrobe(db, session_id, tool_input)
        
        elif tool_name == "create_brand":
            return await self._create_brand(db, session_id, tool_input)
        
        elif tool_name == "research_brand":
            return await self._research_brand(db, session_id, tool_input)
        
        elif tool_name == "semantic_search":
            return await self._semantic_search(db, session_id, tool_input)
        
        elif tool_name == "get_library_docs":
            return await self._get_library_docs(tool_input)
        
        elif tool_name == "save_style":
            return await self._save_style(db, session_id, tool_input)
        
        elif tool_name == "generate_campaign":
            return await self._generate_campaign(db, session_id, tool_input)
        
        elif tool_name == "transcribe_voice":
            return await self._transcribe_voice(tool_input)
        
        elif tool_name == "plan_and_execute":
            return await self._plan_and_execute(db, session_id, tool_input, resolved_entities or [])
        
        elif tool_name == "advanced_edit_video":
            return await self._advanced_edit_video(db, session_id, tool_input)
        
        elif tool_name == "audio_visual_sync":
            return await self._audio_visual_sync(db, session_id, tool_input)
        
        elif tool_name == "resize_image":
            return await self._resize_image(db, session_id, tool_input)
        
        # (add_audio_to_video zaten yukarıda handle ediliyor)
        
        return {"success": False, "error": f"Bilinmeyen araç: {tool_name}"}
    
    async def _summarize_conversation(self, messages: list, max_messages: int = 15) -> list:
        """
        Uzun konuşmaları özetleyerek context window tasarrufu sağlar.
        Zehirli mesajları filtreler, kullanıcı parametrelerini korur.
        """
        if len(messages) <= max_messages:
            return messages
        
        try:
            # Son 5 mesajı koru (en güncel context)
            recent_messages = messages[-5:]
            old_messages = messages[:-5]
            
            # 🛡️ Zehirli/gürültülü mesajları filtrele (özete dahil etme)
            NOISE_PATTERNS = [
                "Video üretimine başladım",
                "Videonuz hazır",
                "Video üretimi başarısız",
                "Beklenmeyen Sistem Hatası",
                "hata oluştu",
                "tekrar deneyelim",
            ]
            
            filtered_old = []
            for msg in old_messages:
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
                
                # Gürültülü mesajları atla
                if any(noise in content for noise in NOISE_PATTERNS):
                    continue
                filtered_old.append(msg)
            
            # Eski mesajları özetle
            summary_prompt = """Aşağıdaki konuşmayı kısa ve öz özetle.

ÖNEMLİ KURALLAR:
- Kullanıcının belirttiği PARAMETRELERİ (süre, boyut, model, stil) AYNEN koru
- Oluşturulan entity'leri (@karakterler, @mekanlar) listele
- Başarılı üretim sonuçlarını (URL'ler) koru
- Başarısız denemeleri ve hata mesajlarını ATLAMA — bunları özetleme
- Kullanıcının tercihlerini ve tekrar eden isteklerini belirt

Konuşma:
"""
            for msg in filtered_old:
                role = "Kullanıcı" if msg.get("role") == "user" else "Asistan"
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
                summary_prompt += f"\n{role}: {content[:500]}..."
            
            # GPT-4o-mini ile özetle
            summary_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=600,
                messages=[
                    {"role": "system", "content": "Sen bir konuşma özetleyicisisin. Kullanıcının verdiği parametreleri (süre, boyut, model) AYNEN koru. Hata mesajlarını ve başarısız denemeleri özetleme — sadece başarılı sonuçları ve kullanıcı tercihlerini yaz."},
                    {"role": "user", "content": summary_prompt}
                ]
            )
            
            summary_text = summary_response.choices[0].message.content
            
            summary_message = {
                "role": "system",
                "content": f"📝 ÖNCEKİ KONUŞMA ÖZETİ:\n{summary_text}\n\n⚠️ DİKKAT: Bu özetteki parametreler geçmişe aittir. Yeni isteklerde SADECE kullanıcının SON mesajındaki parametreleri kullan.\n\n(Son {len(recent_messages)} mesaj aşağıda)"
            }
            
            print(f"🧠 Konuşma özetlendi: {len(old_messages)} mesaj → {len(filtered_old)} filtrelendi → 1 özet + {len(recent_messages)} güncel")
            
            return [summary_message] + recent_messages
            
        except Exception as e:
            print(f"⚠️ Özetleme hatası: {e}")
            return messages[-10:]

    
    async def _generate_image(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict, 
        resolved_entities: list = None,
        uploaded_reference_url: str = None
    ) -> dict:
        """
        Akıllı görsel üretim sistemi.
        
        İş Akışı:
        1. Entity'de referans görsel var mı kontrol et
        2. VARSA → Akıllı sistem: Nano Banana + Face Swap fallback
        3. YOKSA → Sadece Nano Banana Pro
        4. Her üretimde asset'i veritabanına kaydet
        
        Agent kendi başına karar verir ve en iyi sonucu sunar.
        """
        try:
            original_prompt = params.get("prompt", "")
            aspect_ratio = params.get("aspect_ratio", "1:1")
            resolution = params.get("resolution", "1K")
            
            # 🔄 PROMPTU İNGİLİZCE'YE ÇEVİR (Hangi dilde olursa olsun - daha iyi görsel sonuçları için)
            prompt, was_translated = await translate_to_english(original_prompt)
            if was_translated:
                print(f"📝 Prompt çevrildi: '{original_prompt[:50]}...' → '{prompt[:50]}...'")
            
            # 🎬 PROMPT ZENGİNLEŞTİRME — kısa/belirsiz promptları sinematik detaylı hale getir
            prompt = await self._enrich_prompt(prompt, "image")            
            # Referans görseli olan karakter var mı kontrol et
            face_reference_url = None
            entity_description = ""
            physical_attributes = {}
            
            # Debug: resolved_entities kontrolü
            print(f"🔍 _generate_image: resolved_entities = {len(resolved_entities) if resolved_entities else 0} adet")
            
            if resolved_entities:
                for entity in resolved_entities:
                    print(f"   → Entity: {getattr(entity, 'tag', 'unknown')}, type: {type(entity)}")
                    
                    # Referans görsel kontrolü
                    if hasattr(entity, 'reference_image_url') and entity.reference_image_url:
                        face_reference_url = entity.reference_image_url
                        print(f"   ✅ Referans görsel BULUNDU: {face_reference_url[:80]}...")
                    else:
                        print(f"   ⚠️ Referans görsel YOK - hasattr: {hasattr(entity, 'reference_image_url')}, value: {getattr(entity, 'reference_image_url', 'N/A')}")
                    
                    # Entity açıklamasını topla
                    if hasattr(entity, 'description') and entity.description:
                        entity_description += f"{entity.description}. "
                    # Fiziksel özellikleri topla (attributes içinden)
                    if hasattr(entity, 'attributes') and entity.attributes:
                        attrs = entity.attributes
                        for key in ['eye_color', 'hair_color', 'skin_tone', 'eyebrow_color', 
                                   'eyebrow_shape', 'hair_style', 'facial_features']:
                            if attrs.get(key):
                                physical_attributes[key] = attrs[key]
            
            # Entity açıklamasını ve fiziksel özellikleri prompt'a ekle
            brand_guidelines = ""
            if resolved_entities:
                for entity in resolved_entities:
                    if hasattr(entity, 'attributes') and entity.attributes:
                        banned = entity.attributes.get("banned_words", [])
                        aesthetic = entity.attributes.get("mandatory_aesthetic", "")
                        if banned:
                            brand_guidelines += f" ABSOLUTELY DO NOT INCLUDE: {', '.join(banned)}."
                        if aesthetic:
                            brand_guidelines += f" MANDATORY AESTHETIC RULES: {aesthetic}."

            if entity_description or physical_attributes:
                prompt = await enhance_character_prompt(
                    base_prompt=f"{entity_description} {prompt}",
                    physical_attributes=physical_attributes
                )
                print(f"🎨 Karakter prompt zenginleştirildi: '{prompt[:80]}...'")
            else:
                # Entity yoksa bile prompt'u sinematik kaliteye taşı
                from app.services.prompt_translator import enrich_prompt
                prompt = await enrich_prompt(prompt)
                print(f"✨ Prompt zenginleştirildi (genel): '{prompt[:80]}...'")
            
            # Brand Book kurallarını en sona güçlü bir şekilde ekle
            if brand_guidelines:
                prompt = f"{prompt} | BRAND BOOK STRICT GUIDELINES: {brand_guidelines}"
                print(f"📖 Brand Book Kuralları Uygulandı: {brand_guidelines}")
            
            # Kullanıcı direkt referans fotoğraf yüklediyse ve entity'den referans gelmemişse
            if not face_reference_url and uploaded_reference_url:
                face_reference_url = uploaded_reference_url
                print(f"   ✅ Yüklenen referans görsel kullanılacak: {face_reference_url[:80]}...")
            
            additional_ref_urls = params.get("additional_reference_urls", [])
            
            # AKILLI SİSTEM: Referans görsel VEYA ekstra webt'den bulunmuş görsel varsa
            print(f"🎯 Referans görsel durumu: Face={face_reference_url is not None}, Web={len(additional_ref_urls)} adet")
            if face_reference_url or additional_ref_urls:
                # === HİBRİT PIPELINE: Gemini FIRST → fal.ai FALLBACK ===
                print(f"🤖 Hibrit pipeline: Gemini ile denenecek, başarısızsa fal.ai fallback")
                
                # Çoklu referans URL'leri topla (multi-image upload)
                all_ref_urls = []
                if hasattr(self, '_current_uploaded_urls') and self._current_uploaded_urls:
                    all_ref_urls = self._current_uploaded_urls[:]
                elif face_reference_url:
                    all_ref_urls = [face_reference_url]
                    
                # Web'den gelen ekstra resimleri listeye ekle
                if additional_ref_urls:
                    all_ref_urls.extend(additional_ref_urls)
                    print(f"🌐 İnternetten {len(additional_ref_urls)} adet ekstra multi-referans (örn: dövme/vücut vb.) eklendi!")
                
                primary_ref = face_reference_url if face_reference_url else (all_ref_urls[0] if all_ref_urls else None)

                # Adım 1: Gemini ile dene
                gemini_result = None
                try:
                    from app.services.gemini_image_service import gemini_image_service
                    gemini_result = await gemini_image_service.generate_with_reference(
                        prompt=prompt,
                        reference_image_url=primary_ref,
                        reference_images_urls=all_ref_urls if len(all_ref_urls) > 1 else None,
                        aspect_ratio=aspect_ratio
                    )
                except Exception as gemini_err:
                    print(f"⚠️ Gemini import/çağrı hatası: {gemini_err}")
                    gemini_result = {"success": False, "error": str(gemini_err)}
                
                if gemini_result and gemini_result.get("success"):
                    result = gemini_result
                    print(f"✅ Gemini başarılı! URL: {result.get('image_url', '')[:60]}...")
                else:
                    # Adım 2: Gemini başarısız → fal.ai fallback
                    gemini_error = gemini_result.get("error", "bilinmiyor") if gemini_result else "import hatası"
                    print(f"⚠️ Gemini başarısız ({gemini_error}), fal.ai fallback deniyor...")
                    
                    result = await self.fal_plugin._smart_generate_with_face({
                        "prompt": prompt,
                        "face_image_url": face_reference_url,
                        "aspect_ratio": aspect_ratio,
                        "resolution": resolution
                    })
                
                if result.get("success"):
                    method = result.get("method_used", "unknown")
                    quality_notes = result.get("quality_notes", "")
                    model_display = result.get("model_display_name", method)
                    image_url = result.get("image_url")
                    # ==========================================
                    # 🔍 2. SELF-REFLECTION (AUTO-CORRECTION) BAŞLANGICI
                    # Eğer kullanıcı prompt içinde spesifik "yazı/text" istemişse,
                    # görseli hemen dönmeden önce arka planda analiz et. 
                    # Hata varsa 1 kez tekrar üret.
                    # ==========================================
                    prompt_lower = prompt.lower()
                    needs_text = any(kw in prompt_lower for kw in ["yaz", "text", "saying", "written", "letters", "kelime", "harf"])
                    
                    if needs_text and result.get("attempts", []) == []:
                        print("🤖 🔍 SELF-REFLECTION TETIKLENDI: Görselde yazı istendi, kalite kontrol yapılıyor...")
                        try:
                            # analyze_image arcını gizlice çağır
                            analysis_result = await self._analyze_image({
                                "image_url": image_url,
                                "question": "Bu görseldeki yazıları BİREBİR OKU. Eğer prompttaki istenen yazıyla eşleşmiyorsa, harf hatası (typo) varsa veya anlamsız bozuk şekiller varsa SADECE 'HATA: [hatanın detayı]' yaz. Her şey kusursuzsa SADECE 'KUSURSUZ' yaz."
                            })
                            
                            analysis_text = analysis_result.get("analysis", "")
                            print(f"   📊 Analiz Sonucu: {analysis_text}")
                            
                            if analysis_result.get("success") and "HATA" in analysis_text.upper() and "KUSURSUZ" not in analysis_text.upper():
                                print("   ❌ Kalite kontrol başarısız! Otonom düzeltme (Retry 1) başlatılıyor...")
                                # Otonom Retry - Hata bilgisini prompta ekleyerek DÜZELT
                                correction_prompt = f"{prompt}. CRITICAL FIX: The previous generation failed because: {analysis_text}. You MUST render the text flawlessly this time. Use high contrast, clear typography, and double check spelling."
                                
                                retry_result = await self.fal_plugin.execute("generate_image", {
                                    "prompt": correction_prompt,
                                    "aspect_ratio": aspect_ratio,
                                    "resolution": resolution
                                })
                                
                                if retry_result.success and retry_result.data.get("image_url"):
                                    print("   ✅ Otonom düzeltme başarılı! Yeni görsel kullanılıyor.")
                                    # Eski (hatalı) görsel URL'sini ez
                                    image_url = retry_result.data.get("image_url")
                                    method = "nano-banana-pro (Auto-Corrected)"
                                    model_display = "Nano Banana Pro (Auto-Corrected)"
                                    quality_notes += " | 🤖 Otonom Self-Reflection çalıştı ve tespit edilen yazım hatası düzeltildi."
                        except Exception as ref_err:
                            print(f"⚠️ Self-Reflection hatası (Gözardı ediliyor): {ref_err}")
                    # ==========================================
                    # 🔍 SELF-REFLECTION BİTİŞİ
                    # ==========================================
                    
                    # 📦 Asset'i veritabanına kaydet
                    entity_ids = [str(getattr(e, 'id', None)) for e in resolved_entities if getattr(e, 'id', None)] if resolved_entities else None
                    await asset_service.save_asset(
                        db=db,
                        session_id=session_id,
                        url=image_url,
                        asset_type="image",
                        prompt=prompt,
                        model_name=method,
                        model_params={
                            "aspect_ratio": aspect_ratio,
                            "resolution": resolution,
                            "face_reference_used": True,
                            "pipeline": "gemini-hybrid",
                            "attempts": result.get("attempts", [])
                        },
                        entity_ids=entity_ids
                    )
                    
                    # 📊 İstatistik kaydet
                    user_id = await get_user_id_from_session(db, session_id)
                    await StatsService.track_image_generation(db, user_id, method)
                    
                    return {
                        "success": True,
                        "image_url": image_url,
                        "base_image_url": result.get("base_image_url"),
                        "model": method,
                        "model_display_name": model_display,
                        "quality_notes": quality_notes,
                        "attempts": result.get("attempts", []),
                        "message": f"Görsel üretildi. Yöntem: {model_display}. {quality_notes}",
                        "agent_decision": f"Referans görsel algılandı. Kullanılan yöntem: {model_display}"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Görsel üretilemedi")
                    }
            
            else:
                # Referans yok - sadece generate_image (Smart Router)
                plugin_result = await self.fal_plugin.execute("generate_image", {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution
                })
                result = plugin_result.data if plugin_result.success else {"success": False, "error": plugin_result.error or "Görsel üretilemedi"}
                
                if result.get("success"):
                    image_url = result.get("image_url")
                    method = "nano-banana-pro"
                    model_display = "Nano Banana Pro"
                    quality_notes = "Referans görsel olmadan Nano Banana Pro ile üretildi."
                    
                    # ==========================================
                    # 🔍 2. SELF-REFLECTION (AUTO-CORRECTION) BAŞLANGICI
                    # ==========================================
                    prompt_lower = prompt.lower()
                    needs_text = any(kw in prompt_lower for kw in ["yaz", "text", "saying", "written", "letters", "kelime", "harf"])
                    
                    if needs_text:
                        print("🤖 🔍 SELF-REFLECTION TETIKLENDI (NON-REF): Görselde yazı istendi, kalite kontrol yapılıyor...")
                        try:
                            analysis_result = await self._analyze_image({
                                "image_url": image_url,
                                "question": "Bu görseldeki yazıları BİREBİR OKU. Eğer prompttaki istenen yazıyla eşleşmiyorsa, harf hatası (typo) varsa veya anlamsız bozuk şekiller varsa SADECE 'HATA: [hatanın detayı]' yaz. Her şey kusursuzsa SADECE 'KUSURSUZ' yaz."
                            })
                            
                            analysis_text = analysis_result.get("analysis", "")
                            print(f"   📊 Analiz Sonucu: {analysis_text}")
                            
                            if analysis_result.get("success") and "HATA" in analysis_text.upper() and "KUSURSUZ" not in analysis_text.upper():
                                print("   ❌ Kalite kontrol başarısız! Otonom düzeltme (Retry 1) başlatılıyor...")
                                correction_prompt = f"{prompt}. CRITICAL FIX: The previous generation failed because: {analysis_text}. You MUST render the text flawlessly this time. Use high contrast, clear typography, and double check spelling."
                                
                                retry_result = await self.fal_plugin.execute("generate_image", {
                                    "prompt": correction_prompt,
                                    "aspect_ratio": aspect_ratio,
                                    "resolution": resolution
                                })
                                
                                if retry_result.success and retry_result.data.get("image_url"):
                                    print("   ✅ Otonom düzeltme başarılı! Yeni görsel kullanılıyor.")
                                    image_url = retry_result.data.get("image_url")
                                    method = "nano-banana-pro (Auto-Corrected)"
                                    model_display = "Nano Banana Pro (Auto-Corrected)"
                                    quality_notes += " | 🤖 Otonom Self-Reflection çalıştı ve tespit edilen yazım hatası düzeltildi."
                        except Exception as ref_err:
                            print(f"⚠️ Self-Reflection hatası (Gözardı ediliyor): {ref_err}")
                    # ==========================================
                    # 🔍 SELF-REFLECTION BİTİŞİ
                    # ==========================================
                    
                    # 📦 Asset'i veritabanına kaydet
                    entity_ids = [str(getattr(e, 'id', None)) for e in resolved_entities if getattr(e, 'id', None)] if resolved_entities else None
                    await asset_service.save_asset(
                        db=db,
                        session_id=session_id,
                        url=image_url,
                        asset_type="image",
                        prompt=prompt,
                        model_name=method,
                        model_params={
                            "aspect_ratio": aspect_ratio,
                            "resolution": resolution,
                            "face_reference_used": False
                        },
                        entity_ids=entity_ids
                    )
                    
                    # 📊 İstatistik kaydet
                    user_id = await get_user_id_from_session(db, session_id)
                    await StatsService.track_image_generation(db, user_id, method)
                    
                    return {
                        "success": True,
                        "image_url": image_url,
                        "model": method,
                        "model_display_name": model_display,
                        "quality_notes": quality_notes,
                        "message": f"Görsel başarıyla üretildi ({model_display}).",
                        "agent_decision": f"Referans görsel yok, {model_display} kullanıldı"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Görsel üretilemedi")
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_entity(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        entity_type: str, 
        params: dict,
        current_reference_image: str = None
    ) -> dict:
        """
        Yeni entity oluştur.
        
        Eğer use_current_reference=True ise veya reference_image_url verilmişse,
        görseli fal.ai'ye yükleyip entity'ye kaydet.
        """
        try:
            reference_image_url = params.get("reference_image_url")
            use_current_reference = params.get("use_current_reference", False)
            
            # Kullanıcı mevcut referans görselini kullanmak istiyorsa
            if use_current_reference and current_reference_image and not reference_image_url:
                # Base64 görseli fal.ai'ye yükle
                try:
                    upload_result = await self.fal_plugin.upload_base64_image(current_reference_image)
                    if upload_result.get("success"):
                        reference_image_url = upload_result.get("url")
                        print(f"📸 Referans görsel yüklendi: {reference_image_url[:50]}...")
                except Exception as upload_error:
                    print(f"⚠️ Referans görsel yükleme hatası: {upload_error}")
            
            # Session'dan user_id al
            user_id = await get_user_id_from_session(db, session_id)
            
            entity = await entity_service.create_entity(
                db=db,
                user_id=user_id,
                entity_type=entity_type,
                name=params.get("name"),
                description=params.get("description"),
                attributes=params.get("attributes", {}),
                reference_image_url=reference_image_url,
                session_id=session_id  # Opsiyonel - hangi projede oluşturulduğu
            )
            
            return {
                "success": True,
                "message": f"{entity.name} ({entity_type}) oluşturuldu. Tag: {entity.tag}",
                "entity": {
                    "id": str(entity.id),
                    "tag": entity.tag,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "reference_image_url": reference_image_url
                },
                "has_reference_image": bool(reference_image_url)
            }
        
        except ValueError as ve:
            # Duplicate entity hatası - kullanıcıya açık mesaj göster
            return {
                "success": False,
                "error": str(ve),
                "duplicate": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_entity(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """Tag ile entity bul."""
        try:
            tag = params.get("tag", "")
            user_id = await get_user_id_from_session(db, session_id)
            entity = await entity_service.get_by_tag(db, user_id, tag)
            
            if entity:
                return {
                    "success": True,
                    "entity": {
                        "id": str(entity.id),
                        "tag": entity.tag,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "description": entity.description,
                        "attributes": entity.attributes,
                        "reference_image_url": entity.reference_image_url
                    },
                    "has_reference_image": bool(entity.reference_image_url)
                }
            else:
                return {
                    "success": False,
                    "error": f"'{tag}' tag'i ile entity bulunamadı."
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _list_entities(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """Kullanıcının entity'lerini listele."""
        try:
            entity_type = params.get("entity_type", "all")
            user_id = await get_user_id_from_session(db, session_id)
            
            if entity_type == "all":
                entities = await entity_service.list_entities(db, user_id)
            else:
                entities = await entity_service.list_entities(db, user_id, entity_type)
            
            return {
                "success": True,
                "entities": [
                    {
                        "tag": e.tag,
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "description": e.description[:100] + "..." if e.description and len(e.description) > 100 else e.description,
                        "reference_image_url": e.reference_image_url,
                        "has_image": bool(e.reference_image_url)
                    }
                    for e in entities
                ],
                "count": len(entities)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ===============================
    # YENİ ARAÇ METODLARI
    # ===============================
    
    async def _generate_video(self, db: AsyncSession, session_id: uuid.UUID, params: dict, resolved_entities: list = None) -> dict:
        """
        Video üret (text-to-video veya image-to-video).
        
        Entity referansı varsa, önce görsel üretilip image-to-video yapılır.
        """
    async def _run_edit_video_bg(
        self,
        user_id: str,
        session_id: str,
        prompt: str,
        video_url: str,
        image_url: str = None,
    ):
        """Asenkron video düzenleme ve bildirimi."""
        asset_sid = session_id
        try:
            from app.core.database import async_session_maker
            from app.services.progress_service import progress_service
            import asyncio

            edit_payload = {
                "video_url": video_url,
                "prompt": prompt,
                "image_url": image_url,
            }

            await progress_service.send_progress(session_id, "video", 0.10, "Video düzenleme başlatıldı")

            progress_done = asyncio.Event()

            async def _smooth_progress():
                statuses = [
                    (0.18, "🎞️ Referans video analiz ediliyor..."),
                    (0.28, "🧠 Düzenleme talimatı uygulanıyor..."),
                    (0.40, "🎨 Yeni stil işleniyor..."),
                    (0.52, "🎬 Kareler yeniden oluşturuluyor..."),
                    (0.64, "✨ Geçişler ve hareket işleniyor..."),
                    (0.76, "📹 Çıktı hazırlanıyor..."),
                    (0.88, "💾 Kaydetme için son kontroller yapılıyor..."),
                ]
                for pct, msg in statuses:
                    if progress_done.is_set():
                        return
                    await asyncio.sleep(8)
                    if progress_done.is_set():
                        return
                    try:
                        await progress_service.send_progress(session_id, "video", pct, msg)
                    except Exception:
                        pass

            import time as _time
            import random as _random
            _edit_start = _time.time()
            _edit_last_reassurance = _time.time()

            async def _silence_detector():
                """Uzun sessizlik varsa bilinçli mesaj gönder."""
                nonlocal _edit_last_reassurance
                while not progress_done.is_set():
                    await asyncio.sleep(60)
                    if progress_done.is_set():
                        break
                    elapsed_since_last = _time.time() - _edit_last_reassurance
                    if elapsed_since_last >= 180:  # 3 dk sessizlik
                        elapsed_total = int((_time.time() - _edit_start) / 60)
                        msgs = [
                            f"⏳ Video düzenleme {elapsed_total} dakikadır sürüyor — model sırasında bekliyoruz. Bir sorun yok, devam ediyor!",
                            f"⏳ {elapsed_total} dakika oldu, düzenleme hâlâ devam ediyor. Yapay zeka modeli yoğun olabilir — birazdan hazır olacak.",
                            f"⏳ {elapsed_total}. dakikadayız. Düzenleme işlemi sürüyor, model kuyrukta bekliyoruz. Beklemene değecek!",
                        ]
                        try:
                            await progress_service.send_reassurance(session_id, "video", _random.choice(msgs))
                            _edit_last_reassurance = _time.time()
                        except Exception:
                            pass

            progress_task = asyncio.create_task(_smooth_progress())
            reassurance_task = asyncio.create_task(_silence_detector())
            try:
                plugin_result = await self.fal_plugin.execute("edit_video", edit_payload)
            finally:
                progress_done.set()
                progress_task.cancel()
                reassurance_task.cancel()

            result_data = plugin_result.data or {}

            async with async_session_maker() as db:
                if plugin_result.success:
                    video_url_out = result_data.get("video_url")
                    model_name = result_data.get("model", "video-edit")

                    await progress_service.send_progress(session_id, "video", 0.92, "Kaydediliyor")

                    if video_url_out:
                        await asset_service.save_asset(
                            db=db,
                            session_id=uuid.UUID(asset_sid),
                            url=video_url_out,
                            asset_type="video",
                            prompt=prompt or "Video edit",
                            model_name=model_name,
                            model_params={"source_video": video_url, "reference_image": image_url},
                            thumbnail_url=result_data.get("thumbnail_url"),
                        )

                    try:
                        await StatsService.track_video_generation(db, uuid.UUID(user_id), model_name)
                    except Exception as stats_err:
                        print(f"⚠️ Video edit istatistiği yazılamadı: {stats_err}")

                    from app.models.models import Message

                    new_msg_content = f"Videonuz hazır! (Model: {model_name})"
                    bg_message = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=new_msg_content,
                        metadata_={"videos": [{"url": video_url_out}]},
                    )
                    db.add(bg_message)
                    await db.commit()

                    await progress_service.send_complete(
                        session_id=session_id,
                        task_type="video",
                        result={
                            "video_url": video_url_out,
                            "message": new_msg_content,
                            "message_id": str(bg_message.id),
                        },
                    )
                else:
                    error_msg = plugin_result.error or "Video düzenleme başarısız oldu"
                    await progress_service.send_error(
                        session_id=session_id,
                        task_type="video",
                        error=error_msg,
                    )

                    from app.models.models import Message

                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(error_msg, "video"),
                    )
                    db.add(fail_msg)
                    await db.commit()
        except Exception as e:
            print(f"❌ Background video edit error: {e}")
            try:
                from app.services.progress_service import progress_service
                await progress_service.send_error(
                    session_id=session_id,
                    task_type="video",
                    error=str(e),
                )
            except Exception as ws_err:
                print(f"⚠️ Background video edit WS error bildirimi başarısız: {ws_err}")

            try:
                from app.core.database import async_session_maker
                async with async_session_maker() as db:
                    from app.models.models import Message

                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(str(e), "video"),
                    )
                    db.add(fail_msg)
                    await db.commit()
            except Exception as inner_e:
                print(f"❌ Could not save background video edit crash error to DB: {inner_e}")

    async def _queue_video_edit(self, db: AsyncSession, session_id: uuid.UUID, params: dict, message: str) -> dict:
        """Video düzenleme işini arka plana al."""
        try:
            import asyncio

            prompt = params.get("prompt", "")
            video_url = params.get("video_url")
            image_url = params.get("image_url")

            if not video_url:
                return {"success": False, "error": "Video referansı bulunamadı."}

            user_id = await get_user_id_from_session(db, session_id)

            task = asyncio.create_task(
                self._run_edit_video_bg(
                    user_id=str(user_id),
                    session_id=str(session_id),
                    prompt=prompt,
                    video_url=video_url,
                    image_url=image_url,
                )
            )

            global _GLOBAL_BG_TASKS
            _GLOBAL_BG_TASKS.add(task)
            task.add_done_callback(_GLOBAL_BG_TASKS.discard)
            self._register_bg_task(str(session_id), task)

            return {
                "success": True,
                "message": message,
                "is_background_task": True,
                "_bg_generation": {"type": "video", "prompt": (prompt or "")[:80], "duration": None},
            }
        except Exception as e:
            return {"success": False, "error": format_user_error_message(str(e), "video")}

    async def _run_video_bg(self, user_id: str, session_id: str, prompt: str, image_url: str, duration: str, aspect_ratio: str, model: str, entity_ids: list = None):
        """Asenkron kısa video üretimi ve bildirimi. session_id = proje."""
        asset_sid = session_id
        try:
            from app.core.database import async_session_maker
            from app.services.progress_service import progress_service
            
            # 🔄 Promptu İngilizce'ye çevir
            english_prompt = prompt
            try:
                from app.services.prompt_translator import translate_to_english
                english_prompt, _ = await translate_to_english(prompt)
                english_prompt = await self._enrich_prompt(english_prompt, "video")
            except Exception:
                pass
            
            video_payload = {
                "prompt": english_prompt,
                "image_url": image_url,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "model": model
            }
            
            # Üretim — Veo: Google SDK, diğerleri: fal.ai
            print(f"🚀 [BG] Video üretiliyor ({model}): {prompt[:50]}...")
            await progress_service.send_progress(session_id, "video", 0.10, "Üretim başlatıldı")
            
            # Simüle edilmiş smooth progress (10% → 65% arası 5sn arayla)
            import asyncio
            progress_done = asyncio.Event()
            
            async def _smooth_progress():
                # ~200 saniye kapsayacak şekilde 10sn arayla 20 adım
                statuses = [
                    (0.13, "🎬 Model hazırlanıyor..."),
                    (0.16, "🎨 Görsel analiz ediliyor..."),
                    (0.19, "🧠 Sahne planlanıyor..."),
                    (0.22, "🎥 Render başlatılıyor..."),
                    (0.25, "🎞️ Kare 1 oluşturuluyor..."),
                    (0.28, "✨ Animasyon işleniyor..."),
                    (0.31, "🎬 Hareket hesaplanıyor..."),
                    (0.34, "🔄 Kare dizisi render..."),
                    (0.37, "🎨 Detaylar ekleniyor..."),
                    (0.40, "📹 Işık ve gölge..."),
                    (0.43, "🎥 Fizik simülasyonu..."),
                    (0.46, "✨ Doku işleme..."),
                    (0.49, "🎬 Sahne derleniyor..."),
                    (0.52, "🔄 Kalite kontrol..."),
                    (0.55, "🎨 Renk düzeltme..."),
                    (0.58, "📹 Son kareler..."),
                    (0.61, "🎞️ Video kodlama..."),
                    (0.64, "✨ Optimizasyon..."),
                    (0.67, "📹 Neredeyse hazır..."),
                    (0.68, "⏳ Son dokunuşlar..."),
                ]
                for pct, msg in statuses:
                    if progress_done.is_set():
                        return
                    await asyncio.sleep(10)
                    if progress_done.is_set():
                        return
                    try:
                        await progress_service.send_progress(session_id, "video", pct, msg)
                    except Exception:
                        pass

            import time as _time
            import random as _random
            _vid_start = _time.time()
            _vid_last_reassurance = _time.time()

            async def _silence_detector():
                """Uzun sessizlik varsa bilinçli mesaj gönder."""
                nonlocal _vid_last_reassurance
                while not progress_done.is_set():
                    await asyncio.sleep(60)
                    if progress_done.is_set():
                        break
                    elapsed_since_last = _time.time() - _vid_last_reassurance
                    if elapsed_since_last >= 180:  # 3 dk sessizlik
                        elapsed_total = int((_time.time() - _vid_start) / 60)
                        msgs = [
                            f"⏳ Video üretimi {elapsed_total} dakikadır sürüyor — fal.ai model sırasında bekliyoruz. Bir sorun yok, devam ediyor!",
                            f"⏳ {elapsed_total} dakika oldu, video hâlâ üretiliyor. Yapay zeka modeli yoğun olabilir — birazdan hazır olacak.",
                            f"⏳ {elapsed_total}. dakikadayız. Model kuyrukta bekliyoruz, üretim devam ediyor. Beklemene değecek!",
                        ]
                        try:
                            await progress_service.send_reassurance(session_id, "video", _random.choice(msgs))
                            _vid_last_reassurance = _time.time()
                        except Exception:
                            pass

            progress_task = asyncio.create_task(_smooth_progress())
            reassurance_task = asyncio.create_task(_silence_detector())
            
            try:
                if model == "veo":
                    from app.services.google_video_service import GoogleVideoService
                    veo_svc = GoogleVideoService()
                    result = await veo_svc.generate_video(video_payload)
                else:
                    result = await self.fal_plugin._generate_video(video_payload)
            finally:
                progress_done.set()
                progress_task.cancel()
                reassurance_task.cancel()
            
            await progress_service.send_progress(session_id, "video", 0.70, "Video hazırlanıyor")
                
            async with async_session_maker() as db:
                if result.get("success"):
                    video_url = result.get("video_url")
                    model_name = result.get("model", model)
                    
                    # Asset Kaydet (PROJE session'a)
                    await progress_service.send_progress(session_id, "video", 0.90, "Kaydediliyor")
                    await asset_service.save_asset(
                        db=db,
                        session_id=uuid.UUID(asset_sid),
                        url=video_url,
                        asset_type="video",
                        prompt=prompt,
                        model_name=model_name,
                        model_params={
                            "duration": duration,
                            "aspect_ratio": aspect_ratio,
                            "source_image": image_url
                        },
                        entity_ids=entity_ids,
                        thumbnail_url=result.get("thumbnail_url")
                    )
                    
                    # İstatistik hatası kullanıcıya tamamlanan videoyu bozmasın.
                    try:
                        await StatsService.track_video_generation(db, uuid.UUID(user_id), model_name)
                    except Exception as stats_err:
                        print(f"⚠️ Video istatistiği yazılamadı: {stats_err}")
                    
                    # Mesaj oluştur ve Push at
                    from app.models.models import Message
                    new_msg_content = f"Videonuz hazır! ({duration}s, Model: {model_name})"
                    bg_message = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=new_msg_content,
                        metadata_={"videos": [{"url": video_url}]}
                    )
                    db.add(bg_message)
                    await db.commit()
                    
                    await progress_service.send_complete(
                        session_id=session_id,
                        task_type="video",
                        result={
                            "video_url": video_url,
                            "message": new_msg_content,
                            "message_id": str(bg_message.id)
                        }
                    )
                else:
                    error_msg = result.get("error", "Video üretilemedi")
                    await progress_service.send_error(
                        session_id=session_id,
                        task_type="video",
                        error=error_msg
                    )
                    
                    # ❌ Hatayı Mesaj Geçmişine Kaydet (User görsün)
                    from app.models.models import Message
                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(error_msg, "video")
                    )
                    db.add(fail_msg)
                    await db.commit()
        except Exception as e:
            print(f"❌ Background video error: {e}")
            try:
                from app.services.progress_service import progress_service
                await progress_service.send_error(
                    session_id=session_id,
                    task_type="video",
                    error=str(e)
                )
            except Exception as ws_err:
                print(f"⚠️ Background video WS error bildirimi başarısız: {ws_err}")

            try:
                from app.core.database import async_session_maker
                async with async_session_maker() as db:
                    from app.models.models import Message
                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(str(e), "video")
                    )
                    db.add(fail_msg)
                    await db.commit()
            except Exception as inner_e:
                print(f"❌ Could not save background crash error to DB: {inner_e}")

    async def _generate_video(self, db: AsyncSession, session_id: uuid.UUID, params: dict, resolved_entities: list = None) -> dict:
        """Video üret (3-10 sn) - Arka plana atar."""
        try:
            prompt = params.get("prompt", "")
            image_url = params.get("image_url")
            duration = params.get("duration", "5")
            aspect_ratio = params.get("aspect_ratio", "16:9")
            # Test branch'inde kredi tasarrufu önceliği: model verilmezse daha ucuz varsayılanı kullan.
            model = params.get("model") or "hailuo"
            
            # ⛔ 10s üstü videolar için plan zorunlu — generate_long_video'ya yönlendir
            if int(duration) > 10:
                return {
                    "success": False,
                    "error": f"⛔ {duration}s video 10 saniyeden uzun! 10s üstü videolar için generate_long_video aracını kullan. ÖNCE kullanıcıya sahne planı göster, onay al, sonra generate_long_video çağır."
                }
            
            user_id = await get_user_id_from_session(db, session_id)
            
            # Entity'leri IDs olarak hazırla
            entity_ids = [str(getattr(e, 'id', None)) for e in resolved_entities if getattr(e, 'id', None)] if resolved_entities else None
            
            # Entity description injection (Prompt'a ekle - BG'ye gitmeden önce)
            enriched_prompt = prompt
            brand_guidelines = ""
            if resolved_entities:
                for entity in resolved_entities:
                    if hasattr(entity, 'description') and entity.description:
                        enriched_prompt = f"{entity.description}. {enriched_prompt}"
                    if hasattr(entity, 'attributes') and entity.attributes:
                        banned = entity.attributes.get("banned_words", [])
                        aesthetic = entity.attributes.get("mandatory_aesthetic", "")
                        if banned:
                            brand_guidelines += f" ABSOLUTELY DO NOT INCLUDE: {', '.join(banned)}."
                        if aesthetic:
                            brand_guidelines += f" MANDATORY AESTHETIC RULES: {aesthetic}."

            if brand_guidelines:
                enriched_prompt = f"{enriched_prompt} | BRAND BOOK STRICT GUIDELINES: {brand_guidelines}"
                print(f"📖 Video Brand Book Kuralları Uygulandı: {brand_guidelines}")
            
            # Eğer image-to-video isteniyorsa ama görsel yoksa, BG'de beklemesi yerine burada generate_image yapamaz mı? 
            # Hayır, her şey BG'ye gidebilir. Ama user'a hemen bir şey döndürmemiz lazım.
            
            
            import asyncio
            task = asyncio.create_task(
                self._run_video_bg(
                    user_id=str(user_id),
                    session_id=str(session_id),
                    prompt=enriched_prompt,
                    image_url=image_url,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    model=model,
                    entity_ids=entity_ids
                )
            )
            
            # Prevent Python Garbage Collector from silently destroying the task
            global _GLOBAL_BG_TASKS
            if "_GLOBAL_BG_TASKS" not in globals():
                _GLOBAL_BG_TASKS = set()
            _GLOBAL_BG_TASKS.add(task)
            task.add_done_callback(_GLOBAL_BG_TASKS.discard)
            self._register_bg_task(str(session_id), task)
            
            decision = "Görselden video (i2v)" if image_url else "Metinden video (t2v)"
            
            # Kullanıcı olumsuz geri bildirim verdiyse empatik mesaj, değilse nötr mesaj
            prompt_lower = prompt.lower()
            negative_signals = ['beğenmedim', 'kötü', 'bozuk', 'berbat', 'yanlış', 'tekrar dene', 'yeniden', 'hoşuma gitmedi', 'olmamış', 'beğenmedi', 'istemiyorum']
            is_retry = any(s in prompt_lower for s in negative_signals)
            
            if is_retry:
                msg = f"Anlıyorum, hemen farklı bir yaklaşımla {duration} saniyelik videoyu {model.upper()} ile yeniden üretiyorum. ({decision}). Hazır olduğunda bildirim atacağım!"
            else:
                msg = f"{duration} saniyelik videoyu {model.upper()} ile arka planda üretmeye başladım. ({decision}). Hazır olduğunda sana bildirim atacağım!"
            
            return {
                "success": True,
                "message": msg,
                "is_background_task": True,
                "_bg_generation": {"type": "video", "prompt": prompt[:80], "duration": duration}
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_long_video_bg(self, user_id: str, session_id: str, prompt: str, total_duration: int, aspect_ratio: str, scene_descriptions: list):
        """Asenkron arka plan görevi: Video üret, DB'ye asset kaydet, yeni mesaj yarat ve Push at."""
        try:
            from app.core.database import async_session_maker
            from app.services.long_video_service import long_video_service
            from app.services.progress_service import progress_service
            
            # Prompt çevirisi
            english_prompt = prompt
            try:
                from app.services.prompt_translator import translate_to_english
                english_prompt, _ = await translate_to_english(prompt)
            except Exception:
                pass
            
            translated_scenes = None
            if scene_descriptions:
                try:
                    from app.services.prompt_translator import translate_to_english
                    translated_scenes = []
                    for scene in scene_descriptions:
                        if isinstance(scene, dict):
                            translated_txt, _ = await translate_to_english(scene.get("prompt", ""))
                            # Create a new dict to avoid mutating shared references
                            new_scene = dict(scene)
                            new_scene["prompt"] = translated_txt
                            translated_scenes.append(new_scene)
                        else:
                            translated, _ = await translate_to_english(str(scene))
                            translated_scenes.append(translated)
                except Exception:
                    translated_scenes = scene_descriptions
            
            import asyncio
            import time as _time
            import random
            import re as _re

            long_video_done = asyncio.Event()
            _start_time = _time.time()
            _last_reassurance_time = _time.time()
            _completed_scenes = 0
            _total_scenes = len(scene_descriptions) if scene_descriptions else 4
            _stitching_notified = False

            async def _on_progress(pct, msg):
                nonlocal _last_reassurance_time, _completed_scenes, _total_scenes, _stitching_notified
                try:
                    await progress_service.send_progress(session_id, "long_video", pct / 100.0, msg)
                except Exception:
                    pass

                if not msg:
                    return

                msg_lower = msg.lower()

                # --- Olay: Sahne tamamlandı ---
                if "tamamlandı" in msg_lower:
                    # Sayıyı mesajdan parse et (ör: "Sahne 2/4 tamamlandı")
                    match = _re.search(r'(\d+)/(\d+)', msg)
                    if match:
                        _completed_scenes = int(match.group(1))
                        _total_scenes = int(match.group(2))

                    remaining = _total_scenes - _completed_scenes
                    elapsed = int((_time.time() - _start_time) / 60)

                    if remaining > 0:
                        msgs = [
                            f"🎬 {_completed_scenes}. sahne hazır! Kalan {remaining} sahne daha var. Şu ana kadar {elapsed} dakika geçti, devam ediyorum!",
                            f"✅ Sahne {_completed_scenes}/{_total_scenes} tamamlandı! Sıradaki sahneye geçiyorum. {elapsed}. dakikadayız.",
                            f"🎬 {_completed_scenes}/{_total_scenes} bitti! {remaining} sahne kaldı. Model üzerinde çalışmaya devam ediyorum.",
                        ]
                        try:
                            await progress_service.send_reassurance(session_id, "long_video", random.choice(msgs), _completed_scenes, _total_scenes)
                            _last_reassurance_time = _time.time()
                        except Exception:
                            pass
                    # remaining == 0 → birleştirme mesajını gönderme, stitching callback'i gönderecek

                # --- Olay: Birleştirme başladı ---
                elif ("birleştir" in msg_lower or "stitch" in msg_lower) and not _stitching_notified:
                    _stitching_notified = True
                    elapsed = int((_time.time() - _start_time) / 60)
                    try:
                        await progress_service.send_reassurance(
                            session_id, "long_video",
                            f"🔧 Tüm {_total_scenes} sahne hazır! FFmpeg ile birleştiriyorum — son adım, {elapsed} dakikada buraya geldik. Neredeyse bitti! 🎉",
                            _total_scenes, _total_scenes
                        )
                        _last_reassurance_time = _time.time()
                    except Exception:
                        pass

            async def _silence_detector():
                """Uzun sessizlik varsa bilinçli mesaj gönder (3+ dk event yok)."""
                nonlocal _last_reassurance_time
                while not long_video_done.is_set():
                    await asyncio.sleep(60)  # Her dakika kontrol et
                    if long_video_done.is_set() or _stitching_notified:
                        break  # Birleştirme başladıysa artık sessizlik mesajı gönderme

                    elapsed_since_last = _time.time() - _last_reassurance_time
                    if elapsed_since_last >= 180:  # 3 dakikadır sessizlik
                        elapsed_total = int((_time.time() - _start_time) / 60)
                        msgs = [
                            f"⏳ {elapsed_total} dakika oldu, sahne {_completed_scenes + 1} üretiliyor — model sırasında bekliyoruz. Şu an {_completed_scenes}/{_total_scenes} sahne hazır. Bir sorun yok!",
                            f"⏳ {elapsed_total}. dakikadayız, hâlâ çalışıyorum! Sahne {_completed_scenes + 1}/{_total_scenes} üretiliyor, yapay zeka modeli yoğun olabilir.",
                            f"⏳ Şu an {_completed_scenes}/{_total_scenes} sahne tamamlandı. {elapsed_total} dakikadır üretim sürüyor — model kuyrukta bekliyoruz, devam edecek.",
                        ]
                        try:
                            await progress_service.send_reassurance(session_id, "long_video", random.choice(msgs), _completed_scenes, _total_scenes)
                            _last_reassurance_time = _time.time()
                        except Exception:
                            pass

            reassurance_task = asyncio.create_task(_silence_detector())

            try:
                result = await long_video_service.create_and_process(
                    user_id=user_id,
                    session_id=session_id,
                    prompt=english_prompt,
                    total_duration=total_duration,
                    aspect_ratio=aspect_ratio,
                    scene_descriptions=translated_scenes,
                    progress_callback=_on_progress
                )
            finally:
                long_video_done.set()
                reassurance_task.cancel()
            
            async with async_session_maker() as db:
                if result.get("success") and result.get("video_url"):
                    try:
                        await asset_service.save_asset(
                            db=db,
                            session_id=uuid.UUID(session_id),
                            url=result["video_url"],
                            asset_type="video",
                            prompt=prompt,
                            model_name="kling-3.0-pro-long",
                            model_params={
                                "total_duration": total_duration,
                                "segments": result.get("segments", 0),
                                "aspect_ratio": aspect_ratio,
                            },
                        )
                    except Exception as save_err:
                        print(f"⚠️ Long video asset kayıt hatası: {save_err}")
                    
                    from app.models.models import Message
                    new_msg_content = f"Videonuz hazır! {result.get('duration', total_duration)} saniyelik film {result.get('segments', 0)} sahneden birleştirildi."
                    bg_message = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=new_msg_content,
                        metadata_={"videos": [{"url": result["video_url"]}]}
                    )
                    db.add(bg_message)
                    await db.commit()
                    await db.refresh(bg_message)
                    
                    await progress_service.send_complete(
                        session_id=session_id,
                        task_type="long_video",
                        result={
                            "video_url": result["video_url"],
                            "message": new_msg_content,
                            "message_id": str(bg_message.id)
                        }
                    )
                else:
                    error_msg = result.get("error", "Uzun video üretilemedi")
                    await progress_service.send_error(
                        session_id=session_id,
                        task_type="long_video",
                        error=error_msg
                    )
                    
                    # ❌ Hatayı Mesaj Geçmişine Kaydet (User görsün)
                    from app.models.models import Message
                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(error_msg, "long_video")
                    )
                    db.add(fail_msg)
                    await db.commit()
        except Exception as e:
            print(f"❌ Background long video error: {e}")
            try:
                from app.services.progress_service import progress_service
                await progress_service.send_error(
                    session_id=session_id,
                    task_type="long_video",
                    error=str(e)
                )
            except Exception as ws_err:
                print(f"⚠️ Background long video WS error bildirimi başarısız: {ws_err}")

            try:
                from app.core.database import async_session_maker
                async with async_session_maker() as db:
                    from app.models.models import Message
                    fail_msg = Message(
                        session_id=uuid.UUID(session_id),
                        role="assistant",
                        content=format_user_error_message(str(e), "long_video")
                    )
                    db.add(fail_msg)
                    await db.commit()
            except Exception as inner_e:
                print(f"❌ Could not save background crash error to DB: {inner_e}")

    async def _generate_long_video(self, db: AsyncSession, session_id: uuid.UUID, params: dict, resolved_entities: list = None) -> dict:
        """Uzun video üret (30s - 3 dakika) - Arka plana atar."""
        # ⛔ Guard 1: scene_descriptions zorunlu ve en az 2 sahne
        scene_descriptions = params.get("scene_descriptions")
        if not scene_descriptions or len(scene_descriptions) < 2:
            return {
                "success": False, 
                "error": "⛔ PLAN GEREKLİ! scene_descriptions parametresine en az 2 detaylı sahne açıklaması ver. ÖNCE kullanıcıya sahne planını göster, onay al, sonra sahne açıklamalarıyla birlikte tekrar çağır."
            }
        
        prompt = params.get("prompt", "")
        total_duration = max(30, min(180, params.get("total_duration", 60)))
        aspect_ratio = params.get("aspect_ratio", "16:9")
        scene_descriptions = params.get("scene_descriptions")
        user_id = await get_user_id_from_session(db, session_id)
        
        # 🎨 Brand Book Injection
        brand_guidelines = ""
        if resolved_entities:
            for entity in resolved_entities:
                if hasattr(entity, 'attributes') and entity.attributes:
                    banned = entity.attributes.get("banned_words", [])
                    aesthetic = entity.attributes.get("mandatory_aesthetic", "")
                    if banned:
                        brand_guidelines += f" ABSOLUTELY DO NOT INCLUDE: {', '.join(banned)}."
                    if aesthetic:
                        brand_guidelines += f" MANDATORY AESTHETIC RULES: {aesthetic}."

        if brand_guidelines:
            # Append brand guidelines to every single scene description to ensure consistency across the entire long video
            for scene in scene_descriptions:
                if isinstance(scene, dict) and "prompt" in scene:
                    scene["prompt"] = f"{scene['prompt']} | BRAND BOOK STRICT GUIDELINES: {brand_guidelines}"
                elif isinstance(scene, str):
                    scene = f"{scene} | BRAND BOOK STRICT GUIDELINES: {brand_guidelines}"
            prompt = f"{prompt} | BRAND BOOK STRICT GUIDELINES: {brand_guidelines}"
            print(f"📖 Uzun Video Brand Book Kuralları Uygulandı: {brand_guidelines}")
        
        import asyncio
        task = asyncio.create_task(
            self._run_long_video_bg(
                user_id=str(user_id),
                session_id=str(session_id),
                prompt=prompt,
                total_duration=total_duration,
                aspect_ratio=aspect_ratio,
                scene_descriptions=scene_descriptions
            )
        )
        
        global _GLOBAL_BG_TASKS
        if "_GLOBAL_BG_TASKS" not in globals():
            _GLOBAL_BG_TASKS = set()
        _GLOBAL_BG_TASKS.add(task)
        task.add_done_callback(_GLOBAL_BG_TASKS.discard)
        self._register_bg_task(str(session_id), task)
        
        return {
            "success": True,
            "message": f"🎬 Video üretimi arka planda başladı! {total_duration} saniyelik filmin {len(scene_descriptions)} sahnesi sırayla üretilecek. Hazır olduğunda otomatik bildirim gelecek.",
            "is_background_task": True,
            "ai_instruction": "⚠️ VİDEO HENÜZ HAZIR DEĞİL! Arka planda üretiliyor. Kullanıcıya 'videon tamam/hazır' DEME! 'Üretim başladı, hazır olduğunda bildireceğim' gibi bir mesaj yaz.",
            "_bg_generation": {"type": "long_video", "prompt": prompt[:80], "duration": total_duration}
        }
    
    async def _save_style(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Stil/moodboard kaydet — sonraki üretimlerde otomatik uygulanır."""
        try:
            name = params.get("name", "")
            description = params.get("description", "")
            color_palette = params.get("color_palette", [])
            
            user_id = await get_user_id_from_session(db, session_id)
            
            # Kullanıcı hafızasına stil kaydet
            from app.services.conversation_memory_service import conversation_memory
            await conversation_memory.update_style_preference(user_id, "active_style", name)
            await conversation_memory.update_style_preference(user_id, "style_description", description)
            if color_palette:
                await conversation_memory.update_style_preference(user_id, "color_palette", ", ".join(color_palette))
            
            print(f"🎨 Stil kaydedildi: '{name}'")
            
            return {
                "success": True,
                "style_name": name,
                "message": f"'{name}' stili kaydedildi! Bundan sonraki tüm üretimlerde bu stil otomatik uygulanacak."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _generate_campaign(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Toplu kampanya üretimi — farklı formatlar ve varyasyonlar."""
        try:
            prompt = params.get("prompt", "")
            count = min(params.get("count", 4), 9)
            formats = params.get("formats", ["post"])
            brand_tag = params.get("brand_tag")
            
            # Format → aspect ratio mapping
            format_map = {
                "post": "1:1",
                "story": "9:16",
                "reel": "9:16",
                "cover": "16:9"
            }
            
            # Marka bilgisi varsa ekle
            brand_context = ""
            if brand_tag:
                try:
                    entity = await entity_service.get_by_tag(db, await get_user_id_from_session(db, session_id), brand_tag)
                    if entity and entity.attributes:
                        colors = entity.attributes.get("colors", {})
                        brand_context = f" Brand colors: {colors}. Brand: {entity.name}."
                except Exception:
                    pass
            
            # Prompt çevirisi
            english_prompt = prompt
            try:
                from app.services.prompt_translator import translate_to_english
                english_prompt, _ = await translate_to_english(prompt)
            except Exception:
                pass
            
            # Varyasyon prompt'ları oluştur
            variations = [
                f"{english_prompt}, clean minimalist design, centered composition.{brand_context}",
                f"{english_prompt}, vibrant dynamic composition, bold typography.{brand_context}",
                f"{english_prompt}, elegant premium feel, subtle gradients.{brand_context}",
                f"{english_prompt}, modern flat design, geometric shapes.{brand_context}",
                f"{english_prompt}, cinematic dramatic lighting, depth of field.{brand_context}",
                f"{english_prompt}, retro vintage aesthetic, warm tones.{brand_context}",
                f"{english_prompt}, neon futuristic style, dark background.{brand_context}",
                f"{english_prompt}, soft pastel colors, dreamy atmosphere.{brand_context}",
                f"{english_prompt}, high contrast black and white, editorial.{brand_context}",
            ][:count]
            
            # Paralel üretim
            import asyncio
            results = []
            
            for i, var_prompt in enumerate(variations):
                fmt = formats[i % len(formats)]
                aspect_ratio = format_map.get(fmt, "1:1")
                
                try:
                    result = await self.fal_plugin.execute("generate_image", {
                        "prompt": var_prompt,
                        "aspect_ratio": aspect_ratio,
                        "image_size": "landscape_16_9" if aspect_ratio == "16:9" else 
                                     "portrait_9_16" if aspect_ratio == "9:16" else "square"
                    })
                    
                    if result.success and result.data.get("image_url"):
                        url = result.data["image_url"]
                        # Asset kaydet
                        try:
                            await asset_service.save_asset(
                                db=db, session_id=session_id,
                                url=url, asset_type="image",
                                prompt=var_prompt,
                                model_name="campaign",
                                model_params={"format": fmt, "variation": i + 1}
                            )
                        except Exception:
                            pass
                        
                        results.append({
                            "url": url,
                            "format": fmt,
                            "aspect_ratio": aspect_ratio,
                            "variation": i + 1
                        })
                except Exception as e:
                    print(f"⚠️ Campaign varyasyon {i+1} hatası: {e}")
            
            return {
                "success": True,
                "images": results,
                "count": len(results),
                "message": f"{len(results)} varyasyon üretildi ({', '.join(formats)} formatlarında)."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _plan_and_execute(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict,
        resolved_entities: list = None
    ) -> dict:
        """
        Phase 22: Full Autonomous Studio Orchestration.
        
        GPT-4o ile üretim planı oluşturup paralel yürütür.
        Tek cümlelik hedeften tam kampanya çıkarır.
        """
        try:
            from app.services.campaign_planner_service import campaign_planner
            
            goal = params.get("goal", "")
            brand_tag = params.get("brand_tag")
            output_types = params.get("output_types")
            count = params.get("count")
            formats = params.get("formats")
            style_notes = params.get("style_notes", "")
            
            if not goal:
                return {"success": False, "error": "Hedef (goal) belirtilmedi."}
            
            # Brand context oluştur
            brand_context = ""
            if brand_tag:
                try:
                    user_id = await get_user_id_from_session(db, session_id)
                    entity = await entity_service.get_by_tag(db, user_id, brand_tag)
                    if entity:
                        attrs = entity.attributes or {}
                        colors = attrs.get("colors", {})
                        brand_context = (
                            f"Marka: {entity.name}. "
                            f"Açıklama: {entity.description or ''}. "
                            f"Renkler: primary={colors.get('primary', '')}, "
                            f"secondary={colors.get('secondary', '')}, "
                            f"accent={colors.get('accent', '')}. "
                            f"Slogan: {attrs.get('tagline', '')}. "
                            f"Ton: {attrs.get('tone', '')}. "
                            f"Sektör: {attrs.get('industry', '')}."
                        )
                except Exception as e:
                    print(f"⚠️ Brand context alınamadı: {e}")
            
            # Entity context oluştur
            entity_context = ""
            if resolved_entities:
                for ent in resolved_entities:
                    entity_context += f"@{getattr(ent, 'tag', '')}: {getattr(ent, 'name', '')} — {getattr(ent, 'description', '')[:80]}. "
            
            print(f"\n🚀 [Phase 22] OTONOM KAMPANYA BAŞLADI")
            print(f"   Hedef: {goal}")
            print(f"   Marka: {brand_context[:80] if brand_context else 'Yok'}")
            
            # 1. Plan oluştur (GPT-4o)
            plan = await campaign_planner.plan_campaign(
                goal=goal,
                brand_context=brand_context,
                entity_context=entity_context,
                output_types=output_types,
                count=count,
                formats=formats,
                style_notes=style_notes
            )
            
            if not plan.get("success"):
                return {
                    "success": False,
                    "error": plan.get("error", "Plan oluşturulamadı")
                }
            
            tasks = plan.get("tasks", [])
            plan_title = plan.get("plan_title", "Kampanya")
            plan_summary = plan.get("plan_summary", "")
            
            print(f"   📋 Plan: {plan_title} ({len(tasks)} görev)")
            for t in tasks:
                print(f"      - [{t.get('type', '?')}] {t.get('label', t.get('id', '?'))}")
            
            # 2. Planı yürüt (paralel + sıralı)
            execution_result = await campaign_planner.execute_plan(
                plan=plan,
                orchestrator=self,
                db=db,
                session_id=session_id,
                resolved_entities=resolved_entities
            )
            
            completed = execution_result.get("completed", 0)
            total = execution_result.get("total_tasks", 0)
            failed = execution_result.get("failed", 0)
            results = execution_result.get("results", [])
            
            # Başarılı sonuçları özetle
            image_urls = [r["url"] for r in results if r["type"] == "image" and r.get("url")]
            video_urls = [r["url"] for r in results if r["type"] == "video" and r.get("url")]
            audio_urls = [r["url"] for r in results if r["type"] == "audio" and r.get("url")]
            
            # Sonuç mesajı
            parts = []
            if image_urls:
                parts.append(f"{len(image_urls)} görsel")
            if video_urls:
                parts.append(f"{len(video_urls)} video")
            if audio_urls:
                parts.append(f"{len(audio_urls)} ses")
            
            summary_msg = f"✅ {plan_title}: {' + '.join(parts)} üretildi ({completed}/{total} başarılı)."
            if failed > 0:
                summary_msg += f" ⚠️ {failed} görev başarısız oldu."
            
            print(f"   ✅ Kampanya tamamlandı: {completed}/{total}")
            
            return {
                "success": True,
                "plan_title": plan_title,
                "plan_summary": plan_summary,
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "image_urls": image_urls,
                "video_urls": video_urls,
                "audio_urls": audio_urls,
                "results": results,
                "message": summary_msg
            }
            
        except Exception as e:
            print(f"❌ Phase 22 plan_and_execute hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def _advanced_edit_video(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        Phase 23: FFmpeg tabanlı gelişmiş video düzenleme.
        VideoEditorService'i dispatch eder.
        """
        try:
            from app.services.video_editor_service import video_editor
            from app.services.asset_service import asset_service
            
            operation = params.get("operation", "")
            video_url = params.get("video_url", "")
            
            if not operation:
                return {"success": False, "error": "İşlem (operation) belirtilmedi."}
            
            # Concat video_urls'den alır
            if operation == "concat" and not video_url:
                video_urls = params.get("video_urls", [])
                if len(video_urls) < 2:
                    return {"success": False, "error": "Birleştirme için en az 2 video URL gerekli (video_urls)."}
            elif not video_url and operation != "concat":
                return {"success": False, "error": "Video URL gerekli."}
            
            print(f"\n✂️ [Phase 23] Video Edit: {operation}")
            print(f"   video_url: {video_url[:60] if video_url else 'N/A'}...")
            
            result = None
            
            if operation == "trim":
                result = await video_editor.trim(
                    video_url=video_url,
                    start_time=params.get("start_time", 0),
                    end_time=params.get("end_time"),
                    duration=params.get("duration"),
                )
            elif operation == "speed":
                result = await video_editor.change_speed(
                    video_url=video_url,
                    speed=params.get("speed", 1.0),
                )
            elif operation == "fade":
                result = await video_editor.add_fade(
                    video_url=video_url,
                    fade_in=params.get("fade_in", 0),
                    fade_out=params.get("fade_out", 0),
                )
            elif operation == "text_overlay":
                result = await video_editor.add_text_overlay(
                    video_url=video_url,
                    text=params.get("text", ""),
                    position=params.get("text_position", "bottom"),
                    font_size=params.get("font_size", 48),
                    font_color=params.get("font_color", "white"),
                    start_time=params.get("start_time", 0),
                    duration=params.get("duration"),
                )
            elif operation == "reverse":
                result = await video_editor.reverse(video_url=video_url)
            elif operation == "resize":
                result = await video_editor.resize(
                    video_url=video_url,
                    aspect_ratio=params.get("aspect_ratio"),
                    width=params.get("width"),
                    height=params.get("height"),
                )
            elif operation == "concat":
                video_urls = params.get("video_urls", [])
                if video_url and video_url not in video_urls:
                    video_urls.insert(0, video_url)
                result = await video_editor.concat(video_urls=video_urls)
            elif operation == "loop":
                result = await video_editor.loop(
                    video_url=video_url,
                    count=params.get("loop_count", 2),
                )
            elif operation == "filter":
                result = await video_editor.apply_filter(
                    video_url=video_url,
                    filter_name=params.get("filter_name", "grayscale"),
                    intensity=params.get("filter_intensity", 1.0),
                )
            elif operation == "extract_frame":
                result = await video_editor.extract_frame(
                    video_url=video_url,
                    timestamp=params.get("timestamp", 0),
                )
            else:
                return {"success": False, "error": f"Bilinmeyen video düzenleme işlemi: {operation}"}
            
            # Başarılı sonuçları asset olarak kaydet
            if result and result.get("success"):
                output_url = result.get("video_url") or result.get("image_url")
                output_type = "image" if operation == "extract_frame" else "video"
                if output_url:
                    try:
                        await asset_service.save_asset(
                            db=db, session_id=session_id,
                            url=output_url, asset_type=output_type,
                            prompt=f"Video edit: {operation}",
                            model_name="ffmpeg-editor",
                            model_params={"operation": operation, "source": video_url[:100]},
                        )
                    except Exception as save_err:
                        print(f"⚠️ Video edit asset kaydetme hatası: {save_err}")
                
                print(f"   ✅ {operation} başarılı: {output_url[:60]}...")
            else:
                print(f"   ❌ {operation} başarısız: {result.get('error', 'unknown')}")
            
            return result or {"success": False, "error": "İşlem sonuçsuz."}
            
        except Exception as e:
            print(f"❌ Phase 23 advanced_edit_video hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def _audio_visual_sync(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        Phase 24: Ses-Görüntü Senkronizasyonu.
        AudioSyncService'i dispatch eder.
        """
        try:
            from app.services.audio_sync_service import audio_sync
            from app.services.asset_service import asset_service
            
            operation = params.get("operation", "")
            video_url = params.get("video_url", "")
            audio_url = params.get("audio_url", "")
            
            if not operation:
                return {"success": False, "error": "İşlem (operation) belirtilmedi."}
            
            print(f"\n🎵 [Phase 24] Audio-Visual Sync: {operation}")
            
            result = None
            
            if operation == "analyze_audio":
                if not audio_url:
                    return {"success": False, "error": "audio_url gerekli."}
                result = await audio_sync.analyze_audio(audio_url)
            
            elif operation == "detect_beats":
                if not audio_url:
                    return {"success": False, "error": "audio_url gerekli."}
                result = await audio_sync.detect_beats(audio_url)
            
            elif operation == "beat_cut_list":
                if not audio_url:
                    return {"success": False, "error": "audio_url gerekli."}
                result = await audio_sync.generate_beat_cut_list(
                    audio_url=audio_url,
                    video_duration=params.get("video_duration", 10.0),
                    num_cuts=params.get("num_cuts", 5),
                )
            
            elif operation == "generate_sfx":
                if not video_url:
                    return {"success": False, "error": "video_url gerekli."}
                result = await audio_sync.generate_sfx_from_video(video_url)
                # SFX'i asset olarak kaydet
                if result and result.get("success") and result.get("audio_url"):
                    try:
                        await asset_service.save_asset(
                            db=db, session_id=session_id,
                            url=result["audio_url"], asset_type="audio",
                            prompt="Auto-generated SFX",
                            model_name="mirelo-sfx-v1.5",
                        )
                    except Exception:
                        pass
            
            elif operation == "smart_mix":
                if not video_url or not audio_url:
                    return {"success": False, "error": "video_url ve audio_url gerekli."}
                result = await audio_sync.smart_mix(
                    video_url=video_url,
                    audio_url=audio_url,
                    music_volume=params.get("music_volume", 0.3),
                    fade_in=params.get("fade_in", 0.5),
                    fade_out=params.get("fade_out", 1.0),
                )
                if result and result.get("success") and result.get("video_url"):
                    try:
                        await asset_service.save_asset(
                            db=db, session_id=session_id,
                            url=result["video_url"], asset_type="video",
                            prompt="Smart audio mix",
                            model_name="ffmpeg-smart-mix",
                        )
                    except Exception:
                        pass
            
            elif operation == "tts_narration":
                if not video_url:
                    return {"success": False, "error": "video_url gerekli."}
                text = params.get("text", "")
                if not text:
                    return {"success": False, "error": "Seslendirme metni (text) gerekli."}
                result = await audio_sync.add_tts_narration(
                    video_url=video_url,
                    text=text,
                    voice=params.get("voice", "nova"),
                    start_time=params.get("start_time", 0),
                )
                if result and result.get("success") and result.get("video_url"):
                    try:
                        await asset_service.save_asset(
                            db=db, session_id=session_id,
                            url=result["video_url"], asset_type="video",
                            prompt=f"TTS narration: {text[:50]}",
                            model_name="tts-narration",
                        )
                    except Exception:
                        pass
            
            else:
                return {"success": False, "error": f"Bilinmeyen ses senkronizasyon işlemi: {operation}"}
            
            if result and result.get("success"):
                print(f"   ✅ {operation} başarılı")
            else:
                print(f"   ❌ {operation}: {result.get('error', 'unknown') if result else 'no result'}")
            
            return result or {"success": False, "error": "İşlem sonuçsuz."}
            
        except Exception as e:
            print(f"❌ Phase 24 audio_visual_sync hatası: {e}")
            return {"success": False, "error": str(e)}
    
    async def _resize_image(self, db, session_id, params: dict) -> dict:
        """Tek görsel birçok boyut — Nano Banana 2 ile AI-powered aspect ratio dönüşümü."""
        try:
            from app.services.plugins.fal_plugin_v2 import fal_plugin_v2
            from app.services.asset_service import AssetService
            asset_service = AssetService()
            
            result = await fal_plugin_v2.execute("resize_image", params)
            
            if result.success and result.data:
                data = result.data
                images = data.get("images", [])
                
                # Her boyutu asset olarak kaydet
                image_url = None
                for img in images:
                    if img.get("image_url"):
                        try:
                            await asset_service.save_asset(
                                db=db, session_id=session_id,
                                url=img["image_url"], asset_type="image",
                                prompt=f"Resize: {img.get('ratio_name', img.get('ratio', ''))}",
                                model_name="nano-banana-2-edit",
                            )
                        except Exception:
                            pass
                        if not image_url:
                            image_url = img["image_url"]
                
                return {
                    "success": True,
                    "image_url": image_url,
                    "images": images,
                    "total": data.get("total", 0),
                    "model": "nano-banana-2-edit",
                }
            
            return {"success": False, "error": result.error or "Resize başarısız"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _transcribe_voice(self, params: dict) -> dict:
        """Sesli mesajı metne çevir (Whisper)."""
        try:
            from app.services.voice_audio_service import voice_audio_service
            return await voice_audio_service.transcribe(
                audio_url=params.get("audio_url", ""),
                language=params.get("language", "tr")
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # _add_audio_to_video eski voice_audio_service versiyonu silindi
    # Artık tek implementasyon aşağıdaki FFmpeg versiyonu (satır ~3298)
    
    async def _edit_image(self, params: dict) -> dict:
        """
        GERÇEK GÖRSEL DÜZENLEME (True Inpainting)
        
        fal.ai object-removal API kullanarak:
        - Orijinal görsel korunur
        - Sadece belirtilen nesne silinir/değiştirilir
        - "Gözlüğü kaldır", "şapkayı sil" gibi talimatlar doğrudan çalışır
        """
        try:
            image_url = params.get("image_url")
            edit_instruction = params.get("prompt", "")
            
            if not image_url:
                return {
                    "success": False,
                    "error": "image_url gerekli"
                }
            
            if not edit_instruction:
                return {
                    "success": False,
                    "error": "Düzenleme talimatı gerekli"
                }
            
            print(f"🎨 GERÇEK DÜZENLEME BAŞLADI (Object Removal)")
            print(f"   Görsel: {image_url[:60]}...")
            print(f"   Talimat: {edit_instruction}")
            
            # Talimatı İngilizce'ye çevir (daha iyi sonuç için)
            from app.services.prompt_translator import translate_to_english
            english_instruction, _ = await translate_to_english(edit_instruction)
            
            # Nesne silme talimatlarını tespit et
            removal_keywords = ["kaldır", "sil", "çıkar", "remove", "delete", "erase", "take off"]
            is_removal = any(kw in edit_instruction.lower() for kw in removal_keywords)
            
            import fal_client
            
            if is_removal:
                # Object Removal API - Nesne silme
                # Talimatı "object to remove" formatına çevir
                object_to_remove = english_instruction
                for word in ["remove", "delete", "erase", "take off", "the", "from", "image", "photo"]:
                    object_to_remove = object_to_remove.lower().replace(word, "").strip()
                
                print(f"   Silinecek nesne: {object_to_remove}")
                
                try:
                    result = await fal_client.subscribe_async(
                        "fal-ai/object-removal",
                        arguments={
                            "image_url": image_url,
                            "prompt": object_to_remove,  # "glasses", "hat" gibi
                        },
                        with_logs=True,
                    )
                    
                    if result and "image" in result:
                        print(f"✅ Object Removal başarılı!")
                        return {
                            "success": True,
                            "image_url": result["image"]["url"],
                            "original_image_url": image_url,
                            "model": "object-removal",
                            "method": "fal-ai/object-removal",
                            "message": f"'{object_to_remove}' görselden başarıyla kaldırıldı."
                        }
                except Exception as removal_error:
                    print(f"⚠️ Object Removal hatası: {removal_error}")
            
            # ---- DÜZENLEME PIPELINE (4 aşamalı) ----
            # Aşama 1: Gemini (true inpainting — en iyi kalite)
            # Aşama 2-4: fal.ai fallback modelleri + face swap
            
            import fal_client
            import asyncio
            
            face_ref = params.get("face_reference_url")
            all_refs = list(params.get("all_reference_urls", []) or [])
            if not all_refs and isinstance(edit_instruction, str):
                inline_ref_urls = []
                for match in re.findall(r"https?://[^\s)\]>\"']+", edit_instruction, flags=re.IGNORECASE):
                    cleaned_url = match.rstrip(".,]")
                    if cleaned_url != image_url and cleaned_url.lower().split("?", 1)[0].endswith((".png", ".jpg", ".jpeg", ".webp")):
                        inline_ref_urls.append(cleaned_url)
                if inline_ref_urls:
                    all_refs = list(dict.fromkeys(inline_ref_urls))
                    print(f"   🔗 Prompt içinden {len(all_refs)} referans URL çıkarıldı")
            if face_ref and face_ref not in all_refs:
                all_refs.insert(0, face_ref)

            # --- ZEKİ REFERANS SEÇİMİ (Phase 19) ---
            if len(all_refs) > 1:
                print(f"   🧠 Birden fazla referans var ({len(all_refs)}), en uygun olanı seçiliyor...")
                best_ref = await self._pick_best_reference(english_instruction, all_refs)
                if best_ref and best_ref in all_refs:
                    # Seçilen referansı en başa al
                    all_refs.remove(best_ref)
                    all_refs.insert(0, best_ref)
                    print(f"   ✅ En uygun referans seçildi: {best_ref[:60]}...")
            
            async def _post_edit_face_swap(edited_url: str, face_ref_url: str) -> str:
                """Edit sonrası orijinal yüzü geri koy."""
                if not face_ref_url:
                    return edited_url
                try:
                    print(f"   🔄 Face swap: orijinal yüzü geri koyuluyor...")
                    swap_result = await asyncio.wait_for(
                        fal_client.subscribe_async(
                            "fal-ai/face-swap",
                            arguments={
                                "base_image_url": edited_url,
                                "swap_image_url": face_ref_url,
                            },
                            with_logs=True,
                        ),
                        timeout=30
                    )
                    if swap_result and "image" in swap_result:
                        print(f"   ✅ Face swap başarılı!")
                        return swap_result["image"]["url"]
                    else:
                        print(f"   ⚠️ Face swap sonuç döndürmedi, orijinal edit kullanılıyor")
                        return edited_url
                except Exception as swap_err:
                    print(f"   ⚠️ Face swap hatası: {swap_err}, orijinal edit kullanılıyor")
                    return edited_url
            
            # ===== AŞAMA 1: GEMINI (True Inpainting) =====
            try:
                from app.services.gemini_image_service import gemini_image_service
                from app.core.config import settings as app_settings
                gemini_api_key = app_settings.GEMINI_API_KEY
                
                if gemini_api_key:
                    print(f"   🌟 Aşama 1: Gemini True Inpainting (Identity-Aware) deneniyor...")
                    
                    # Gemini service'in yeni metodunu kullan
                    res = await gemini_image_service.edit_with_reference(
                        prompt=english_instruction,
                        image_to_edit_url=image_url,
                        reference_images_urls=all_refs
                    )
                    
                    if res.get("success"):
                        print(f"✅ Gemini True Inpainting başarılı!")
                        return {
                            "success": True,
                            "image_url": res["image_url"],
                            "original_image_url": image_url,
                            "model": "gemini-inpainting",
                            "method": res.get("method_used", "gemini-inpainting"),
                            "message": "Görsel başarıyla düzenlendi."
                        }
                    else:
                        print(f"   ⚠️ Gemini başarısız: {res.get('error')}")
                else:
                    print(f"   ⚠️ GEMINI_API_KEY bulunamadı, Gemini atlanıyor")
            except Exception as gemini_err:
                print(f"   ⚠️ Gemini hatası: {gemini_err}")
            
            # ===== AŞAMA 2: Nano Banana Pro Edit + Face Swap =====
            try:
                print(f"   🎨 Aşama 2: Nano Banana Pro Edit deneniyor...")
                result = await asyncio.wait_for(
                    fal_client.subscribe_async(
                        "fal-ai/nano-banana-pro/edit",
                        arguments={
                            "image_url": image_url,
                            "image_urls": [image_url],
                            "prompt": english_instruction,
                        },
                        with_logs=True,
                    ),
                    timeout=45
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    edited_url = result["images"][0]["url"]
                    print(f"✅ Nano Banana Pro Edit başarılı!")
                    
                    # AKILLI FALLBACK: Tüm referansları dene
                    final_url = edited_url
                    if all_refs:
                        # İlk olarak face_ref dene, yoksa listedeki ilkini
                        top_face_ref = face_ref if face_ref else all_refs[0]
                        final_url = await _post_edit_face_swap(edited_url, top_face_ref)
                    
                    return {
                        "success": True,
                        "image_url": final_url,
                        "original_image_url": image_url,
                        "model": "nano-banana-pro-edit" + ("+face-swap" if final_url != edited_url else ""),
                        "method": "fal-ai/nano-banana-pro/edit",
                        "message": "Görsel başarıyla düzenlendi."
                    }
            except asyncio.TimeoutError:
                print(f"   ⚠️ Nano Banana Pro Edit timeout (45s)")
            except Exception as nano_err:
                print(f"   ⚠️ Nano Banana Pro Edit hatası: {nano_err}")
            
            # ===== AŞAMA 3: GPT Image 1 Edit + Face Swap =====
            try:
                print(f"   🎨 Aşama 3: GPT Image 1 Edit deneniyor...")
                result = await asyncio.wait_for(
                    fal_client.subscribe_async(
                        "fal-ai/gpt-image-1/edit-image",
                        arguments={
                            "image_urls": [image_url],
                            "prompt": english_instruction,
                        },
                        with_logs=True,
                    ),
                    timeout=60
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    edited_url = result["images"][0]["url"]
                    print(f"✅ GPT Image 1 Edit başarılı!")
                    
                    # AKILLI FALLBACK
                    final_url = edited_url
                    if all_refs:
                        top_face_ref = face_ref if face_ref else all_refs[0]
                        final_url = await _post_edit_face_swap(edited_url, top_face_ref)
                    
                    return {
                        "success": True,
                        "image_url": final_url,
                        "original_image_url": image_url,
                        "model": "gpt-image-1-edit" + ("+face-swap" if final_url != edited_url else ""),
                        "method": "fal-ai/gpt-image-1/edit-image",
                        "message": "Görsel başarıyla düzenlendi."
                    }
            except asyncio.TimeoutError:
                print(f"   ⚠️ GPT Image 1 Edit timeout (60s)")
            except Exception as gpt_edit_err:
                print(f"   ⚠️ GPT Image 1 Edit hatası: {gpt_edit_err}")
            
            # ===== AŞAMA 4: FLUX Kontext Pro + Face Swap =====
            try:
                print(f"   🎨 Aşama 4: FLUX Kontext Pro deneniyor...")
                result = await asyncio.wait_for(
                    fal_client.subscribe_async(
                        "fal-ai/flux-pro/kontext",
                        arguments={
                            "image_url": image_url,
                            "prompt": english_instruction,
                        },
                        with_logs=True,
                    ),
                    timeout=45
                )
                
                if result and "images" in result and len(result["images"]) > 0:
                    edited_url = result["images"][0]["url"]
                    print(f"✅ Image-to-image fallback başarılı!")
                    
                    # AKILLI FALLBACK
                    final_url = edited_url
                    if all_refs:
                        top_face_ref = face_ref if face_ref else all_refs[0]
                        final_url = await _post_edit_face_swap(edited_url, top_face_ref)
                    
                    return {
                        "success": True,
                        "image_url": final_url,
                        "original_image_url": image_url,
                        "model": "i2i-fallback" + ("+face-swap" if final_url != edited_url else ""),
                        "method": "fal-ai/nano-banana-pro",
                        "message": "Görsel düzenleme tamamlandı."
                    }
            except asyncio.TimeoutError:
                print(f"   ⚠️ FLUX Kontext Pro timeout (45s)")
            except Exception as kontext_err:
                print(f"   ⚠️ FLUX Kontext Pro hatası: {kontext_err}")
            
            # Hiçbir yöntem çalışmadı
            return {
                "success": False,
                "error": f"Görsel düzenleme başarısız. Lütfen daha basit bir talimat deneyin."
            }
        
        except Exception as e:
            print(f"❌ DÜZENLEME HATASI: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    async def _outpaint_image(self, params: dict) -> dict:
        """Görseli genişlet (outpainting)."""
        try:
            image_url = params.get("image_url")
            
            if not image_url:
                return {"success": False, "error": "image_url gerekli"}
            
            print(f"🔲 Outpainting başlatılıyor...")
            
            plugin_result = await self.fal_plugin.execute("outpaint_image", params)
            
            if plugin_result.success and plugin_result.data:
                return {
                    "success": True,
                    "image_url": plugin_result.data.get("image_url"),
                    "model": "outpaint",
                    "message": "Görsel başarıyla genişletildi."
                }
            return {"success": False, "error": plugin_result.error or "Outpainting başarısız"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _apply_style(self, params: dict) -> dict:
        """Görsele sanatsal stil uygula (style transfer)."""
        try:
            image_url = params.get("image_url")
            style = params.get("style", "impressionism")
            
            if not image_url:
                return {"success": False, "error": "image_url gerekli"}
            
            print(f"🎨 Style Transfer başlatılıyor: {style}")
            
            plugin_result = await self.fal_plugin.execute("apply_style", params)
            
            if plugin_result.success and plugin_result.data:
                return {
                    "success": True,
                    "image_url": plugin_result.data.get("image_url"),
                    "style_applied": style,
                    "model": "style-transfer",
                    "message": f"'{style}' stili başarıyla uygulandı."
                }
            return {"success": False, "error": plugin_result.error or "Stil aktarımı başarısız"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _pick_best_reference(self, prompt: str, reference_urls: list[str]) -> str:
        """
        Verilen prompt'a göre en uygun referans görseli seçer (GPT-4o Vision).
        Özellikle çoklu referanslarda (erkek/kadın ayrımı gibi) hayati önem taşır.
        """
        if not reference_urls:
            return None
        if len(reference_urls) == 1:
            return reference_urls[0]
            
        try:
            # Sadece ilk 4 referansı kontrol et (maliyet ve hız için)
            refs_to_check = reference_urls[:4]
            
            content = [
                {
                    "type": "text",
                    "content": (
                        f"I will provide a set of numbered images and a visual instruction. "
                        f"Your task is to tell me which image number (1, 2, 3, or 4) matches the visual elements or subjects "
                        f"mentioned in this instruction: '{prompt}'.\n"
                        f"Respond with ONLY the NUMBER of the matching image. If unsure, respond '1'.\n"
                        f"IMPORTANT: Do NOT attempt to identify people or recognize individuals. "
                        f"Simply match visual descriptions to image thumbnails."
                    )
                }
            ]
            
            for i, url in enumerate(refs_to_check):
                content.append({
                    "type": "text",
                    "content": f"Image {i+1} URL: {url}"
                })
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
                
            response = await self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=200
            )
            
            best_indicator = response.choices[0].message.content.strip().lower()
            
            # --- REFUSAL HANDLING ---
            refusal_keywords = ["maalesef", "üzgünüm", "tanımlayamam", "identif", "recognize", "sorry", "cannot help"]
            if any(kw in best_indicator for kw in refusal_keywords):
                print(f"   ⚠️ GPT-4o Refusal detected in reference picking. Falling back to first reference.")
                return reference_urls[0]

            # Sayı veya URL ayıkla
            import re
            numbers = re.findall(r'\d+', best_indicator)
            if numbers:
                idx = int(numbers[0]) - 1
                if 0 <= idx < len(refs_to_check):
                    return refs_to_check[idx]
            
            # Eğer URL döndüyse (eski mantık fallback)
            for url in reference_urls:
                if url in best_indicator:
                    return url
                    
            return reference_urls[0] # Fallback
            
        except Exception as e:
            print(f"   ⚠️ _pick_best_reference hatası: {e}")
            return reference_urls[0]

    async def _upscale_image(self, params: dict) -> dict:
        """Görsel kalitesini artır."""
        try:
            image_url = params.get("image_url")
            scale = params.get("scale", 2)
            
            if not image_url:
                return {
                    "success": False,
                    "error": "image_url gerekli"
                }
            
            result = await self.fal_plugin._upscale_image({
                "image_url": image_url,
                "scale": scale
            })
            
            if result.get("success"):
                return {
                    "success": True,
                    "image_url": result.get("image_url"),
                    "model": result.get("model"),
                    "message": f"Görsel {scale}x büyütüldü ve kalitesi artırıldı."
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Upscale yapılamadı")
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _remove_background(self, params: dict) -> dict:
        """Görsel arka planını kaldır."""
        try:
            image_url = params.get("image_url")
            
            if not image_url:
                return {
                    "success": False,
                    "error": "image_url gerekli"
                }
            
            # FalPluginV2._remove_background expects a dict with image_url
            result = await self.fal_plugin._remove_background(
                {"image_url": image_url}
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "image_url": result.get("image_url"),
                    "model": result.get("model", "bria-rmbg"),
                    "message": "Arka plan kaldırıldı, şeffaf PNG oluşturuldu."
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Arka plan kaldırılamadı")
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ===============================
    # AKILLI AGENT METODLARI
    # ===============================
    
    async def _get_past_assets(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """Geçmiş üretimleri getir."""
        try:
            entity_tag = params.get("entity_tag")
            asset_type = params.get("asset_type")
            favorites_only = params.get("favorites_only", False)
            limit = params.get("limit", 5)
            
            assets = await asset_service.get_session_assets(
                db=db,
                session_id=session_id,
                entity_tag=entity_tag,
                asset_type=asset_type,
                favorites_only=favorites_only,
                limit=limit
            )
            
            if not assets:
                return {
                    "success": True,
                    "assets": [],
                    "message": "Bu oturumda henüz üretilmiş içerik yok."
                }
            
            # Asset'leri serializable formata dönüştür
            asset_list = []
            for asset in assets:
                asset_list.append({
                    "id": str(asset.id),
                    "url": asset.url,
                    "type": asset.asset_type,
                    "prompt": asset.prompt[:100] + "..." if asset.prompt and len(asset.prompt) > 100 else asset.prompt,
                    "model": asset.model_name,
                    "is_favorite": asset.is_favorite,
                    "created_at": asset.created_at.isoformat() if asset.created_at else None
                })
            
            return {
                "success": True,
                "assets": asset_list,
                "count": len(asset_list),
                "message": f"{len(asset_list)} adet içerik bulundu."
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _mark_favorite(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """Asset'i favori olarak işaretle."""
        try:
            asset_url = params.get("asset_url")
            
            # URL verilmediyse son asset'i bul
            if not asset_url:
                last_asset = await asset_service.get_last_asset(db, session_id)
                if not last_asset:
                    return {
                        "success": False,
                        "error": "Favori yapılacak içerik bulunamadı."
                    }
                asset_id = last_asset.id
            else:
                # URL'den asset bul
                from sqlalchemy import select
                from app.models.models import GeneratedAsset
                
                result = await db.execute(
                    select(GeneratedAsset).where(
                        GeneratedAsset.url == asset_url,
                        GeneratedAsset.session_id == session_id
                    )
                )
                asset = result.scalar_one_or_none()
                if not asset:
                    return {
                        "success": False,
                        "error": "Asset bulunamadı."
                    }
                asset_id = asset.id
            
            # Favori olarak işaretle
            updated_asset = await asset_service.mark_favorite(db, asset_id, True)
            
            if updated_asset:
                return {
                    "success": True,
                    "asset_id": str(updated_asset.id),
                    "url": updated_asset.url,
                    "message": "İçerik favorilere eklendi! ⭐"
                }
            else:
                return {
                    "success": False,
                    "error": "Favori işaretlenemedi."
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _undo_last(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> dict:
        """Son işlemi geri al, önceki versiyona dön."""
        try:
            # Son asset'i bul
            last_asset = await asset_service.get_last_asset(db, session_id)
            
            if not last_asset:
                return {
                    "success": False,
                    "error": "Geri alınacak içerik bulunamadı."
                }
            
            # Parent'ı var mı kontrol et
            if last_asset.parent_asset_id:
                # Parent'ı getir
                parent_asset = await asset_service.get_asset_by_id(
                    db, last_asset.parent_asset_id
                )
                
                if parent_asset:
                    return {
                        "success": True,
                        "previous_url": parent_asset.url,
                        "previous_type": parent_asset.asset_type,
                        "current_url": last_asset.url,
                        "message": "Önceki versiyona dönüldü. İşte önceki içerik:"
                    }
            
            # Parent yoksa, son 2 asset'i getir
            recent_assets = await asset_service.get_session_assets(
                db, session_id, limit=2
            )
            
            if len(recent_assets) >= 2:
                previous_asset = recent_assets[1]
                return {
                    "success": True,
                    "previous_url": previous_asset.url,
                    "previous_type": previous_asset.asset_type,
                    "current_url": last_asset.url,
                    "message": "Bir önceki üretim gösteriliyor:"
                }
            else:
                return {
                    "success": False,
                    "error": "Geri dönülecek önceki içerik bulunamadı."
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ===============================
    # GÖRSEL MUHAKEME METODLARI
    # ===============================
    
    async def _enrich_prompt(self, prompt: str, media_type: str = "image") -> str:
        """
        Kısa/belirsiz promptları sinematik detaylı hale getir.
        Sadece 100 karakterden kısa promptlarda tetiklenir.
        """
        if not prompt or len(prompt) > 100:
            return prompt  # Zaten detaylı, dokunma
        
        try:
            type_context = "görsel" if media_type == "image" else "video"
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"Sen bir sinematik prompt mühendisisin. Verilen kısa {type_context} promptunu zenginleştir: ışık, atmosfer, kamera açısı, renk paleti, detaylar ekle. Orijinal anlamı koru, sadece detay ekle. Cevabın SADECE zenginleştirilmiş İngilizce prompt olsun, başka açıklama yazma. Max 2 cümle."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )
            
            enriched = response.choices[0].message.content.strip()
            if enriched and len(enriched) > len(prompt):
                print(f"✨ Prompt zenginleştirildi: '{prompt[:40]}...' → '{enriched[:60]}...'")
                return enriched
            return prompt
            
        except Exception:
            return prompt  # Hata durumunda orijinal promptu kullan
    
    async def _auto_quality_check(self, media_url: str, original_prompt: str, media_type: str = "image") -> str:
        """
        Otomatik kalite kontrolü — üretilen görseli/videoyu promptla karşılaştır.
        Hızlı analiz (max 200 token) — ciddi sorunları yakalar.
        """
        if not media_url or not original_prompt:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Hız için mini
                messages=[
                    {
                        "role": "system",
                        "content": "Sen bir kalite kontrol uzmanısın. Üretilen görseli orijinal promptla karşılaştır. SADECE ciddi sorunları bildir (yanlış yazı, eksik ana element, bariz hata). Küçük farklılıkları yoksay. Sorun yoksa 'OK' yaz. Sorun varsa tek cümleyle belirt."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Prompt: {original_prompt}\n\nBu görsel promptla uyumlu mu? Ciddi sorun var mı?"},
                            {
                                "type": "image_url",
                                "image_url": {"url": media_url, "detail": "low"}
                            }
                        ]
                    }
                ],
                max_tokens=200
            )
            
            check_result = response.choices[0].message.content.strip()
            
            if check_result.upper() in ["OK", "UYUMLU", "SORUN YOK"]:
                return None  # Sorun yok, ekleme yapma
            
            return f"⚠️ Kalite notu: {check_result}"
            
        except Exception:
            return None  # Hata durumunda sessizce atla
    
    async def _analyze_image(self, params: dict) -> dict:
        """
        Gelişmiş görsel analiz — GPT-4o Vision ile görseldeki her detayı okuma.
        Yazılar, objeler, renkler, ışık, kompozisyon, hatalar dahil.
        """
        try:
            image_url = params.get("image_url", "")
            question = params.get("question", "Bu görseli son derece detaylı analiz et. Şunları listele: 1) Görseldeki tüm yazılar/metinler, 2) Kişiler ve kıyafetleri, 3) Objeler ve konumları, 4) Arka plan ve mekan, 5) Renkler ve ışık, 6) Kompozisyon, 7) Varsa hatalar veya tutarsızlıklar.")
            
            if not image_url:
                return {"success": False, "error": "Görsel URL'si gerekli."}
            
            # GPT-4o Vision çağrısı — detaylı analiz için yüksek token limiti
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Sen uzman bir görsel analist ve yaratıcı yönetmensin. Görseli en ince detayına kadar analiz et. Hiçbir şeyi atlama — yazılar, yüz ifadeleri, ışık, gölgeler, arka plan detayları, renk paleti, kompozisyon, varsa AI üretim hataları (deforme eller, tutarsız gölgeler, bulanık yazılar vb.) hepsini raporla."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500
            )
            
            analysis = response.choices[0].message.content
            
            return {
                "success": True,
                "analysis": analysis,
                "message": f"Görsel analizi tamamlandı:\n\n{analysis}"
            }
        
        except Exception as e:
            return {"success": False, "error": f"Vision analizi başarısız: {str(e)}"}
    
    async def _analyze_video(self, params: dict) -> dict:
        """
        Video analiz — ffmpeg ile key frame'ler çıkarıp GPT-4o Vision ile analiz.
        Sahneleri, hareketleri, yazıları, hataları tespit eder.
        """
        try:
            import tempfile
            import subprocess
            import base64
            import os
            import httpx
            
            video_url = params.get("video_url", "")
            question = params.get("question", "Bu videodaki her sahneyi detaylıca analiz et: kişiler, hareketler, arka plan, yazılar, renkler, geçişler ve varsa hatalar.")
            num_frames = min(params.get("num_frames", 6), 12)
            
            if not video_url:
                return {"success": False, "error": "Video URL'si gerekli."}
            
            print(f"🎬 Video analizi başlıyor: {video_url[:60]}... ({num_frames} frame)")
            
            # 1. Videoyu indir
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = os.path.join(tmpdir, "video.mp4")
                
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(video_url)
                    if resp.status_code != 200:
                        return {"success": False, "error": f"Video indirilemedi (HTTP {resp.status_code})"}
                    with open(video_path, "wb") as f:
                        f.write(resp.content)
                
                # 2. Video süresini öğren
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
                    capture_output=True, text=True
                )
                import json as json_module
                try:
                    probe_data = json_module.loads(probe.stdout)
                    duration = float(probe_data.get("format", {}).get("duration", 10))
                except:
                    duration = 10.0
                
                print(f"   Video süresi: {duration:.1f}s")
                
                # 3. Key frame'leri çıkar (eşit aralıklarla)
                frame_paths = []
                interval = duration / (num_frames + 1)
                
                for i in range(num_frames):
                    timestamp = interval * (i + 1)
                    frame_path = os.path.join(tmpdir, f"frame_{i:02d}.jpg")
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-ss", str(timestamp),
                            "-i", video_path, "-vframes", "1",
                            "-q:v", "2", frame_path
                        ],
                        capture_output=True
                    )
                    if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                        frame_paths.append((frame_path, timestamp))
                
                if not frame_paths:
                    return {"success": False, "error": "Videodan frame çıkarılamadı."}
                
                print(f"   {len(frame_paths)} frame çıkarıldı")
                
                # 4. Frame'leri base64'e çevir ve GPT-4o'ya gönder
                content_parts = [
                    {
                        "type": "text",
                        "text": f"Bu bir videonun {len(frame_paths)} key frame'idir (toplam süre: {duration:.1f}s). Her frame'in zamanı belirtilmiştir.\n\nSoru: {question}\n\nHer frame'i sırayla analiz et ve sonra genel bir video özeti ver."
                    }
                ]
                
                for frame_path, timestamp in frame_paths:
                    with open(frame_path, "rb") as f:
                        frame_b64 = base64.b64encode(f.read()).decode("utf-8")
                    
                    content_parts.append({
                        "type": "text",
                        "text": f"\n--- Frame @ {timestamp:.1f}s ---"
                    })
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}",
                            "detail": "high"
                        }
                    })
                
                # 5. GPT-4o Vision ile analiz
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Sen uzman bir video analist ve yaratıcı yönetmensin. Videonun key frame'lerini analiz ediyorsun. Her frame'deki detayları (kişiler, hareketler, yazılar, objeler, arka plan, ışık, kamera açısı) titizlikle okuyup raporla. Sahneler arası geçişleri, tutarlılığı ve varsa hataları belirt. Sonunda genel bir video özeti ver."
                        },
                        {
                            "role": "user",
                            "content": content_parts
                        }
                    ],
                    max_tokens=2000
                )
                
                analysis = response.choices[0].message.content
                
                print(f"   ✅ Video analizi tamamlandı")
                
                return {
                    "success": True,
                    "analysis": analysis,
                    "duration": duration,
                    "frames_analyzed": len(frame_paths),
                    "message": f"Video analizi tamamlandı ({duration:.1f}s, {len(frame_paths)} frame):\n\n{analysis}"
                }
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Video analizi başarısız: {str(e)}"}

    async def _generate_music(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """
        AI müzik üretimi — Dual Model Smart Router.
        
        Models:
        - elevenlabs: Vokal + şarkı sözü, uzun parça (5dk), bölüm yapısı
        - stable_audio: Enstrümantal, ambient, sinematik, remix (Stable Audio 2.5)
        """
        try:
            import fal_client
            
            prompt = params.get("prompt", "")
            lyrics = params.get("lyrics")
            duration = params.get("duration", 30)
            model = params.get("model", "auto")  # auto, elevenlabs, stable_audio
            
            if not prompt:
                return {"success": False, "error": "Müzik promptu gerekli."}
            
            # --- Smart Model Selection ---
            if model == "auto":
                lower_prompt = prompt.lower()
                vocal_keywords = ["vokal", "vocal", "şarkı", "song", "lyrics", "söz", 
                                  "sing", "verse", "chorus", "şarkıcı", "singer"]
                if lyrics or any(kw in lower_prompt for kw in vocal_keywords):
                    model = "elevenlabs"
                else:
                    model = "stable_audio"
            
            print(f"🎵 Müzik üretimi başlıyor ({model}): {prompt[:60]}... ({duration}s)")
            
            audio_url = None
            used_model = model
            
            # --- ElevenLabs Music ---
            if model == "elevenlabs":
                try:
                    duration_ms = min(int(duration) * 1000, 300000)  # Max 5 dakika (ms)
                    fal_args = {
                        "prompt": f"{prompt}\n\n{lyrics}" if lyrics else prompt,
                        "music_length_ms": duration_ms,
                    }
                    
                    result = await fal_client.subscribe_async(
                        "fal-ai/elevenlabs/music-v1",
                        arguments=fal_args,
                        with_logs=True,
                    )
                    
                    if result and isinstance(result, dict):
                        for key in ["audio", "audio_url", "output"]:
                            if key in result:
                                val = result[key]
                                audio_url = val.get("url") if isinstance(val, dict) else val
                                if audio_url:
                                    used_model = "elevenlabs"
                                    break
                    
                    if not audio_url:
                        print("⚠️ ElevenLabs başarısız, Stable Audio'ya geçiliyor...")
                except Exception as el_err:
                    print(f"⚠️ ElevenLabs hatası: {el_err}, Stable Audio'ya geçiliyor...")
            
            # --- Stable Audio 2.5 (varsayılan veya fallback) ---
            if not audio_url:
                try:
                    sa_duration = min(int(duration), 190)  # Max 190 saniye
                    fal_args = {
                        "prompt": prompt,
                        "seconds_total": sa_duration,
                        "num_inference_steps": 8,
                    }
                    
                    result = await fal_client.subscribe_async(
                        "fal-ai/stable-audio-25/text-to-audio",
                        arguments=fal_args,
                        with_logs=True,
                    )
                    
                    if result and isinstance(result, dict):
                        for key in ["audio_file", "audio", "output"]:
                            if key in result:
                                val = result[key]
                                audio_url = val.get("url") if isinstance(val, dict) else val
                                if audio_url:
                                    used_model = "stable_audio"
                                    break
                except Exception as sa_err:
                    print(f"⚠️ Stable Audio hatası: {sa_err}")
            
            # --- Son Fallback: CassetteAI ---
            if not audio_url:
                try:
                    print("⚠️ Ana modeller başarısız, CassetteAI deneniyor...")
                    result = await fal_client.subscribe_async(
                        "cassetteai/music-gen",
                        arguments={"prompt": prompt, "duration": min(int(duration), 120)},
                        with_logs=True,
                    )
                    if result and isinstance(result, dict) and "audio_file" in result:
                        val = result["audio_file"]
                        audio_url = val.get("url") if isinstance(val, dict) else val
                        used_model = "cassetteai"
                except Exception:
                    pass
            
            if not audio_url:
                return {"success": False, "error": "Müzik üretilemedi. Tüm modeller başarısız oldu."}
            
            print(f"✅ Müzik üretildi ({used_model}): {audio_url[:60]}...")
            
            # --- Asset olarak kaydet (Medya Varlıkları paneline) ---
            try:
                from app.services.asset_service import asset_service
                await asset_service.save_asset(
                    db=db,
                    session_id=session_id,
                    url=audio_url,
                    asset_type="audio",
                    prompt=prompt,
                    model_name=used_model,
                    model_params={"duration": duration, "model": used_model}
                )
                print(f"💾 Ses dosyası Medya Varlıklarına kaydedildi.")
            except Exception as save_err:
                print(f"⚠️ Ses asset kaydetme hatası: {save_err}")
            
            return {
                "success": True,
                "audio_url": audio_url,
                "duration": duration,
                "model": used_model,
                "message": f"🎵 Müzik üretildi ({duration}s, {used_model}). Kullanıcıya şu markdown linkini VER: [Müziği dinle]({audio_url})"
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Müzik üretimi başarısız: {str(e)}"}
    
    async def _add_audio_to_video(self, db, session_id, params: dict) -> dict:
        """Videoya müzik/ses ekle — LOKAL FFmpeg ile birleştir, fal storage'a yükle."""
        try:
            import fal_client
            import httpx
            import tempfile
            import subprocess
            import os
            from app.services.asset_service import asset_service
            
            video_url = params.get("video_url", "")
            audio_url = params.get("audio_url", "")
            replace_audio = params.get("replace_audio", True)
            
            if not video_url or not audio_url:
                return {"success": False, "error": "video_url ve audio_url gerekli."}
            
            print(f"🎬+🎵 Video-müzik birleştirme başlıyor (lokal FFmpeg)...")
            print(f"   Video: {video_url[:80]}...")
            print(f"   Audio: {audio_url[:80]}...")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                video_path = os.path.join(tmp_dir, "input_video.mp4")
                audio_path = os.path.join(tmp_dir, "input_audio.wav")
                output_path = os.path.join(tmp_dir, "output.mp4")
                
                # 1. Video ve audio dosyalarını indir
                print("   ⬇️ Dosyalar indiriliyor...")
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    video_resp = await client.get(video_url)
                    if video_resp.status_code != 200:
                        return {"success": False, "error": f"Video indirilemedi (HTTP {video_resp.status_code})"}
                    with open(video_path, "wb") as f:
                        f.write(video_resp.content)
                    
                    audio_resp = await client.get(audio_url)
                    if audio_resp.status_code != 200:
                        return {"success": False, "error": f"Audio indirilemedi (HTTP {audio_resp.status_code})"}
                    with open(audio_path, "wb") as f:
                        f.write(audio_resp.content)
                
                print(f"   ✅ Video: {os.path.getsize(video_path)} bytes, Audio: {os.path.getsize(audio_path)} bytes")
                
                # 2. FFmpeg ile birleştir
                if replace_audio:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", video_path,
                        "-i", audio_path,
                        "-c:v", "copy", "-c:a", "aac",
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-shortest",
                        "-movflags", "+faststart",
                        output_path
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", video_path,
                        "-i", audio_path,
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=shortest[aout]",
                        "-c:v", "copy",
                        "-map", "0:v:0", "-map", "[aout]",
                        "-movflags", "+faststart",
                        output_path
                    ]
                
                print(f"   🔧 FFmpeg çalıştırılıyor...")
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if proc.returncode != 0:
                    print(f"   ❌ FFmpeg hatası: {proc.stderr[:500]}")
                    return {"success": False, "error": f"FFmpeg birleştirme hatası: {proc.stderr[:200]}"}
                
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    return {"success": False, "error": "FFmpeg çıktı dosyası oluşturulamadı."}
                
                print(f"   ✅ Birleştirme tamamlandı: {os.path.getsize(output_path)} bytes")
                
                # 3. fal storage'a yükle
                print("   ⬆️ fal.ai storage'a yükleniyor...")
                final_url = fal_client.upload_file(output_path)
                print(f"   ✅ Yüklendi: {final_url[:60]}...")
            
            # 4. Asset olarak kaydet
            try:
                await asset_service.save_asset(
                    db=db,
                    session_id=session_id,
                    url=final_url,
                    asset_type="video",
                    prompt=f"Video + Audio birleştirildi",
                    model_name="ffmpeg-local",
                )
                print(f"💾 Birleştirilmiş video asset olarak kaydedildi")
            except Exception as save_err:
                print(f"⚠️ Asset kaydetme hatası: {save_err}")
            
            return {
                "success": True,
                "video_url": final_url,
                "message": f"🎬🎵 Video ve müzik başarıyla birleştirildi!"
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Video-müzik birleştirme hatası: {str(e)}"}
    
    async def _save_web_asset(self, db, session_id: str, params: dict) -> dict:
        """
        Agent'ın webt'den bulduğu görseli projenin Media Asset'lerine kaydetmesi.
        """
        try:
            from app.services.asset_service import asset_service
            
            asset_url = params.get("asset_url")
            asset_type = params.get("asset_type", "image")
            
            if not asset_url:
                return {"success": False, "error": "Kaydedilecek asset_url gerekli."}
                
            stored_asset = await asset_service.save_asset(
                db=db, 
                session_id=session_id,
                url=asset_url, 
                asset_type=asset_type,
                prompt="Agent tarafından webt'en otomatik olarak indirildi.",
                source="web_search"
            )
            
            if stored_asset:
                return {
                    "success": True,
                    "message": f"Kullanıcı için harika bir referans veya medya dosyası başarıyla Assets paneline kaydedildi! (URL: {asset_url})"
                }
            else:
                return {"success": False, "error": "Veritabanına kaydetme başarısız."}
                
        except Exception as e:
            return {"success": False, "error": f"Asset kaydetme hatası: {str(e)}"}
    
    async def _compare_images(self, params: dict) -> dict:
        """
        İki görseli karşılaştır.
        
        Agent bu metodu şu durumlarda kullanır:
        - Kullanıcı "hangisi daha iyi?" dediğinde
        - Önceki/şimdiki versiyonları kıyaslarken
        """
        try:
            from app.services.llm.claude_service import claude_service
            
            image_url_1 = params.get("image_url_1", "")
            image_url_2 = params.get("image_url_2", "")
            
            if not image_url_1 or not image_url_2:
                return {
                    "success": False,
                    "error": "Her iki görsel URL'si de gerekli."
                }
            
            result = await claude_service.compare_images(
                image_url_1=image_url_1,
                image_url_2=image_url_2
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "comparison": result.get("comparison"),
                    "message": "Görsel karşılaştırması tamamlandı."
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Karşılaştırma başarısız")
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ===============================
    # ROADMAP METODLARI
    # ===============================
    
    async def _create_roadmap(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """
        Çoklu adım görev planı (roadmap) oluştur.
        
        Agent karmaşık istekleri parçalara ayırarak yönetir.
        """
        try:
            from app.services.task_service import task_service
            
            goal = params.get("goal", "")
            steps = params.get("steps", [])
            
            if not goal or not steps:
                return {
                    "success": False,
                    "error": "Hedef ve adımlar gerekli."
                }
            
            # Roadmap oluştur
            roadmap = await task_service.create_roadmap(
                db=db,
                session_id=session_id,
                goal=goal,
                steps=steps
            )
            
            # İlk görevi otomatik başlat
            first_task = await task_service.get_next_task(db, roadmap.id)
            if first_task:
                await task_service.start_task(db, first_task.id)
            
            return {
                "success": True,
                "roadmap_id": str(roadmap.id),
                "goal": goal,
                "total_steps": len(steps),
                "steps": [
                    {
                        "step": i + 1,
                        "type": s.get("type"),
                        "description": s.get("description")
                    }
                    for i, s in enumerate(steps)
                ],
                "message": f"Roadmap oluşturuldu: {len(steps)} adımlık plan. İlk adım başlatıldı."
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_roadmap_progress(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        params: dict
    ) -> dict:
        """Roadmap ilerleme durumunu getir."""
        try:
            from app.services.task_service import task_service, TaskType
            
            roadmap_id = params.get("roadmap_id")
            
            if not roadmap_id:
                # Son aktif roadmap'i bul
                roadmaps = await task_service.get_session_roadmaps(db, session_id)
                if not roadmaps:
                    return {
                        "success": False,
                        "error": "Aktif roadmap bulunamadı."
                    }
                roadmap = roadmaps[0]
                roadmap_id = roadmap.id
            else:
                roadmap_id = uuid.UUID(roadmap_id)
                roadmap = await task_service.get_roadmap(db, roadmap_id)
            
            if not roadmap:
                return {
                    "success": False,
                    "error": "Roadmap bulunamadı."
                }
            
            # İlerleme durumunu getir
            progress = await task_service.get_roadmap_progress(db, roadmap_id)
            
            return {
                "success": True,
                "roadmap_id": str(roadmap_id),
                "goal": roadmap.input_data.get("goal", ""),
                "status": roadmap.status,
                "progress": progress,
                "message": f"İlerleme: {progress['completed']}/{progress['total']} adım tamamlandı ({progress['progress_percent']}%)"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ===============================
    # SİSTEM YÖNETİM METODLARI
    # ===============================
    
    async def _manage_project(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Proje yönetim işlemleri."""
        try:
            action = params.get("action")
            project_name = params.get("project_name")
            project_id = params.get("project_id")
            
            if action == "create":
                if not project_name:
                    return {"success": False, "error": "Proje adı gerekli."}
                new_id = str(uuid.uuid4())[:8]
                return {"success": True, "project_id": new_id, "message": f"'{project_name}' projesi oluşturuldu!"}
            
            elif action == "list":
                mock_projects = [{"id": "samsung", "name": "Samsung Campaign"}, {"id": "nike", "name": "Nike Spring"}]
                return {"success": True, "projects": mock_projects, "count": len(mock_projects)}
            
            elif action == "switch":
                return {"success": True, "message": f"'{project_id}' projesine geçildi."}
            
            elif action == "delete":
                return {"success": True, "message": f"'{project_id}' projesi çöp kutusuna taşındı."}
            
            return {"success": False, "error": f"Bilinmeyen action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _delete_entity(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Entity'yi çöp kutusuna taşı."""
        try:
            entity_tag = params.get("entity_tag", "").lstrip("@")
            if not entity_tag:
                return {"success": False, "error": "Entity tag gerekli."}
            
            entity = await entity_service.get_by_tag(db, session_id, f"@{entity_tag}")
            if not entity:
                return {"success": False, "error": f"'{entity_tag}' bulunamadı."}
            
            entity.is_deleted = True
            await db.commit()
            return {"success": True, "message": f"{entity.name} çöp kutusuna taşındı."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _manage_trash(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Çöp kutusu işlemleri."""
        try:
            action = params.get("action")
            item_id = params.get("item_id")
            
            if action == "list":
                from sqlalchemy import select
                from app.models.models import Entity
                result = await db.execute(select(Entity).where(Entity.session_id == session_id, Entity.is_deleted == True))
                items = result.scalars().all()
                trash = [{"id": str(i.id), "name": i.name, "type": i.entity_type} for i in items]
                return {"success": True, "items": trash, "count": len(trash), "message": f"Çöp kutusunda {len(trash)} öğe var." if trash else "Çöp kutusu boş."}
            
            elif action == "restore":
                from sqlalchemy import select
                from app.models.models import Entity
                result = await db.execute(select(Entity).where(Entity.id == uuid.UUID(item_id)))
                entity = result.scalar_one_or_none()
                if entity:
                    entity.is_deleted = False
                    await db.commit()
                    return {"success": True, "message": f"{entity.name} geri getirildi!"}
                return {"success": False, "error": "Öğe bulunamadı."}
            
            elif action == "empty":
                from sqlalchemy import delete
                from app.models.models import Entity
                await db.execute(delete(Entity).where(Entity.session_id == session_id, Entity.is_deleted == True))
                await db.commit()
                return {"success": True, "message": "Çöp kutusu boşaltıldı."}
            
            return {"success": False, "error": f"Bilinmeyen action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _manage_plugin(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Creative Plugin yönetimi — gerçek DB kaydı."""
        try:
            from app.models.models import Preset
            from sqlalchemy import select
            
            action = params.get("action")
            name = params.get("name")
            description = params.get("description", "")
            config = params.get("config", {})
            is_public = params.get("is_public", True)  # Varsayılan: toplulukta yayınla
            
            # User ID'yi session'dan al
            user_id = None
            try:
                user_id = await get_user_id_from_session(db, session_id)
            except Exception:
                pass
            
            if action == "create":
                if not name:
                    return {"success": False, "error": "Preset adı gerekli."}
                
                # AI'ın config'ini KULLANMA — session'daki gerçek entity'lerden oluştur
                from app.models.models import Entity
                entity_result = await db.execute(
                    select(Entity).where(
                        Entity.session_id == session_id
                    )
                )
                entities = entity_result.scalars().all()
                
                # Gerçek config'i entity'lerden oluştur
                config = {}
                characters = [e for e in entities if e.entity_type == "character"]
                locations = [e for e in entities if e.entity_type == "location"]
                
                if characters:
                    config["character_tag"] = characters[0].tag  # İlk karakter
                if locations:
                    config["location_tag"] = locations[0].tag  # İlk lokasyon
                
                # Stil bilgisini AI'dan al (hallüsinasyon riski düşük)
                ai_config = params.get("config", {})
                if ai_config.get("style"):
                    config["style"] = ai_config["style"]
                if ai_config.get("timeOfDay"):
                    config["timeOfDay"] = ai_config["timeOfDay"]
                if ai_config.get("cameraAngles"):
                    config["cameraAngles"] = ai_config["cameraAngles"]
                
                # Duplicate kontrolü — aynı session'da benzer plugin var mı?
                existing_result = await db.execute(
                    select(Preset).where(
                        Preset.session_id == session_id
                    )
                )
                existing_plugins = existing_result.scalars().all()
                if existing_plugins:
                    existing_names = [p.name for p in existing_plugins]
                    # Aynı isimde preset varsa bilgilendir
                    if name in existing_names:
                        return {
                            "success": False, 
                            "already_exists": True,
                            "message": f"Bu sohbette daha önce '{name}' adlı bir preset oluşturulmuş. 🔄 Tekrar oluşturmamı ister misiniz, yoksa mevcut preset'inizi düzenlemek mi istersiniz?\n\n📌 Mevcut preset'leriniz: {', '.join(existing_names)}\n\n💡 İpucu: Sol menüdeki ➡️ Topluluk butonuna tıklayıp ➡️ Preset'lerim sekmesinde mevcut preset'lerinizi görüntüleyebilir, toplulukta yayınlayabilir veya değişiklik yapabilirsiniz."
                        }
                    # Farklı isimde ama max 3 preset per session
                    if len(existing_plugins) >= 3:
                        return {
                            "success": False,
                            "already_exists": True,  
                            "message": f"Bu sohbette daha önce {len(existing_plugins)} preset oluşturulmuş: **{', '.join(existing_names)}**.\n\n🔄 Yine de yeni bir preset oluşturmamı ister misiniz?\n\n💡 İpucu: Sol menüdeki ➡️ Topluluk butonuna tıklayıp ➡️ Preset'lerim sekmesinde mevcut preset'lerinizi görüntüleyebilir, düzenleyebilir ve toplulukta yayınlayabilirsiniz."
                        }
                
                # Prompt template oluştur
                prompt_parts = []
                if config.get("character_tag"):
                    prompt_parts.append(config["character_tag"])
                if config.get("location_tag"):
                    prompt_parts.append(f"at {config['location_tag']}")
                if config.get("style"):
                    prompt_parts.append(f"{config['style']} style")
                if config.get("timeOfDay"):
                    prompt_parts.append(f"{config['timeOfDay']} lighting")
                if config.get("cameraAngles"):
                    prompt_parts.append(f"angles: {', '.join(config['cameraAngles'])}")
                
                system_prompt = config.get("promptTemplate") or ", ".join(prompt_parts) or f"{name} tarzında görsel üret"
                
                # DB'ye kaydet
                plugin = Preset(
                    user_id=user_id,
                    session_id=session_id,
                    name=name,
                    description=description or f"{name} preset'i",
                    icon="🧩",
                    color="#22c55e",
                    system_prompt=system_prompt,
                    is_public=is_public,
                    config=config
                )
                db.add(plugin)
                await db.commit()
                await db.refresh(plugin)
                
                # Deterministik başarı mesajı
                filled = []
                missing = []
                for field, label in [("character_tag", "Karakter"), ("location_tag", "Lokasyon"), ("style", "Stil"), ("timeOfDay", "Zaman"), ("cameraAngles", "Kamera Açıları")]:
                    if config.get(field):
                        filled.append(f"{label}: {config[field]}")
                    else:
                        missing.append(label)
                
                msg = f"✅ **'{name}'** preset'i başarıyla oluşturuldu!\n\n"
                if filled:
                    msg += f"📋 **İçerik:** {', '.join(filled)}\n"
                if missing:
                    msg += f"📝 **Eksik:** {', '.join(missing)} (sonradan eklenebilir)\n"
                msg += f"\n💡 Topluluk sekmesinden preset'inizi yayınlayabilir veya düzenleyebilirsiniz."
                
                return {"success": True, "plugin_id": str(plugin.id), "name": name, "message": msg, "_deterministic": True}
            
            elif action == "list":
                result = await db.execute(
                    select(Preset).where(Preset.session_id == session_id)
                )
                plugins = result.scalars().all()
                plugin_list = [{"id": str(p.id), "name": p.name, "description": p.description} for p in plugins]
                return {"success": True, "plugins": plugin_list, "count": len(plugin_list)}
            
            elif action == "delete":
                plugin_id = params.get("plugin_id")
                if not plugin_id:
                    return {"success": False, "error": "Plugin ID gerekli."}
                result = await db.execute(
                    select(Preset).where(Preset.id == uuid.UUID(plugin_id))
                )
                plugin = result.scalar_one_or_none()
                if plugin:
                    await db.delete(plugin)
                    await db.commit()
                    return {"success": True, "message": f"'{plugin.name}' plugin'i silindi."}
                return {"success": False, "error": "Plugin bulunamadı."}
            
            return {"success": False, "error": f"Bilinmeyen action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_system_state(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Sistemin mevcut durumunu getir."""
        try:
            entities = await entity_service.list_entities(db, session_id)
            assets = await asset_service.get_session_assets(db, session_id, limit=5) if params.get("include_assets", True) else []
            
            state = {
                "session_id": str(session_id),
                "entities": {"characters": [e.name for e in entities if e.entity_type == "character"],
                            "locations": [e.name for e in entities if e.entity_type == "location"]},
                "recent_assets": len(assets) if assets else 0
            }
            return {"success": True, "state": state, "message": f"{len(entities)} entity, {len(assets) if assets else 0} asset var."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _manage_wardrobe(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """Wardrobe (kıyafet) yönetimi."""
        try:
            action = params.get("action")
            name = params.get("name")
            
            if action == "add":
                if not name:
                    return {"success": False, "error": "Kıyafet adı gerekli."}
                return {"success": True, "message": f"'{name}' kıyafeti eklendi!"}
            
            elif action == "list":
                mock = [{"id": "1", "name": "Business Suit"}, {"id": "2", "name": "Casual Jeans"}]
                return {"success": True, "wardrobe": mock, "count": len(mock)}
            
            elif action == "remove":
                return {"success": True, "message": "Kıyafet silindi."}
            
            return {"success": False, "error": f"Bilinmeyen action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===============================
    # WEB ARAMA METODLARI
    # ===============================
    
    async def _search_images(self, params: dict) -> dict:
        """
        DuckDuckGo ile görsel arar.
        """
        try:
            from duckduckgo_search import DDGS
            
            query = params.get("query")
            num_results = params.get("num_results", 5)
            
            if not query:
                return {"success": False, "error": "Arama terimi gerekli."}
            
            print(f"=== SEARCH IMAGES ===")
            print(f"Query: {query}")
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.images(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "thumbnail": r.get("thumbnail", ""),
                        "image": r.get("image", ""),
                        "source": r.get("source", ""),
                        "url": r.get("url", "")
                    })
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "message": f"'{query}' için {len(results)} görsel bulundu."
            }
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _search_web(self, params: dict) -> dict:
        """
        DuckDuckGo ile metin araması yapar.
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            query = params.get("query")
            num_results = params.get("num_results", 5)
            region = params.get("region", "tr-tr")
            
            if not query:
                return {"success": False, "error": "Arama terimi gerekli."}
            
            print(f"=== SEARCH WEB ===")
            print(f"Query: {query}, Region: {region}")
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, region=region, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "url": r.get("href", "")
                    })
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "message": f"'{query}' için {len(results)} sonuç bulundu."
            }
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _search_videos(self, params: dict) -> dict:
        """
        DuckDuckGo ile video arar.
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            query = params.get("query")
            num_results = params.get("num_results", 5)
            
            if not query:
                return {"success": False, "error": "Arama terimi gerekli."}
            
            print(f"=== SEARCH VIDEOS ===")
            print(f"Query: {query}")
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.videos(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "description": r.get("description", ""),
                        "duration": r.get("duration", ""),
                        "publisher": r.get("publisher", ""),
                        "embed_url": r.get("embed_url", ""),
                        "url": r.get("content", "")
                    })
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "message": f"'{query}' için {len(results)} video bulundu."
            }
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _browse_url(self, params: dict) -> dict:
        """
        URL'ye gider ve sayfa içeriğini okur.
        """
        import httpx
        from bs4 import BeautifulSoup
        
        try:
            url = params.get("url")
            extract_images = params.get("extract_images", False)
            
            if not url:
                return {"success": False, "error": "URL gerekli."}
            
            print(f"=== BROWSE URL ===")
            print(f"URL: {url}")
            
            # Sayfayı indir
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"Sayfa yüklenemedi: {response.status_code}"}
                
                html = response.text
            
            # HTML'i parse et
            soup = BeautifulSoup(html, "lxml")
            
            # Script ve style taglarını kaldır
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Başlık
            title = soup.title.string if soup.title else "Başlık yok"
            
            # Meta açıklama
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")
            
            # Ana içerik - article veya main tag'ini ara
            main_content = soup.find("article") or soup.find("main") or soup.find("body")
            
            # Metni çıkar
            text = main_content.get_text(separator="\n", strip=True) if main_content else ""
            
            # Çok uzunsa kısalt
            if len(text) > 5000:
                text = text[:5000] + "...[kısaltıldı]"
            
            result = {
                "success": True,
                "url": url,
                "title": title,
                "description": meta_desc,
                "content": text,
                "content_length": len(text),
                "message": f"'{title}' sayfası okundu."
            }
            
            # Görselleri çıkar
            if extract_images:
                images = []
                for img in soup.find_all("img", src=True)[:10]:
                    src = img.get("src", "")
                    # Relative URL'leri absolute yap
                    if src.startswith("/"):
                        from urllib.parse import urljoin
                        src = urljoin(url, src)
                    if src.startswith("http"):
                        images.append({
                            "src": src,
                            "alt": img.get("alt", "")
                        })
                result["images"] = images
                result["image_count"] = len(images)
            
            return result
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _fetch_web_image(self, db: AsyncSession, session_id: uuid.UUID, params: dict) -> dict:
        """
        Web'den görsel indirir ve sisteme kaydeder.
        """
        import httpx
        import base64
        import os
        from datetime import datetime
        
        try:
            image_url = params.get("image_url")
            save_as_entity = params.get("save_as_entity", False)
            entity_name = params.get("entity_name")
            
            if not image_url:
                return {"success": False, "error": "Görsel URL'si gerekli."}
            
            print(f"=== FETCH WEB IMAGE ===")
            print(f"URL: {image_url[:100]}...")
            
            # Görseli indir
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(
                    image_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"Görsel indirilemedi: {response.status_code}"}
                
                # Content type kontrolü
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    return {"success": False, "error": f"Geçersiz içerik tipi: {content_type}"}
                
                image_data = response.content
            
            # Dosya uzantısını belirle
            ext = "jpg"
            if "png" in content_type:
                ext = "png"
            elif "gif" in content_type:
                ext = "gif"
            elif "webp" in content_type:
                ext = "webp"
            
            # Dosyayı kaydet
            upload_dir = settings.STORAGE_PATH
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join(upload_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(image_data)
            
            # URL oluştur (local için)
            saved_url = f"http://localhost:8000/uploads/{filename}"
            
            result = {
                "success": True,
                "url": saved_url,
                "original_url": image_url,
                "filename": filename,
                "size_bytes": len(image_data),
                "message": f"Görsel başarıyla indirildi: {filename}"
            }
            
            # Entity olarak kaydet
            if save_as_entity and entity_name:
                try:
                    # Entity oluştur veya güncelle
                    user_id = await get_user_id_from_session(db, session_id)
                    entity = await entity_service.create_entity(
                        db=db,
                        user_id=user_id,
                        entity_type="character",
                        name=entity_name,
                        description=f"Web'den indirilen görsel: {image_url[:50]}...",
                        reference_image_url=saved_url,
                        session_id=session_id
                    )
                    result["entity_id"] = str(entity.id)
                    result["entity_tag"] = f"@{entity_name.lower().replace(' ', '_')}"
                    result["message"] += f" Entity olarak kaydedildi: @{entity_name}"
                except ValueError as ve:
                    # Duplicate entity - user'a bildir ama görsel yine de kaydedildi
                    result["entity_warning"] = str(ve)
                    result["message"] += f" (⚠️ Entity kaydedilemedi: zaten mevcut)"
            
            # Asset olarak kaydet
            try:
                from app.models.models import Asset
                new_asset = Asset(
                    session_id=session_id,
                    asset_type="image",
                    url=saved_url,
                    prompt=f"Web'den indirildi: {image_url[:100]}",
                    model_used="web_fetch"
                )
                db.add(new_asset)
                await db.commit()
                result["asset_id"] = str(new_asset.id)
            except Exception as e:
                print(f"Asset kayıt hatası: {e}")
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}


    async def _generate_grid(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict,
        resolved_entities: list = None
    ) -> dict:
        """
        3x3 Grid oluşturma.
        
        Özellikler:
        - 9 kamera açısı (angles) veya 9 hikaye paneli (storyboard)
        - @karakter referansı ile otomatik görsel kullanımı
        - Panel extraction ve upscale
        """
        import httpx
        
        try:
            image_url = params.get("image_url")
            mode = params.get("mode", "angles")
            aspect_ratio = params.get("aspect_ratio", "16:9")
            extract_panel = params.get("extract_panel")
            scale = params.get("scale", 2)
            custom_prompt = params.get("custom_prompt")
            
            # Entity referansından görsel al
            if resolved_entities:
                for entity in resolved_entities:
                    if hasattr(entity, 'reference_image_url') and entity.reference_image_url:
                        if not image_url:
                            image_url = entity.reference_image_url
                        break
            
            if not image_url:
                return {"success": False, "error": "Görsel URL'si gerekli. Bir görsel gönder veya @karakter kullan."}
            
            # Grid prompt oluştur
            if custom_prompt:
                grid_prompt = custom_prompt
            else:
                grid_prompt = self._build_grid_prompt(mode)
            
            print(f"=== GRID GENERATION (Agent) ===")
            print(f"Mode: {mode}, Aspect: {aspect_ratio}")
            print(f"Image URL: {image_url[:100]}...")
            
            # Grid oluştur (Nano Banana Pro)
            grid_image_url = None
            
            request_body = {
                "prompt": grid_prompt,
                "image_urls": [image_url],
                "num_images": 1,
                "aspect_ratio": aspect_ratio,
                "output_format": "png",
                "resolution": "2K",
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    response = await client.post(
                        "https://fal.run/fal-ai/nano-banana-pro/edit",
                        headers={
                            "Authorization": f"Key {self.fal_plugin.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("images") and len(data["images"]) > 0:
                            grid_image_url = data["images"][0]["url"]
                except Exception as e:
                    print(f"Nano Banana Pro failed: {e}")
            
            # Fallback: FLUX dev
            if not grid_image_url:
                if aspect_ratio == "16:9":
                    image_size = {"width": 1920, "height": 1080}
                elif aspect_ratio == "9:16":
                    image_size = {"width": 1080, "height": 1920}
                else:
                    image_size = {"width": 1024, "height": 1024}
                
                flux_body = {
                    "prompt": grid_prompt,
                    "image_url": image_url,
                    "strength": 0.75,
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "image_size": image_size,
                    "num_images": 1,
                    "enable_safety_checker": False,
                    "output_format": "png",
                }
                
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        "https://fal.run/fal-ai/flux/dev/image-to-image",
                        headers={
                            "Authorization": f"Key {self.fal_plugin.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=flux_body
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("images") and len(data["images"]) > 0:
                            grid_image_url = data["images"][0]["url"]
                    else:
                        return {"success": False, "error": f"Grid oluşturulamadı: {response.text}"}
            
            if not grid_image_url:
                return {"success": False, "error": "Grid oluşturulamadı."}
            
            result = {
                "success": True,
                "grid_image_url": grid_image_url,
                "mode": mode,
                "aspect_ratio": aspect_ratio,
                "message": f"3x3 {mode} grid oluşturuldu!"
            }
            
            # Panel extraction istendi mi?
            if extract_panel and 1 <= extract_panel <= 9:
                # Panel extraction için grid görselini indir ve crop et
                # Bu client-side yapılıyor, URL'yi döndür
                result["extract_panel"] = extract_panel
                result["scale"] = scale
                result["message"] += f" Panel #{extract_panel} seçildi ({scale}x upscale için hazır)."
            
            # Asset kaydet
            try:
                from app.models.models import Asset
                new_asset = Asset(
                    session_id=session_id,
                    asset_type="image",
                    url=grid_image_url,
                    prompt=f"3x3 {mode} grid",
                    model_used="nano-banana-pro"
                )
                db.add(new_asset)
                await db.commit()
                result["asset_id"] = str(new_asset.id)
            except Exception as e:
                print(f"Asset kayıt hatası: {e}")
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _build_grid_prompt(self, mode: str) -> str:
        """Grid için prompt oluştur."""
        if mode == "angles":
            return """Create a seamless 3x3 grid of 9 cinematic camera angles showing the same subject.

GRID REQUIREMENTS:
- NO white borders or gaps between panels
- Each panel edge-to-edge, flowing into the next
- The SAME EXACT person in ALL 9 panels

9 CAMERA ANGLES:
1. WIDE SHOT - full body, environment visible
2. MEDIUM WIDE - head to knees
3. MEDIUM SHOT - waist up
4. MEDIUM CLOSE-UP - chest and head
5. CLOSE-UP - face fills frame
6. THREE-QUARTER VIEW - face angled 45°
7. LOW ANGLE - heroic
8. HIGH ANGLE - looking down
9. PROFILE - side view

CRITICAL: Face must be clearly visible in ALL panels. Cinematic, photorealistic."""

        elif mode == "storyboard":
            return """Create a seamless 3x3 grid of 9 sequential storyboard panels.

GRID REQUIREMENTS:
- NO white borders or gaps between panels
- Each panel edge-to-edge, flowing into the next
- The SAME EXACT person in ALL 9 panels

9 STORY BEATS:
1. ESTABLISHING - calm moment, wide shot
2. TENSION - notices something
3. REACTION - close-up, concern
4. ACTION BEGINS - starts moving
5. PEAK ACTION - dynamic movement
6. INTENSITY - extreme close-up
7. CLIMAX - dramatic action
8. RESOLUTION - conflict ending
9. CONCLUSION - final emotion

CRITICAL: Same character throughout. Cinematic storyboard quality."""

        else:
            return "Create a seamless 3x3 grid showing 9 variations. NO borders, NO gaps. Photorealistic, cinematic."
    
    async def _use_grid_panel(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        Grid'den belirli bir paneli seç ve işlem yap.
        
        Panel numarası 1-9 arası (3x3 grid):
        | 1 | 2 | 3 |
        | 4 | 5 | 6 |
        | 7 | 8 | 9 |
        """
        try:
            panel_number = params.get("panel_number", 1)
            action = params.get("action", "video")
            video_prompt = params.get("video_prompt", "")
            edit_prompt = params.get("edit_prompt", "")
            
            if not 1 <= panel_number <= 9:
                return {"success": False, "error": "Panel numarası 1-9 arası olmalı."}
            
            # Son grid asset'ini bul
            from app.models.models import GeneratedAsset
            from sqlalchemy import select
            
            result = await db.execute(
                select(GeneratedAsset)
                .where(
                    GeneratedAsset.session_id == session_id,
                    GeneratedAsset.prompt.ilike("%grid%")
                )
                .order_by(GeneratedAsset.created_at.desc())
                .limit(1)
            )
            grid_asset = result.scalar_one_or_none()
            
            if not grid_asset:
                return {"success": False, "error": "Önce bir grid oluşturmalısın. 'Grid yap' komutunu dene."}
            
            grid_url = grid_asset.url
            
            # Panel koordinatlarını hesapla (3x3 grid)
            row = (panel_number - 1) // 3
            col = (panel_number - 1) % 3
            
            # Grid görselinden panel crop için frontend'e bilgi gönder
            # veya server-side crop yap
            
            if action == "video":
                # Panel'i video'ya çevir
                prompt = video_prompt or f"Cinematic motion, subtle movement, panel {panel_number} comes alive"
                
                result = await self._generate_video(
                    db, session_id,
                    {
                        "prompt": prompt,
                        "image_url": grid_url,  # Grid'in tamamını gönderiyoruz, crop frontend'de yapılacak
                        "duration": "5"
                    }
                )
                
                if result.get("success"):
                    result["message"] = f"Panel #{panel_number}'den video oluşturuldu!"
                    result["source_panel"] = panel_number
                    result["grid_url"] = grid_url
                return result
                
            elif action == "upscale":
                # Panel'i upscale et
                result = await self._upscale_image({
                    "image_url": grid_url,
                    "scale": 2
                })
                if result.get("success"):
                    result["message"] = f"Panel #{panel_number} 2x büyütüldü!"
                    result["source_panel"] = panel_number
                return result
                
            elif action == "edit":
                # Panel'i düzenle
                if not edit_prompt:
                    return {"success": False, "error": "Düzenleme için edit_prompt gerekli."}
                
                result = await self._edit_image(db, session_id, {
                    "image_url": grid_url,
                    "prompt": edit_prompt
                })
                if result.get("success"):
                    result["message"] = f"Panel #{panel_number} düzenlendi!"
                    result["source_panel"] = panel_number
                return result
                
            elif action == "download":
                return {
                    "success": True,
                    "message": f"Panel #{panel_number} indirme için hazır.",
                    "grid_url": grid_url,
                    "panel_number": panel_number,
                    "panel_position": {"row": row, "col": col},
                    "instruction": "Frontend'de bu paneli kırpıp indir."
                }
            
            else:
                return {"success": False, "error": f"Bilinmeyen action: {action}"}
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    # ===============================
    # MARKA YÖNETİM METODLARI
    # ===============================
    
    async def _create_brand(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        Marka entity'si oluştur.
        
        Kullanıcı manuel olarak marka bilgilerini verdiğinde veya
        research_brand sonucu kaydedildiğinde kullanılır.
        """
        try:
            name = params.get("name")
            description = params.get("description", "")
            logo_url = params.get("logo_url")
            attributes = params.get("attributes", {})
            
            # Session'dan user_id al
            user_id = await get_user_id_from_session(db, session_id)
            
            # Entity service ile brand entity oluştur
            entity = await entity_service.create_entity(
                db=db,
                user_id=user_id,
                entity_type="brand",
                name=name,
                description=description,
                attributes=attributes,
                reference_image_url=logo_url,
                session_id=session_id
            )
            
            return {
                "success": True,
                "message": f"✅ Marka '{name}' başarıyla kaydedildi! Tag: {entity.tag}",
                "entity": {
                    "id": str(entity.id),
                    "tag": entity.tag,
                    "name": entity.name,
                    "entity_type": "brand"
                },
                "brand": {
                    "id": str(entity.id),
                    "tag": entity.tag,
                    "name": entity.name,
                    "description": entity.description,
                    "logo_url": logo_url,
                    "colors": attributes.get("colors", {}),
                    "tagline": attributes.get("tagline", ""),
                    "industry": attributes.get("industry", ""),
                    "tone": attributes.get("tone", "")
                }
            }
        
        except ValueError as ve:
            # Duplicate marka hatası
            return {
                "success": False,
                "error": str(ve),
                "duplicate": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Marka oluşturulamadı: {str(e)}"
            }
    
    async def _research_brand(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        AKILLI Web'den marka araştırması.
        
        İş Akışı:
        1. DuckDuckGo ile marka bilgilerini ara
        2. Logo görselini ara ve indir
        3. GPT-4o Vision ile logo analizi yap → RENKLER ÇIKAR
        4. Sosyal medya hesaplarını bul
        5. (Opsiyonel) Marka olarak kaydet
        """
        try:
            brand_name = params.get("brand_name")
            research_depth = params.get("research_depth", "detailed")
            should_save = params.get("save", False)
            
            # Sonuç tutacak
            brand_info = {
                "name": brand_name,
                "description": "",
                "website": None,
                "colors": {},
                "tagline": "",
                "industry": "",
                "tone": "",
                "social_media": {},
                "logo_url": None,
                "research_notes": []
            }
            
            from duckduckgo_search import DDGS
            import httpx
            import base64
            
            with DDGS() as ddgs:
                # 1. Temel bilgi araması
                search_results = list(ddgs.text(
                    f"{brand_name} brand company official",
                    max_results=5
                ))
                
                if search_results:
                    brand_info["description"] = search_results[0].get("body", "")
                    brand_info["website"] = search_results[0].get("href", "")
                    brand_info["research_notes"].append(f"Web aramasından {len(search_results)} sonuç bulundu")
                
                # 2. 🎨 LOGO GÖRSEL ARAŞTIRMASI - KRİTİK!
                print(f"🔍 {brand_name} logosu aranıyor...")
                logo_found = False
                
                try:
                    # Logo görsellerini ara
                    image_results = list(ddgs.images(
                        f"{brand_name} logo official transparent",
                        max_results=5
                    ))
                    
                    if image_results:
                        brand_info["research_notes"].append(f"Logo aramasında {len(image_results)} görsel bulundu")
                        
                        # En iyi logo adayını bul
                        for img_result in image_results:
                            image_url = img_result.get("image")
                            if not image_url:
                                continue
                            
                            print(f"   → Logo adayı: {image_url[:80]}...")
                            
                            try:
                                # Logoyu indir
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    response = await client.get(image_url, follow_redirects=True)
                                    if response.status_code == 200:
                                        image_data = response.content
                                        
                                        # Base64'e çevir
                                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                                        
                                        # Content type belirle
                                        content_type = response.headers.get("content-type", "image/png")
                                        if "jpeg" in content_type or "jpg" in content_type:
                                            media_type = "image/jpeg"
                                        elif "png" in content_type:
                                            media_type = "image/png"
                                        elif "webp" in content_type:
                                            media_type = "image/webp"
                                        else:
                                            media_type = "image/png"
                                        
                                        data_url = f"data:{media_type};base64,{image_base64}"
                                        
                                        # 3. 🧠 GPT-4o VISION İLE RENK ANALİZİ!
                                        print(f"   🎨 Logo analiz ediliyor (GPT-4o Vision)...")
                                        
                                        analysis_response = self.client.chat.completions.create(
                                            model="gpt-4o",
                                            max_tokens=500,
                                            messages=[
                                                {
                                                    "role": "system",
                                                    "content": "Sen bir marka renk analisti sin. Verilen logo görselini analiz et ve marka renklerini çıkart. SADECE JSON formatında yanıt ver, başka hiçbir şey yazma."
                                                },
                                                {
                                                    "role": "user",
                                                    "content": [
                                                        {
                                                            "type": "image_url",
                                                            "image_url": {"url": data_url, "detail": "high"}
                                                        },
                                                        {
                                                            "type": "text",
                                                            "text": f"""Bu {brand_name} markasının logosu. Analiz et ve şu bilgileri JSON olarak döndür:

{{
    "primary_color": "#HEX - ana renk",
    "secondary_color": "#HEX - ikincil renk (varsa)",
    "accent_colors": ["#HEX", "#HEX"] veya [],
    "color_names": {{"primary": "renk adı türkçe", "secondary": "renk adı"}},
    "logo_style": "minimalist/ornate/text-based/icon-based/combination",
    "dominant_mood": "profesyonel/eğlenceli/lüks/enerji/güvenilir/yaratıcı"
}}

SADECE JSON döndür, başka açıklama yazma."""
                                                        }
                                                    ]
                                                }
                                            ]
                                        )
                                        
                                        analysis_text = analysis_response.choices[0].message.content.strip()
                                        
                                        # JSON'u parse et
                                        import json
                                        import re
                                        
                                        # JSON bloğunu bul
                                        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
                                        if json_match:
                                            try:
                                                color_data = json.loads(json_match.group())
                                                brand_info["colors"] = color_data
                                                brand_info["logo_url"] = image_url
                                                logo_found = True
                                                
                                                primary = color_data.get("primary_color", "")
                                                color_name = color_data.get("color_names", {}).get("primary", "")
                                                brand_info["research_notes"].append(f"✅ Logo analizi başarılı! Ana renk: {color_name} ({primary})")
                                                print(f"   ✅ Renkler bulundu: {primary} ({color_name})")
                                                break  # İlk başarılı logoda dur
                                            except json.JSONDecodeError:
                                                print(f"   ⚠️ JSON parse hatası")
                                                continue
                                        
                            except Exception as img_error:
                                print(f"   ⚠️ Logo indirme/analiz hatası: {img_error}")
                                continue
                    else:
                        brand_info["research_notes"].append("Logo görseli bulunamadı")
                        
                except Exception as logo_error:
                    print(f"⚠️ Logo araştırma hatası: {logo_error}")
                    brand_info["research_notes"].append(f"Logo araştırma hatası: {str(logo_error)}")
                
                # 4. Slogan araması
                tagline_results = list(ddgs.text(
                    f"{brand_name} slogan tagline",
                    max_results=3
                ))
                
                for result in tagline_results:
                    body = result.get("body", "")
                    title = result.get("title", "")
                    if any(word in body.lower() for word in ["slogan", "tagline", "motto"]):
                        # Slogan'ı çıkarmaya çalış
                        brand_info["tagline"] = body[:150]
                        brand_info["research_notes"].append(f"Slogan bulundu")
                        break
                
                # 5. Sosyal medya araştırması
                if research_depth in ["detailed", "comprehensive"]:
                    # Instagram
                    insta_results = list(ddgs.text(
                        f"{brand_name} official instagram",
                        max_results=3
                    ))
                    for result in insta_results:
                        href = result.get("href", "")
                        if "instagram.com" in href:
                            brand_info["social_media"]["instagram"] = href
                            break
                    
                    # Twitter/X
                    twitter_results = list(ddgs.text(
                        f"{brand_name} official twitter",
                        max_results=3
                    ))
                    for result in twitter_results:
                        href = result.get("href", "")
                        if "twitter.com" in href or "x.com" in href:
                            brand_info["social_media"]["twitter"] = href
                            break
                    
                    # LinkedIn
                    linkedin_results = list(ddgs.text(
                        f"{brand_name} official linkedin company",
                        max_results=3
                    ))
                    for result in linkedin_results:
                        href = result.get("href", "")
                        if "linkedin.com" in href:
                            brand_info["social_media"]["linkedin"] = href
                            break
                    
                    brand_info["research_notes"].append(f"Sosyal medya: {len(brand_info['social_media'])} hesap bulundu")
            
            # Sonuç özeti
            colors_summary = ""
            if brand_info["colors"]:
                primary = brand_info["colors"].get("primary_color", "")
                color_name = brand_info["colors"].get("color_names", {}).get("primary", "")
                if primary:
                    colors_summary = f"\n🎨 Ana Renk: {color_name} ({primary})"
                    if brand_info["colors"].get("secondary_color"):
                        sec = brand_info["colors"]["secondary_color"]
                        sec_name = brand_info["colors"].get("color_names", {}).get("secondary", "")
                        colors_summary += f"\n🎨 İkincil: {sec_name} ({sec})"
            
            result = {
                "success": True,
                "brand_info": brand_info,
                "research_depth": research_depth,
                "logo_analyzed": logo_found,
                "message": f"🔍 {brand_name} hakkında DETAYLI araştırma tamamlandı.\n"
                          f"Website: {brand_info['website'] or 'Bulunamadı'}"
                          f"{colors_summary}"
                          f"\nSosyal Medya: {len(brand_info['social_media'])} hesap"
                          f"\n📝 {len(brand_info['research_notes'])} araştırma notu"
            }
            
            # Kaydetme istendi mi?
            if should_save:
                save_result = await self._create_brand(
                    db=db,
                    session_id=session_id,
                    params={
                        "name": brand_name,
                        "description": brand_info["description"],
                        "logo_url": brand_info["logo_url"],
                        "attributes": {
                            "colors": brand_info["colors"],
                            "tagline": brand_info["tagline"],
                            "industry": brand_info["industry"],
                            "tone": brand_info["colors"].get("dominant_mood", ""),
                            "social_media": brand_info["social_media"],
                            "website": brand_info["website"]
                        }
                    }
                )
                
                if save_result.get("success"):
                    result["saved"] = True
                    result["brand_tag"] = save_result.get("brand", {}).get("tag")
                    result["message"] += f"\n✅ Marka kaydedildi: {result['brand_tag']}"
            
            return result
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Marka araştırması başarısız: {str(e)}"
            }
    
    async def _semantic_search(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        params: dict
    ) -> dict:
        """
        Pinecone ile semantik entity araması.
        Doğal dil sorgusu ile benzer karakterleri, mekanları veya markaları bulur.
        """
        query = params.get("query", "")
        entity_type = params.get("entity_type", "all")
        limit = params.get("limit", 5)
        
        if not query:
            return {"success": False, "error": "Arama sorgusu gerekli"}
        
        # Pinecone devre dışıysa, basit veritabanı araması yap
        if not settings.USE_PINECONE:
            # Fallback: basit LIKE araması
            user_id = await get_user_id_from_session(db, session_id)
            entities = await entity_service.list_entities(
                db, user_id,
                entity_type=entity_type if entity_type != "all" else None
            )
            
            # Basit kelime eşleştirme
            query_lower = query.lower()
            matches = []
            for entity in entities:
                search_text = f"{entity.name} {entity.description or ''} {json.dumps(entity.attributes or {})}"
                if query_lower in search_text.lower():
                    matches.append({
                        "tag": entity.tag,
                        "name": entity.name,
                        "type": entity.entity_type,
                        "description": entity.description[:100] if entity.description else "",
                        "score": 0.5  # Fallback için sabit skor
                    })
            
            return {
                "success": True,
                "query": query,
                "results": matches[:limit],
                "total": len(matches),
                "method": "database_fallback"
            }
        
        # Pinecone ile semantik arama
        try:
            from app.services.embeddings.pinecone_service import pinecone_service
            
            search_type = None if entity_type == "all" else entity_type
            results = await pinecone_service.search_similar(
                query=query,
                entity_type=search_type,
                top_k=limit
            )
            
            matches = []
            for result in results:
                matches.append({
                    "id": result["id"],
                    "tag": result["metadata"].get("tag", ""),
                    "name": result["metadata"].get("name", ""),
                    "type": result["metadata"].get("entity_type", "unknown"),
                    "description": result["metadata"].get("description", "")[:100],
                    "score": round(result["score"], 3)
                })
            
            return {
                "success": True,
                "query": query,
                "results": matches,
                "total": len(matches),
                "method": "pinecone_semantic"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Semantik arama hatası: {str(e)}"
            }
    
    async def _get_library_docs(self, params: dict) -> dict:
        """
        Context7 MCP kullanarak kütüphane dokümantasyonu çek.
        Güncel API bilgilerini getirerek LLM'lerin eski bilgi kullanmasını engeller.
        """
        library_name = params.get("library_name", "")
        query = params.get("query")  # Opsiyonel: spesifik sorgu
        tokens = params.get("tokens", 5000)
        
        if not library_name:
            return {"success": False, "error": "Kütüphane adı gerekli"}
        
        try:
            result = await context7_service.get_library_docs(
                library_name=library_name,
                query=query,
                tokens=tokens
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "library": result.get("library"),
                    "title": result.get("title", library_name),
                    "content": result.get("content", ""),
                    "description": result.get("description", ""),
                    "version": result.get("version"),
                    "source_url": result.get("source_url"),
                    "message": f"'{library_name}' dokümantasyonu başarıyla çekildi"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Dokümantasyon çekilemedi"),
                    "suggestion": result.get("suggestion")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Context7 hatası: {str(e)}"
            }


# Singleton instance
agent = AgentOrchestrator()
