"""
Oturum API endpoint'leri.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_user_required
from app.models.models import Session, Message, Entity, GeneratedAsset, TrashItem, User
from app.schemas.schemas import SessionCreate, SessionResponse, MessageResponse, EntityResponse, AssetResponse

router = APIRouter(prefix="/sessions", tags=["Oturumlar"])


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Yeni oturum oluştur."""
    try:
        new_session = Session(
            user_id=current_user.id,
            title=session_data.title or "Yeni Proje",
            description=session_data.description,
            category=session_data.category
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Oturum oluşturulurken hata: {str(e)}"
        )


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturumları listele (kullanıcıya özel)."""
    query = select(Session).where(
        Session.is_active == True,
        Session.user_id == current_user.id
    )
    
    result = await db.execute(
        query.order_by(Session.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturum detayı."""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    return session


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturumdaki mesajları getir."""
    # Session sahipliği doğrula
    sess = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == current_user.id))
    if not sess.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    filtered_messages = []
    for msg in messages:
        meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
        has_media = bool(meta.get("images") or meta.get("videos") or meta.get("audio_url"))
        is_blank_pending_assistant = (
            msg.role == "assistant"
            and not (msg.content or "").strip()
            and not has_media
            and meta.get("pending")
        )
        if is_blank_pending_assistant:
            continue
        filtered_messages.append(msg)

    return filtered_messages


@router.get("/{session_id}/entities", response_model=list[EntityResponse])
async def get_session_entities(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturumdaki varlıkları getir."""
    sess = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == current_user.id))
    if not sess.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    result = await db.execute(
        select(Entity)
        .where(Entity.session_id == session_id)
        .order_by(Entity.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{session_id}/assets", response_model=list[AssetResponse])
async def get_session_assets(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturumdaki asset'leri getir."""
    sess = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == current_user.id))
    if not sess.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    result = await db.execute(
        select(GeneratedAsset)
        .where(GeneratedAsset.session_id == session_id)
        .order_by(GeneratedAsset.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Proje bilgilerini güncelle (rename, description, category)."""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    
    if session_data.title:
        session.title = session_data.title
    if session_data.description is not None:
        session.description = session_data.description
    if session_data.category is not None:
        session.category = session_data.category
    
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Oturumu çöp kutusuna taşı (soft delete)."""
    from datetime import datetime, timedelta
    
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    
    # Önce bu session'a bağlı TrashItem'ların session_id'sini NULL yap
    # Böylece session silinince çöp kutusundaki item'lar kaybolmaz
    existing_trash_items = await db.execute(
        select(TrashItem).where(TrashItem.session_id == session_id)
    )
    for trash_item in existing_trash_items.scalars().all():
        trash_item.session_id = None
    
    # Session'ı çöp kutusuna ekle
    trash_item = TrashItem(
        user_id=session.user_id,
        item_type="session",
        item_id=str(session.id),
        item_name=session.title or "Untitled Project",
        original_data={
            "title": session.title,
            "user_id": str(session.user_id) if session.user_id else None,
            "metadata": session.metadata_,
            "created_at": session.created_at.isoformat() if session.created_at else None
        },
        session_id=None,  # Session kendisi silindiği için NULL
        expires_at=datetime.now() + timedelta(days=3)
    )
    db.add(trash_item)
    
    # Session'ı soft delete yap
    session.is_active = False
    await db.commit()


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Asset sil (soft delete - çöp kutusuna taşı)."""
    from datetime import timedelta
    
    result = await db.execute(
        select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadı")
    
    # TrashItem oluştur
    from datetime import datetime
    trash_item = TrashItem(
        user_id=current_user.id,
        item_type="asset",
        item_id=str(asset.id),
        item_name=asset.prompt[:50] if asset.prompt else "Generated Asset",
        original_data={
            "url": asset.url,
            "type": asset.asset_type,
            "prompt": asset.prompt,
            "session_id": str(asset.session_id) if asset.session_id else None,
            "model_name": asset.model_name
        },
        session_id=asset.session_id,
        expires_at=datetime.now() + timedelta(days=3)
    )
    db.add(trash_item)
    
    # İlişkili entity_assets kayıtlarını sil (NOT NULL constraint)
    from app.models.models import EntityAsset
    entity_asset_result = await db.execute(
        select(EntityAsset).where(EntityAsset.asset_id == asset_id)
    )
    for ea in entity_asset_result.scalars().all():
        await db.delete(ea)
    
    # Child asset'lerin parent referansını temizle
    child_result = await db.execute(
        select(GeneratedAsset).where(GeneratedAsset.parent_asset_id == asset_id)
    )
    for child in child_result.scalars().all():
        child.parent_asset_id = None
    
    # Asset'i sil
    await db.delete(asset)
    await db.commit()


from pydantic import BaseModel as PydanticBaseModel

class AssetRenameRequest(PydanticBaseModel):
    prompt: str

@router.patch("/assets/{asset_id}/rename", response_model=AssetResponse)
async def rename_asset(
    asset_id: UUID,
    data: AssetRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Asset adını değiştir."""
    result = await db.execute(
        select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadı")
    
    asset.prompt = data.prompt.strip()
    await db.commit()
    await db.refresh(asset)
    return asset
