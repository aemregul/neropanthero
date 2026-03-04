"""
Campaign Planner Service — Phase 22: Full Autonomous Studio Orchestration

GPT-4o ile kullanıcının üst düzey hedefinden detaylı bir üretim planı çıkarır
ve planı paralel/sıralı olarak yürütür.

Örnek:
  goal = "Nike yaz kampanyası — 5 Instagram post, 2 story videosu"
  → plan: [{type: image, format: post, prompt: ...}, {type: video, ...}, ...]
  → execute: paralel üretim + sonuç toplama
"""
import json
import asyncio
import uuid
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings


PLAN_SYSTEM_PROMPT = """Sen profesyonel bir yaratıcı direktörsün. Kullanıcının üst düzey hedefini alıp detaylı bir üretim planı oluşturuyorsun.

KURALLAR:
1. Her task (görev) bağımsız çalışabilmeli (mümkün olduğunca paralel).
2. Prompt'lar İNGİLİZCE ve SON DERECE DETAYLI olmalı (composition, lighting, colors, mood). Metin yazarlığı (copywriting) görevleri için marka diline uygun brief'ler hazırla.
3. Format→aspect_ratio eşleştirmesi: post=1:1, story/reel=9:16, cover/banner=16:9, thumbnail=16:9.
4. Varyasyonlar oluştur — aynı promptun farklı açılmalarını yap (renk, kompozisyon, mood farkları).
5. Marka bilgisi varsa HER prompt'a entegre et (renkler, ton, slogan).
6. Video görevlerinde uygun model öner (kling=genel, veo=sinematik, sora2=hikaye, hailuo=kısa clip).
7. Görsel görevlerinde uygun model öner (nano_banana=fotorealist, gpt_image=illustrasyon/anime, flux2=tipografi, recraft=logo/vektör).
8. Metin görevleri (text) için reklam metni, sosyal medya açıklaması (caption) gibi hedefleri belirt.

ÇIKTI FORMATI (JSON):
{
  "plan_title": "Kısa başlık",
  "plan_summary": "Kullanıcıya gösterilecek Türkçe özet (2-3 cümle)",
  "tasks": [
    {
      "id": "task_1",
      "type": "image",  // image | video | audio | text
      "prompt": "Detaylı İngilizce üretim promptu... Text için brief",
      "format": "post",  // post | story | reel | cover | banner | thumbnail
      "aspect_ratio": "1:1",
      "model": "nano_banana",  // Önerilen model (Text için 'gpt-4o' vb. yazabilirsin)
      "label": "Türkçe kısa etiket (örn: 'Instagram Post 1 — Yaz Vibes')",
      "depends_on": null  // veya başka bir task id
    }
  ]
}

Sadece JSON döndür, başka bir şey yazma."""


