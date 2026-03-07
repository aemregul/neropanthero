"""
Conversation Memory Service — Kullanıcı Seviyesinde Hafıza.

Tek asistan, farklı projeler modeli:
- Her sohbet sonunda özet çıkar → user hafızasına kaydet
- Yeni sohbette geçmiş özetleri context'e ekle
- Başarılı prompt'ları hatırla (Self-Learning)
- Kullanıcı tercihlerini öğren
"""
import uuid
from typing import Dict, Any, List
from datetime import datetime

from openai import AsyncOpenAI
from app.core.config import settings
from app.services.memory_hygiene import (
    ALLOWED_STYLE_PREFERENCE_KEYS,
    has_conflicting_request_constraints,
    is_stable_memory_fact,
    sanitize_memory_text,
    tokenize_memory_text,
)


class ConversationMemoryService:
    """Kullanıcı seviyesinde hafıza — projeler arası hatırlama."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    # ===============================
    # SOHBET ÖZETLEMESİ
    # ===============================
    
    async def summarize_conversation(
        self,
        messages: List[Dict[str, str]],
        session_title: str = ""
    ) -> str:
        """
        Sohbet geçmişini özetle.
        Her sohbet kapandığında çağrılır.
        """
        if not messages or len(messages) < 2:
            return ""
        
        # Son 30 mesajı al
        recent = messages[-30:]
        conversation_text = "\n".join([
            f"{'Kullanıcı' if m['role'] == 'user' else 'Asistan'}: {m['content'][:200]}"
            for m in recent
        ])
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Hızlı ve ucuz
                messages=[
                    {
                        "role": "system",
                        "content": """Bir sohbet özetleme sistemisİn. Aşağıdaki sohbeti ÇOK KISA özetle (max 3 cümle):
- Ne yapıldı?
- Hangi entity'ler/markalar kullanıldı?
- Kullanıcı neyi beğendi/beğenmedi?
- Hangi stil/format tercih edildi?

