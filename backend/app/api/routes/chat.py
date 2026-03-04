"""
Chat API endpoint'leri — Tek Asistan Mimarisi.
Mesajlar ana chat session'a, asset'ler aktif projeye kaydedilir.
"""
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, WebSocket, WebSocketDisconnect
from typing import List
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import base64
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_user_required
from app.models.models import Session, Message, User
from app.schemas.schemas import ChatRequest, ChatResponse, MessageResponse, AssetResponse, EntityResponse
from app.services.agent.orchestrator import agent

router = APIRouter(prefix="/chat", tags=["Sohbet"])


@router.get("/main-session")
async def get_main_chat_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Kullanıcının ana chat session'ını döndür. Yoksa otomatik oluştur."""
    
    # Mevcut main chat session var mı?
    if current_user.main_chat_session_id:
        result = await db.execute(
            select(Session).where(
                Session.id == current_user.main_chat_session_id,
                Session.is_active == True
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"session_id": str(existing.id), "title": existing.title}
    
    # Yoksa yeni oluştur
    main_session = Session(
        user_id=current_user.id,
        title="Ana Sohbet",
        description="Tüm projeler için tek asistan sohbeti",
        category="main_chat"
    )
    db.add(main_session)
    await db.flush()
    await db.refresh(main_session)
    
    # User'a bağla
    current_user.main_chat_session_id = main_session.id
    await db.commit()
    
    return {"session_id": str(main_session.id), "title": main_session.title}


async def _process_chat(
    actual_session_id: Optional[str],
    actual_message: str,
    reference_images_base64: Optional[List[str]],
    db: AsyncSession,
    user_id,
    active_project_id: Optional[str] = None
) -> ChatResponse:
    """Chat işleme ortak logic. Per-project chat — session_id = proje."""
    
    # Session al veya oluştur
    if actual_session_id:
        try:
            session_uuid = UUID(actual_session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Geçersiz session ID formatı: {actual_session_id}")
        
        result = await db.execute(
            select(Session).where(Session.id == session_uuid, Session.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı veya erişim yetkiniz yok")
    else:
        # Yeni anonim session oluştur
        session = Session(title="Yeni Sohbet")
        db.add(session)
        await db.flush()
        await db.refresh(session)
    
    # Kullanıcı mesajını kaydet
    user_message = Message(
        session_id=session.id,
        role="user",
        content=actual_message,
        metadata_={"has_reference_image": bool(reference_images_base64), "image_count": len(reference_images_base64) if reference_images_base64 else 0} if reference_images_base64 else {}
    )
    db.add(user_message)
    await db.flush()
    await db.refresh(user_message)
    
    # ÖNCEKİ MESAJLARI ÇEK - conversation_history oluştur
    # ChatGPT gibi tüm sohbet geçmişini hatırlaması için gerekli!
    from sqlalchemy import asc
    previous_messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .where(Message.id != user_message.id)  # Yeni mesaj hariç
        .order_by(asc(Message.created_at))  # Kronolojik sıra
    )
    previous_messages = previous_messages_result.scalars().all()
    
    # Hata pattern'leri - bunları içeren asistan mesajlarını atla
    ERROR_PATTERNS = [
        "kredi", "credit", "yetersiz", "insufficient", 
        "hata", "error", "başarısız", "failed",
        "oluşturulamadı", "üretilemedi", "yapılamadı"
    ]
    
    # OpenAI formatına çevir - HATA MESAJLARINI FİLTRELE
    conversation_history = []
    last_reference_urls_from_history = []  # DB'den referans URL listesi çıkar
    
    for msg in previous_messages:
        content = msg.content.lower() if msg.content else ""
        
        # Asistan mesajlarında hata pattern'i varsa atla
        if msg.role == "assistant":
            has_error = any(pattern in content for pattern in ERROR_PATTERNS)
            if has_error:
                continue  # Bu mesajı geçmişe ekleme
        
        # Mesaj içeriğini hazırla
        msg_content = msg.content or ""
        
        # Assistant mesajlarında metadata'dan image/video URL'lerini ekle
        # (content'ten kaldırıldı ama GPT-4o'nun bunları bilmesi gerekiyor)
        if msg.role == "assistant" and msg.metadata_:
            meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            images = meta.get("images", [])
            videos = meta.get("videos", [])
            if images:
                urls = [img.get("url", "") for img in images if isinstance(img, dict) and img.get("url")]
                if urls:
                    msg_content += "\n\n[Bu mesajda üretilen görseller: " + ", ".join(urls) + "]"
                    last_reference_urls_from_history.extend(urls)  # Tüm üretilen görselleri referans olarak kaydet
            if videos:
                urls = [vid.get("url", "") for vid in videos if isinstance(vid, dict) and vid.get("url")]
                if urls:
                    msg_content += "\n\n[Bu mesajda üretilen videolar: " + ", ".join(urls) + "]"
        
        # User mesajlarında referans görsel URL'si varsa çıkar
        if msg.role == "user" and msg.metadata_:
            meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            # Eski tekil yapı
            if meta.get("has_reference_image") and meta.get("reference_url"):
                last_reference_urls_from_history = [meta["reference_url"]]
            # Yeni çoklu yapı
            elif meta.get("reference_urls") and isinstance(meta.get("reference_urls"), list):
                last_reference_urls_from_history = meta["reference_urls"]
        
        conversation_history.append({
            "role": msg.role,
            "content": msg_content
        })
    
    # Max 20 mesaj (son mesajlar)
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    
    print(f"📜 Conversation history: {len(conversation_history)} mesaj yüklendi (session: {session.id})")
    
    # Agent ile yanıt al — çoklu referans görselleri destekle
    primary_image = reference_images_base64[0] if reference_images_base64 else None
    try:
        agent_result = await agent.process_message(
            user_message=actual_message,
            session_id=session.id,  # Proje session — hem chat hem asset
            db=db,
            conversation_history=conversation_history,
            reference_image=primary_image,
            reference_images=reference_images_base64,
            last_reference_urls=last_reference_urls_from_history,
        )
    except Exception as e:
        import traceback
        print(f"AGENT ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent hatası: {str(e)}")
    
    response_content = agent_result.get("response", "")
    images = agent_result.get("images", [])
    videos = agent_result.get("videos", [])
    entities_created = agent_result.get("entities_created", [])
    
    # Kullanıcı referans görselleri yüklendiyse, URL'leri user mesajının metadata'sına kaydet
    uploaded_ref_url = agent_result.get("_uploaded_image_url")
    uploaded_ref_urls = agent_result.get("_uploaded_image_urls", [])
    if uploaded_ref_url or uploaded_ref_urls:
        current_meta = user_message.metadata_ or {}
        current_meta["has_reference_image"] = True
        if uploaded_ref_urls:
            current_meta["reference_urls"] = uploaded_ref_urls
        elif uploaded_ref_url:
            current_meta["reference_url"] = uploaded_ref_url
            current_meta["reference_urls"] = [uploaded_ref_url]
        user_message.metadata_ = current_meta
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user_message, "metadata_")
    
    # Assistant yanıtını kaydet — URL'ler metadata'da saklanır, content'e eklenmez
    enriched_content = response_content
    
    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=enriched_content,
        metadata_={
            "images": images,
            "videos": videos,
            "entities_created": [e.get("tag") for e in entities_created if isinstance(e, dict)]
        } if images or videos or entities_created else {}
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)
    
    # === AUTO SUMMARY: Projeler arası hafıza ===
    # Her 10 mesajda bir sohbet özeti kaydet
    total_messages = len(conversation_history) + 2  # +2 = yeni user + assistant
    if total_messages >= 10 and total_messages % 5 == 0 and session.user_id:
        try:
            from app.services.conversation_memory_service import conversation_memory
            summary_messages = conversation_history[-10:] + [
                {"role": "user", "content": actual_message},
                {"role": "assistant", "content": response_content}
            ]
            summary_text = await conversation_memory.summarize_conversation(
                messages=summary_messages,
                session_title=session.title
            )
            if summary_text:
                await conversation_memory.save_conversation_summary(
                    db=db,
                    user_id=session.user_id,
                    session_id=session.id,
                    summary=summary_text
                )
            print(f"💾 Auto-summary kaydedildi (proje: {session.title}, mesaj: {total_messages})")
        except Exception as e:
            print(f"⚠️ Auto-summary hatası: {e}")
    
    # Assets listesi oluştur
    assets = []
    for img in images:
        assets.append(AssetResponse(
            id=None,
            asset_type="image",
            url=img.get("url", ""),
            prompt=img.get("prompt", "")
        ))
        
    for vid in videos:
        assets.append(AssetResponse(
            id=None,
            asset_type="video",
            url=vid.get("url", ""),
            prompt=vid.get("prompt", ""),
            thumbnail_url=vid.get("thumbnail_url")
        ))
    
    # Entities response listesi oluştur
    entity_responses = []
    for entity_data in entities_created:
        if isinstance(entity_data, dict):
            entity_responses.append(EntityResponse(
                id=entity_data.get("id"),
                user_id=session.user_id,  # Session'dan user_id al
                session_id=session.id,
                entity_type=entity_data.get("entity_type", ""),
                name=entity_data.get("name", ""),
                tag=entity_data.get("tag", ""),
                description=entity_data.get("description"),
                attributes=entity_data.get("attributes"),
                created_at=assistant_message.created_at
            ))
    
    return ChatResponse(
        session_id=session.id,
        message=MessageResponse(
            id=user_message.id,
            session_id=user_message.session_id,
            role=user_message.role,
            content=user_message.content,
            metadata_=user_message.metadata_,
            created_at=user_message.created_at
        ),
        response=MessageResponse(
            id=assistant_message.id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            metadata_=assistant_message.metadata_,
            created_at=assistant_message.created_at
        ),
        assets=assets,
        entities_created=entity_responses
    )


# JSON endpoint (normal mesajlar)
@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Kullanıcı mesajını işle ve yanıt ver (JSON)."""
    return await _process_chat(
        actual_session_id=str(request.session_id) if request.session_id else None,
        actual_message=request.message,
        reference_images_base64=None,
        db=db,
        user_id=current_user.id,
        active_project_id=str(request.active_project_id) if request.active_project_id else None
    )


# FormData endpoint (tek dosya — backward compat)
@router.post("/with-image", response_model=ChatResponse)
async def chat_with_image(
    session_id: str = Form(...),
    message: str = Form(...),
    reference_image: UploadFile = File(...),
    active_project_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Kullanıcı mesajını tek referans görsel ile işle (backward compat)."""
    image_content = await reference_image.read()
    reference_image_base64 = base64.b64encode(image_content).decode('utf-8')
    
    return await _process_chat(
        actual_session_id=session_id,
        actual_message=message,
        reference_images_base64=[reference_image_base64],
        db=db,
        user_id=current_user.id,
        active_project_id=active_project_id
    )


# FormData endpoint (çoklu dosya — max 10)
@router.post("/with-files", response_model=ChatResponse)
async def chat_with_files(
    session_id: str = Form(...),
    message: str = Form(...),
    reference_files: List[UploadFile] = File(...),
    active_project_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Kullanıcı mesajını birden fazla referans görsel ile işle (max 10)."""
    if len(reference_files) > 10:
        raise HTTPException(status_code=400, detail="Maksimum 10 dosya yüklenebilir")
    
    images_base64 = []
    uploaded_urls = []
    
    for f in reference_files:
        content = await f.read()
        images_base64.append(base64.b64encode(content).decode('utf-8'))
        
        # Dosyayı fal.ai storage'a yükle ve asset olarak kaydet
        try:
            import fal_client
            content_type = f.content_type or "image/png"
            url = fal_client.upload(content, content_type)
            uploaded_urls.append((url, f.filename or "uploaded_file"))
        except Exception as e:
            logger.warning(f"Dosya fal.ai'ye yüklenemedi: {e}")
    
    # Yüklenen dosyaları asset olarak kaydet
    if uploaded_urls:
        try:
            from uuid import UUID as UUIDType
            from app.services.asset_service import AssetService
            asset_service = AssetService()
            target_session_id = UUIDType(active_project_id) if active_project_id else UUIDType(session_id)
            
            for url, filename in uploaded_urls:
                await asset_service.save_asset(
                    db=db,
                    session_id=target_session_id,
                    url=url,
                    asset_type="uploaded",
                    prompt=f"Kullanıcı yüklemesi: {filename}",
                    model_name="user_upload",
                )
        except Exception as e:
            logger.warning(f"Uploaded asset kaydedilemedi: {e}")
    
    return await _process_chat(
        actual_session_id=session_id,
        actual_message=message,
        reference_images_base64=images_base64,
        db=db,
        user_id=current_user.id,
        active_project_id=active_project_id
    )


# SSE Streaming endpoint
@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Kullanıcı mesajını işle ve SSE ile stream et (ChatGPT tarzı)."""
    print(f"🔴 STREAM ENDPOINT HIT! message={request.message[:50]} user={current_user.id}")
    from sqlalchemy import asc
    import json
    
    actual_session_id = str(request.session_id) if request.session_id else None
    active_project_id = str(request.active_project_id) if request.active_project_id else None
    actual_message = request.message
    
    # Session al
    if actual_session_id:
        try:
            session_uuid = UUID(actual_session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz session ID")
        result = await db.execute(select(Session).where(Session.id == session_uuid))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    else:
        session = Session(title="Yeni Sohbet")
        db.add(session)
        await db.flush()
        await db.refresh(session)
    
    # Kullanıcı mesajını kaydet
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=actual_message,
        metadata_={"has_reference_image": True} if actual_message and "[REFERANS GÖRSEL URL:" in actual_message else {}
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)
    
    # Geçmiş mesajları çek
    prev_result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .where(Message.id != user_msg.id)
        .order_by(asc(Message.created_at))
    )
    previous_messages = prev_result.scalars().all()
    
    ERROR_PATTERNS = ["kredi", "credit", "yetersiz", "insufficient", "hata", "error", "başarısız", "failed"]
    conversation_history = []
    last_reference_url_from_history = None
    
    for msg in previous_messages:
        content = msg.content.lower() if msg.content else ""
        if msg.role == "assistant" and any(p in content for p in ERROR_PATTERNS):
            continue
        
        msg_content = msg.content or ""
        
        # Assistant mesajlarında metadata'dan image/video URL'lerini ekle
        if msg.role == "assistant" and msg.metadata_:
            meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            images = meta.get("images", [])
            videos = meta.get("videos", [])
            if images:
                urls = [img.get("url", "") for img in images if isinstance(img, dict) and img.get("url")]
                if urls:
                    msg_content += "\n\n[Bu mesajda üretilen görseller: " + ", ".join(urls) + "]"
                    last_reference_url_from_history = urls[-1]
            if videos:
                urls = [vid.get("url", "") for vid in videos if isinstance(vid, dict) and vid.get("url")]
                if urls:
                    msg_content += "\n\n[Bu mesajda üretilen videolar: " + ", ".join(urls) + "]"
        
        if msg.role == "user" and msg.metadata_:
            meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
            if meta.get("has_reference_image") and meta.get("reference_url"):
                last_reference_url_from_history = meta["reference_url"]
        
        conversation_history.append({"role": msg.role, "content": msg_content})
    
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    
    async def event_generator():
        full_response = ""
        all_images = []
        all_videos = []
        all_entities = []
        
        try:
            async for event in agent.process_message_stream(
                user_message=actual_message,
                session_id=session.id,
                db=db,
                conversation_history=conversation_history,
                user_id=current_user.id
            ):
                yield event
                
                # Tam yanıtı biriktir (DB'ye kaydetmek için)
                if event.startswith("event: token"):
                    data_line = event.split("data: ", 1)[1].strip()
                    try:
                        token = json.loads(data_line)
                        full_response += token
                    except:
                        pass
                elif event.startswith("event: assets"):
                    data_line = event.split("data: ", 1)[1].strip()
                    try:
                        all_images = json.loads(data_line)
                    except:
                        pass
                elif event.startswith("event: videos"):
                    data_line = event.split("data: ", 1)[1].strip()
                    try:
                        all_videos = json.loads(data_line)
                    except:
                        pass
        except Exception as e:
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
        
        # Yanıtı DB'ye kaydet — üretilen görsellerin URL'lerini de mesaja ekle
        try:
            # Boş yanıt durumunda: video/görsel arka planda üretiliyorsa placeholder koyma
            # Sadece gerçekten content veya media varsa kaydet
            if full_response or all_images or all_videos:
                enriched_response = full_response or ""
                
                assistant_msg = Message(
                    session_id=session.id,
                    role="assistant",
                    content=enriched_response,
                    metadata_={
                        "images": all_images,
                        "videos": all_videos,
                        "streamed": True
                    } if all_images or all_videos else {"streamed": True}
                )
                db.add(assistant_msg)
                await db.commit()
                
                # === AUTO SUMMARY: Projeler arası hafıza (stream) ===
                total_messages = len(conversation_history) + 2
                if total_messages >= 10 and total_messages % 5 == 0 and session.user_id:
                    try:
                        from app.services.conversation_memory_service import conversation_memory
                        summary_messages = conversation_history[-10:] + [
                            {"role": "user", "content": actual_message},
                            {"role": "assistant", "content": full_response}
                        ]
                        summary_text = await conversation_memory.summarize_conversation(
                            messages=summary_messages,
                            session_title=session.title
                        )
                        if summary_text:
                            await conversation_memory.save_conversation_summary(
                                db=db,
                                user_id=session.user_id,
                                session_id=session.id,
                                summary=summary_text
                            )
                        print(f"💾 Stream auto-summary kaydedildi (proje: {session.title}, mesaj: {total_messages})")
                    except Exception as sum_err:
                        print(f"⚠️ Stream auto-summary hatası: {sum_err}")
            else:
                print("ℹ️ Stream yanıtı boş — arka plan görevi çalışıyor olabilir, DB'ye kayıt atlanıyor")
        except Exception as e:
            print(f"⚠️ Stream DB kayıt hatası: {e}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# WebSocket — gerçek zamanlı üretim ilerleme takibi
@router.websocket("/ws/progress/{session_id}")
async def progress_websocket(websocket: WebSocket, session_id: str):
    """Arka plan görevlerinin ilerleme bilgisini gerçek zamanlı gönderir."""
    from app.services.progress_service import progress_service
    
    await websocket.accept()
    progress_service.register(session_id, websocket)
    print(f"🔌 Progress WS connected: {session_id[:8]}...")
    
    try:
        while True:
            # Client'tan gelen ping/pong mesajları
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        progress_service.unregister(session_id, websocket)
        print(f"🔌 Progress WS disconnected: {session_id[:8]}...")


# ============== GERİ BİLDİRİM SİSTEMİ ==============

from pydantic import BaseModel as PydanticBaseModel

class FeedbackRequest(PydanticBaseModel):
    message_id: str  # Asistan mesajının ID'si
    score: int  # 1 = 👍, -1 = 👎
    reason: Optional[str] = None  # 👎 nedeni: "wrong_style", "bad_quality", "wrong_prompt", "other"


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Asistan yanıtına geri bildirim gönder (👍/👎). Agent bu veriyi öğrenme için kullanır."""
    from uuid import UUID as UUIDType
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.episodic_memory_service import episodic_memory
    
    # Mesajı bul
    try:
        msg_uuid = UUIDType(request.message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz message_id")
    
    result = await db.execute(
        select(Message).where(Message.id == msg_uuid, Message.role == "assistant")
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Asistan mesajı bulunamadı")
    
    # Session sahipliği doğrula
    sess_result = await db.execute(
        select(Session).where(Session.id == message.session_id, Session.user_id == current_user.id)
    )
    if not sess_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu mesaja erişim yetkiniz yok")
    
    # Metadata'ya feedback kaydet
    meta = message.metadata_ or {}
    meta["feedback"] = {
        "score": request.score,
        "reason": request.reason,
        "timestamp": datetime.utcnow().isoformat() if 'datetime' in dir() else __import__('datetime').datetime.utcnow().isoformat()
    }
    message.metadata_ = meta
    flag_modified(message, "metadata_")
    await db.commit()
    
    # === ÖĞRENME: Episodic Memory'ye kaydet ===
    user_id_str = str(current_user.id)
    
    if request.score > 0:
        # 👍 — Başarılı yanıt
        await episodic_memory.remember(
            user_id=user_id_str,
            event_type="feedback",
            content=f"Kullanıcı bu yanıtı beğendi: '{message.content[:80]}...'",
            metadata={"message_id": request.message_id, "score": 1}
        )
        
        # Başarılı prompt'u kaydet (görsel/video varsa)
        images = meta.get("images", [])
        videos = meta.get("videos", [])
        if images or videos:
            try:
                from app.services.conversation_memory_service import conversation_memory
                
                # Prompt'u önceki user mesajından al
                prev_result = await db.execute(
                    select(Message).where(
                        Message.session_id == message.session_id,
                        Message.role == "user",
                        Message.created_at < message.created_at
                    ).order_by(Message.created_at.desc()).limit(1)
                )
                prev_msg = prev_result.scalar_one_or_none()
                
                if prev_msg:
                    asset_url = images[0].get("url", "") if images else videos[0].get("url", "") if videos else ""
                    asset_type = "image" if images else "video"
                    model_name = (images[0].get("model") if images else videos[0].get("model") if videos else "") or "unknown"
                    
                    await conversation_memory.save_successful_prompt(
                        user_id=current_user.id,
                        prompt=prev_msg.content,
                        result_url=asset_url,
                        score=request.score,
                        asset_type=asset_type
                    )
                    
                    # Model başarısını da kaydet
                    await episodic_memory.remember(
                        user_id=user_id_str,
                        event_type="model_success",
                        content=f"'{model_name}' modeli ile '{prev_msg.content[:50]}...' başarılı oldu",
                        metadata={"model": model_name, "asset_type": asset_type, "score": 1}
                    )
            except Exception as e:
                print(f"⚠️ Prompt learning hatası: {e}")
    else:
        # 👎 — Olumsuz feedback
        reason_text = {
            "wrong_style": "Yanlış stil kullanıldı",
            "bad_quality": "Görsel kalitesi kötü",
            "wrong_prompt": "Prompt yanlış anlaşıldı",
            "other": request.reason or "Belirtilmedi"
        }.get(request.reason, request.reason or "Belirtilmedi")
        
        await episodic_memory.remember(
            user_id=user_id_str,
            event_type="feedback",
            content=f"Kullanıcı memnun değil: {reason_text}. Yanıt: '{message.content[:60]}...'",
            metadata={"message_id": request.message_id, "score": -1, "reason": request.reason}
        )
    
    emoji = "👍" if request.score > 0 else "👎"
    print(f"{emoji} Feedback alındı: message={request.message_id[:8]}... score={request.score}")
    
    return {"success": True, "message": f"Geri bildirim kaydedildi {emoji}"}


# ============== PROMPT TEMPLATE KÜTÜPHANESİ ==============

PROMPT_TEMPLATES = [
    {
        "id": "film_poster",
        "name": "Film Afişi",
        "icon": "🎬",
        "category": "creative",
        "template": "Bir film afişi oluştur: {konu}. Sinematik ışıklandırma, dramatik kompozisyon, film afişi tipografisi.",
        "variables": ["konu"],
        "example": "Bir bilim kurgu film afişi: uzay istasyonunda geçen gerilim filmi"
    },
    {
        "id": "product_photo",
        "name": "Ürün Fotoğrafı",
        "icon": "📸",
        "category": "commercial",
        "template": "{ürün} ürünü için profesyonel stüdyo fotoğrafı. Temiz beyaz arka plan, yumuşak stüdyo ışığı, ürün odaklı.",
        "variables": ["ürün"],
        "example": "Lüks saat için profesyonel stüdyo fotoğrafı"
    },
    {
        "id": "social_media",
        "name": "Sosyal Medya Post",
        "icon": "📱",
        "category": "social",
        "template": "{platform} için {konu} hakkında dikkat çekici bir görsel. Modern tasarım, canlı renkler, metin alanı bırak.",
        "variables": ["platform", "konu"],
        "example": "Instagram için kahve dükkanı açılışı hakkında dikkat çekici bir görsel"
    },
    {
        "id": "portrait",
        "name": "Profesyonel Portre",
        "icon": "🧑‍💼",
        "category": "portrait",
        "template": "{kişi} için profesyonel portre fotoğrafı. Stüdyo ışığı, bokeh arka plan, {stil} stil.",
        "variables": ["kişi", "stil"],
        "example": "Genç bir iş kadını için profesyonel portre, corporate stil"
    },
    {
        "id": "anime_character",
        "name": "Anime Karakter",
        "icon": "🎌",
        "category": "creative",
        "template": "{karakter} anime karakteri. {ortam} ortamında, {stil} anime stili, yüksek detay.",
        "variables": ["karakter", "ortam", "stil"],
        "example": "Kılıçlı savaşçı anime karakteri, şato ortamında, shonen anime stili"
    },
    {
        "id": "logo_design",
        "name": "Logo Tasarımı",
        "icon": "✏️",
        "category": "commercial",
        "template": "{marka} adlı {sektör} markası için modern minimalist logo. Temiz çizgiler, {renk} renk paleti.",
        "variables": ["marka", "sektör", "renk"],
        "example": "EcoTech adlı teknoloji markası için modern minimalist logo, yeşil-mavi renk paleti"
    },
    {
        "id": "food_photo",
        "name": "Yemek Fotoğrafı",
        "icon": "🍽️",
        "category": "commercial",
        "template": "{yemek} yemeğinin profesyonel fotoğrafı. Food photography stili, doğal ışık, iştah açıcı sunum.",
        "variables": ["yemek"],
        "example": "Ev yapımı İtalyan pizzasının profesyonel fotoğrafı"
    },
    {
        "id": "landscape",
        "name": "Manzara",
        "icon": "🏔️",
        "category": "creative",
        "template": "{lokasyon} manzarası. {zaman} zamanında, {hava} hava durumu, sinematik geniş açı, 8K detay.",
        "variables": ["lokasyon", "zaman", "hava"],
        "example": "Norveç fiyortları manzarası, gün batımında, puslu hava"
    },
    {
        "id": "fashion",
        "name": "Moda Fotoğrafı",
        "icon": "👗",
        "category": "commercial",
        "template": "{kıyafet} giyen model. {lokasyon} lokasyonunda, {stil} moda fotoğrafı stili, editorial look.",
        "variables": ["kıyafet", "lokasyon", "stil"],
        "example": "Siyah elbise giyen model, Paris sokaklarında, haute couture moda fotoğrafı stili"
    },
    {
        "id": "music_video",
        "name": "Müzik Videosu Karesi",
        "icon": "🎵",
        "category": "creative",
        "template": "{tür} müzik türünde bir müzik videosu karesi. {sahne} sahnesi, {atmosfer} atmosfer, sinematik renk grading.",
        "variables": ["tür", "sahne", "atmosfer"],
        "example": "Lo-fi hip hop türünde bir müzik videosu karesi. Yağmurlu gece sahnesi, nostaljik atmosfer"
    }
]


@router.get("/templates")
async def get_prompt_templates(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user_required)
):
    """Prompt template kütüphanesini döndür."""
    templates = PROMPT_TEMPLATES
    if category:
        templates = [t for t in templates if t["category"] == category]
    
    categories = list(set(t["category"] for t in PROMPT_TEMPLATES))
    return {
        "templates": templates,
        "categories": categories,
        "total": len(templates)
    }