class CampaignPlannerService:
    """
    GPT-4o ile otonom kampanya planlama ve yürütme servisi.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def plan_campaign(
        self,
        goal: str,
        brand_context: str = "",
        entity_context: str = "",
        output_types: list = None,
        count: int = None,
        formats: list = None,
        style_notes: str = ""
    ) -> dict:
        """
        Kullanıcının hedefinden detaylı üretim planı çıkarır.
        
        Returns:
            {plan_title, plan_summary, tasks: [{id, type, prompt, format, ...}]}
        """
        user_prompt_parts = [f"HEDEF: {goal}"]
        
        if brand_context:
            user_prompt_parts.append(f"MARKA BİLGİSİ: {brand_context}")
        if entity_context:
            user_prompt_parts.append(f"MEVCUT KARAKTERLERveMEKANLAR: {entity_context}")
        if output_types:
            user_prompt_parts.append(f"İSTENEN ÇIKTI TÜRLERİ: {', '.join(output_types)}")
        if count:
            user_prompt_parts.append(f"TOPLAM ÇIKTI SAYISI: {count}")
        if formats:
            user_prompt_parts.append(f"HEDEF FORMATLAR: {', '.join(formats)}")
        if style_notes:
            user_prompt_parts.append(f"STİL NOTLARI: {style_notes}")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            plan_text = response.choices[0].message.content
            plan = json.loads(plan_text)
            
            # Validate plan structure
            if "tasks" not in plan or not isinstance(plan["tasks"], list):
                return {
                    "success": False,
                    "error": "GPT-4o geçersiz plan formatı üretti"
                }
            
            # Task ID'leri benzersiz yap
            for i, task in enumerate(plan["tasks"]):
                task["id"] = task.get("id", f"task_{i+1}")
            
            plan["success"] = True
            return plan
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Plan oluşturulamadı: {str(e)}"
            }
    
    async def execute_plan(
        self,
        plan: dict,
        orchestrator,
        db,
        session_id: uuid.UUID,
        resolved_entities: list = None
    ) -> dict:
        """
        Oluşturulan planı yürütür — bağımsız görevleri paralel, bağımlı olanları sıralı çalıştırır.
        
        Returns:
            {success, results: [{task_id, type, url, label, ...}], summary}
        """
        tasks = plan.get("tasks", [])
        if not tasks:
            return {"success": False, "error": "Planda görev yok"}
        
        results = {}
        errors = []
        
        # Bağımlılık grafiği oluştur
        independent_tasks = [t for t in tasks if not t.get("depends_on")]
        dependent_tasks = [t for t in tasks if t.get("depends_on")]
        
        # 1. Bağımsız görevleri paralel çalıştır
        if independent_tasks:
            parallel_results = await asyncio.gather(
                *[self._execute_task(t, orchestrator, db, session_id, resolved_entities, results)
                  for t in independent_tasks],
                return_exceptions=True
            )
            
            for task, result in zip(independent_tasks, parallel_results):
                if isinstance(result, Exception):
                    errors.append({"task_id": task["id"], "error": str(result)})
                    results[task["id"]] = {"success": False, "error": str(result)}
                else:
                    results[task["id"]] = result
        
        # 2. Bağımlı görevleri sıralı çalıştır
        for task in dependent_tasks:
            dep_id = task["depends_on"]
            dep_result = results.get(dep_id, {})
            
            # Bağımlılık başarısızsa atla
            if not dep_result.get("success"):
                errors.append({
                    "task_id": task["id"],
                    "error": f"Bağımlı görev {dep_id} başarısız olduğu için atlandı"
                })
                results[task["id"]] = {"success": False, "error": "Dependency failed"}
                continue
            
            try:
                result = await self._execute_task(
                    task, orchestrator, db, session_id, resolved_entities, results
                )
                results[task["id"]] = result
            except Exception as e:
                errors.append({"task_id": task["id"], "error": str(e)})
                results[task["id"]] = {"success": False, "error": str(e)}
        
        # Sonuçları topla
        successful = [
            {
                "task_id": tid,
                "type": r.get("type", "unknown"),
                "url": r.get("image_url") or r.get("video_url") or r.get("audio_url") or r.get("text_content"),
                "label": r.get("label", ""),
                "model": r.get("model", ""),
            }
            for tid, r in results.items()
            if r.get("success")
        ]
        
        return {
            "success": len(successful) > 0,
            "total_tasks": len(tasks),
            "completed": len(successful),
            "failed": len(errors),
            "results": successful,
            "errors": errors if errors else None,
            "plan_title": plan.get("plan_title", ""),
            "plan_summary": plan.get("plan_summary", ""),
        }
    
    async def _execute_task(
        self,
        task: dict,
        orchestrator,
        db,
        session_id: uuid.UUID,
        resolved_entities: list,
        all_results: dict
    ) -> dict:
        """Tek bir plan görevini yürütür."""
        task_type = task.get("type", "image")
        prompt = task.get("prompt", "")
        aspect_ratio = task.get("aspect_ratio", "1:1")
        model = task.get("model", "auto")
        label = task.get("label", "")
        
        # Bağımlılıktan image_url çek (image→video gibi)
        image_url_from_dep = None
        if task.get("depends_on") and task["depends_on"] in all_results:
            dep = all_results[task["depends_on"]]
            if dep.get("success"):
                image_url_from_dep = dep.get("image_url")
        
        try:
            if task_type == "text":
                # ==========================================
                # 🤖 SWARM DELEGATION: COPYWRITER AGENT 
                # ==========================================
                print(f"🤖 [Copywriter Agent] Metin/Caption yazımı başlatıldı: {label}")
                
                # Extract brand attributes if available
                brand_guidelines = ""
                if resolved_entities:
                    for entity in resolved_entities:
                         if getattr(entity, 'entity_type', '') == 'brand':
                             attrs = getattr(entity, 'attributes', {})
                             banned = attrs.get('banned_words', [])
                             tone = attrs.get('tone', 'profesyonel ve ilgi çekici')
                             if banned:
                                 brand_guidelines += f" KESİNLİKLE KULLANILMAYACAK KELİMELER: {', '.join(banned)}."
                             brand_guidelines += f" MARKA TONU: {tone}."
                
                copywriter_prompt = f"Sen kreatif bir reklam ajansında usta bir Metin Yazarı (Copywriter) Agent'sın. Sana verilen içerik brief'ine göre viral potansiyeli yüksek, ilgi çekici sosyal medya kopyaları veya reklam metinleri yazacaksın.\n\nHEDEF/BRIEF: {prompt}\n{brand_guidelines}\n\nLütfen sadece oluşturduğun metni döndür, giriş veya çıkış cümlesi ekleme."

                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Sen usta bir Metin Yazarı (Copywriter) ajansısın."},
                        {"role": "user", "content": copywriter_prompt}
                    ],
                    temperature=0.7,
                )
                
                generated_text = response.choices[0].message.content
                print(f"✅ [Copywriter Agent] Başarılı: {generated_text[:50]}...")
                
                # TODO: (Optional) Yazıyı asset olarak kaydet
                return {
                    "success": True,
                    "type": "text",
                    "text_content": generated_text,
                    "label": label,
                    "model": "copywriter_agent (gpt-4o)"
                }

            elif task_type == "image":
                result = await orchestrator._generate_image(
                    db, session_id,
                    {"prompt": prompt, "aspect_ratio": aspect_ratio, "model": model},
                    resolved_entities or []
                )
                result["type"] = "image"
                result["label"] = label
                return result
            
            elif task_type == "video":
                # Video üretimi — senkron sonuç dönemez (arka plan), 
                # ama plan_and_execute için fal.ai'ye direkt çağrı yapacağız
                video_params = {
                    "prompt": prompt,
                    "duration": task.get("duration", "5"),
                    "aspect_ratio": aspect_ratio,
                    "model": model,
                }
                if image_url_from_dep:
                    video_params["image_url"] = image_url_from_dep
                
                # Direkt fal plugin çağrısı (arka plana atma, senkron bekle)
                from app.services.prompt_translator import translate_to_english
                english_prompt, _ = await translate_to_english(prompt)
                video_params["prompt"] = english_prompt
                
                if model == "veo":
                    from app.services.google_video_service import GoogleVideoService
                    veo = GoogleVideoService()
                    video_result = await veo.generate_video(video_params)
                else:
                    video_result = await orchestrator.fal_plugin._generate_video(video_params)
                
                if video_result.get("success"):
                    video_url = video_result.get("video_url")
                    # Asset kaydet
                    from app.services.asset_service import asset_service
                    try:
                        await asset_service.save_asset(
                            db=db, session_id=session_id,
                            url=video_url, asset_type="video",
                            prompt=prompt,
                            model_name=video_result.get("model", model),
                            model_params={"aspect_ratio": aspect_ratio, "campaign": True}
                        )
                    except Exception:
                        pass
                    
                    return {
                        "success": True,
                        "type": "video",
                        "video_url": video_url,
                        "model": video_result.get("model", model),
                        "label": label,
                    }
                else:
                    return {
                        "success": False,
                        "type": "video",
                        "error": video_result.get("error", "Video üretilemedi")
                    }
            
            elif task_type == "audio":
                # Müzik üretimi
                from app.services.plugins.fal_plugin_v2 import FalPluginV2
                fal = FalPluginV2()
                audio_result = await fal.execute("generate_music", {
                    "prompt": prompt,
                    "duration": task.get("duration", 30)
                })
                
                if audio_result.success:
                    return {
                        "success": True,
                        "type": "audio",
                        "audio_url": audio_result.data.get("audio_url"),
                        "label": label,
                    }
                else:
                    return {"success": False, "type": "audio", "error": audio_result.error}
            
            else:
                return {"success": False, "error": f"Bilinmeyen görev tipi: {task_type}"}
        
        except Exception as e:
            return {"success": False, "type": task_type, "error": str(e), "label": label}


# Singleton
campaign_planner = CampaignPlannerService()