Türkçe yaz. Sadece özet, başka bir şey yazma."""
                    },
                    {
                        "role": "user",
                        "content": f"Proje: {session_title}\n\nSohbet:\n{conversation_text}"
                    }
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"📝 Sohbet özeti oluşturuldu: {summary[:80]}...")
            return summary
            
        except Exception as e:
            print(f"⚠️ Özet oluşturma hatası: {e}")
            return ""
    
    async def save_conversation_summary(
        self,
        db,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        summary: str
    ):
        """Özeti Redis + DB'ye kaydet."""
        from app.core.cache import cache
        
        # Redis'e kaydet (hızlı erişim)
        memory_key = f"user_memory:{user_id}"
        existing = await cache.get_json(memory_key) or {
            "summaries": [],
            "preferences": {},
            "successful_prompts": [],
            "style_preferences": {}
        }
        
        existing["summaries"].append({
            "session_id": str(session_id),
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Son 20 özeti tut
        if len(existing["summaries"]) > 20:
            existing["summaries"] = existing["summaries"][-20:]
        
        await cache.set_json(memory_key, existing, ttl=604800)  # 7 gün
        print(f"💾 Hafıza kaydedildi: user={str(user_id)[:8]}...")
    
    # ===============================
    # KULLANICI HAFIZASı YÜKLEME
    # ===============================
    
    async def get_user_memory(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Kullanıcının tüm hafızasını getir."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key)
        
        if not memory:
            return {
                "summaries": [],
                "preferences": {},
                "successful_prompts": [],
                "style_preferences": {},
                "core_memories": []
            }
        
        return memory
    
    async def build_memory_context(self, user_id: uuid.UUID) -> str:
        """
        Geçmiş hafızayı system prompt'a eklenecek context'e dönüştür.
        Agent bu bilgiyle kullanıcıyı "tanır".
        """
        memory = await self.get_user_memory(user_id)
        
        parts = []
        
        # Core Memories (Kullanıcı Gerçekleri)
        if memory.get("core_memories"):
            core_lines = []
            for item in memory["core_memories"][-10:]:
                fact = item.get("fact", "")
                category = item.get("category", "general")
                if not is_stable_memory_fact(category, fact):
                    continue
                sanitized_fact = sanitize_memory_text(fact)
                if sanitized_fact:
                    core_lines.append(f"- {sanitized_fact} (Kategori: {category})")

            if core_lines:
                parts.append(
                    "👤 KULLANICI HAKKINDA BİLDİKLERİN (CORE MEMORY):\n" + "\n".join(core_lines)
                )
        
        # Geçmiş sohbet özetleri
        if memory.get("summaries"):
            summary_lines = []
            for summary in memory["summaries"][-5:]:
                sanitized_summary = sanitize_memory_text(summary.get("summary", ""))
                if sanitized_summary:
                    summary_lines.append(f"- {sanitized_summary}")

            if summary_lines:
                parts.append(f"📋 SON PROJELER:\n{'\n'.join(summary_lines)}")
        
        # Tercihler
        if memory.get("preferences"):
            pref_lines = []
            for key, value in memory["preferences"].items():
                fact = f"{key}: {value}"
                if not is_stable_memory_fact("general", fact):
                    continue
                sanitized_fact = sanitize_memory_text(fact)
                if sanitized_fact:
                    pref_lines.append(sanitized_fact)

            if pref_lines:
                parts.append(f"⚙️ TERCİHLER: {', '.join(pref_lines)}")
        
        # Stil tercihleri
        if memory.get("style_preferences"):
            style_lines = []
            for key, value in memory["style_preferences"].items():
                if key not in ALLOWED_STYLE_PREFERENCE_KEYS:
                    continue
                sanitized_value = sanitize_memory_text(str(value))
                if sanitized_value:
                    style_lines.append(f"{key}: {sanitized_value}")

            if style_lines:
                parts.append(f"🎨 STİL: {', '.join(style_lines)}")
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)
    
    # ===============================
    # SELF-LEARNING: BAŞARILI PROMPT'LAR
    # ===============================
    
    async def save_successful_prompt(
        self,
        user_id: uuid.UUID,
        prompt: str,
        result_url: str,
        score: int,
        asset_type: str = "image"
    ):
        """Kullanıcı beğendiğinde prompt'u hafızaya kaydet."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key) or {
            "summaries": [],
            "preferences": {},
            "successful_prompts": [],
            "style_preferences": {}
        }
        
        memory["successful_prompts"].append({
            "prompt": prompt,
            "memory_prompt": sanitize_memory_text(prompt),
            "result_url": result_url,
            "score": score,
            "asset_type": asset_type,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Son 50 başarılı prompt
        if len(memory["successful_prompts"]) > 50:
            memory["successful_prompts"] = memory["successful_prompts"][-50:]
        
        await cache.set_json(memory_key, memory, ttl=604800)
        print(f"⭐ Başarılı prompt kaydedildi: '{prompt[:50]}...' (skor: {score})")
    
    async def find_similar_prompts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Geçmiş başarılı prompt'lardan benzerleri bul."""
        memory = await self.get_user_memory(user_id)
        prompts = memory.get("successful_prompts", [])
        
        if not prompts:
            return []
        
        query_words = tokenize_memory_text(query)
        if not query_words:
            return []

        scored = []
        
        for p in prompts:
            raw_prompt = p.get("prompt", "")
            if has_conflicting_request_constraints(query, raw_prompt):
                continue

            memory_prompt = p.get("memory_prompt") or sanitize_memory_text(raw_prompt)
            if not memory_prompt:
                continue

            prompt_words = tokenize_memory_text(memory_prompt)
            overlap = len(query_words & prompt_words)
            if overlap > 0:
                enriched = dict(p)
                enriched["memory_prompt"] = memory_prompt
                scored.append((overlap, p.get("score", 0), enriched))
        
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in scored[:limit]]
    
    # ===============================
    # TERCİH ÖĞRENME
    # ===============================
    
    async def update_preferences(
        self,
        user_id: uuid.UUID,
        key: str,
        value: str
    ):
        """Kullanıcı tercihini güncelle."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key) or {
            "summaries": [],
            "preferences": {},
            "successful_prompts": [],
            "style_preferences": {}
        }
        
        fact = f"{key}: {value}"
        if not is_stable_memory_fact("general", fact):
            return

        memory["preferences"][key] = sanitize_memory_text(str(value))
        await cache.set_json(memory_key, memory, ttl=604800)
    
    async def update_style_preference(
        self,
        user_id: uuid.UUID,
        style_key: str,
        style_value: str
    ):
        """Stil tercihini kaydet."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key) or {
            "summaries": [],
            "preferences": {},
            "successful_prompts": [],
            "style_preferences": {}
        }
        
        if style_key not in ALLOWED_STYLE_PREFERENCE_KEYS:
            return

        sanitized_value = sanitize_memory_text(str(style_value))
        if not sanitized_value:
            return

        memory["style_preferences"][style_key] = sanitized_value
        await cache.set_json(memory_key, memory, ttl=604800)

    # ===============================
    # CORE MEMORY (ÇEKİRDEK HAFIZA)
    # ===============================
    
    async def save_core_memory(
        self,
        user_id: uuid.UUID,
        category: str,
        fact: str
    ):
        """Kullanıcının temel bir özelliğini veya kuralını kalıcı hafızaya kaydet."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key) or {
            "summaries": [],
            "preferences": {},
            "successful_prompts": [],
            "style_preferences": {},
            "core_memories": []
        }
        
        if not is_stable_memory_fact(category, fact):
            return

        if "core_memories" not in memory:
            memory["core_memories"] = []

        sanitized_fact = sanitize_memory_text(fact)
        if not sanitized_fact:
            return

        memory["core_memories"].append({
            "category": category,
            "fact": sanitized_fact,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        await cache.set_json(memory_key, memory, ttl=604800)
        print(f"🧠 Core memory eklendi ({category}): {fact[:50]}...")

    async def delete_core_memory(self, user_id: uuid.UUID, fact_query: str) -> bool:
        """Belirli bir cümleye veya içeriğe uyan hafızayı sil."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key)
        
        if not memory or "core_memories" not in memory:
            return False
            
        initial_length = len(memory["core_memories"])
        
        # Eğer fact_query tam eşleşiyorsa veya içeriyorsa sil (case-insensitive)
        memory["core_memories"] = [
            m for m in memory["core_memories"]
            if fact_query.lower() not in m["fact"].lower()
        ]
        
        if len(memory["core_memories"]) < initial_length:
            await cache.set_json(memory_key, memory, ttl=604800)
            print(f"🗑️ Core memory silindi: '{fact_query}'")
            return True
            
        return False
        
    async def clear_core_memories(self, user_id: uuid.UUID):
        """Kullanıcının tüm çekirdek hafızasını temizle."""
        from app.core.cache import cache
        
        memory_key = f"user_memory:{user_id}"
        memory = await cache.get_json(memory_key)
        
        if memory and "core_memories" in memory:
            memory["core_memories"] = []
            await cache.set_json(memory_key, memory, ttl=604800)
            print("🧹 Tüm core memory temizlendi.")

# Singleton
conversation_memory = ConversationMemoryService()
