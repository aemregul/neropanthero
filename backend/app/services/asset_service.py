"""
Asset Service - Üretilen görselleri/videoları yönetir.

Akıllı agent özellikleri:
- Geçmiş assetleri getir
- Favori işaretle
- Parent-child ilişkisi
"""
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import GeneratedAsset, EntityAsset, Entity


class AssetService:
    """Asset yönetim servisi."""
    
    async def save_asset(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        url: str,
        asset_type: str = "image",
        prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        model_params: Optional[dict] = None,
        parent_asset_id: Optional[uuid.UUID] = None,
        entity_ids: Optional[list[uuid.UUID]] = None,
        thumbnail_url: Optional[str] = None,
    ) -> GeneratedAsset:
        """
        Yeni asset kaydet.
        
        Args:
            session_id: Oturum ID
            url: Asset URL
            asset_type: "image" veya "video"
            prompt: Üretim prompt'u
            model_name: Kullanılan model
            model_params: Model parametreleri
            parent_asset_id: Türetilen asset ID (edit/upscale için)
            entity_ids: İlişkili entity ID'leri
            thumbnail_url: Video için thumbnail URL (edit işlemleri için kritik)
        
        Returns:
            GeneratedAsset: Kaydedilen asset
        """
        asset = GeneratedAsset(
            session_id=session_id,
            url=url,
            asset_type=asset_type,
            prompt=prompt,
            model_name=model_name,
            model_params=model_params or {},
            parent_asset_id=parent_asset_id,
            thumbnail_url=thumbnail_url,
        )
        
        db.add(asset)
        await db.flush()
        
        # Entity ilişkilerini kur
        if entity_ids:
            for entity_id in entity_ids:
                entity_asset = EntityAsset(
                    entity_id=entity_id,
                    asset_id=asset.id
                )
                db.add(entity_asset)
        
        await db.commit()
        await db.refresh(asset)
        
        # Model kullanım loglaması (fire-and-forget)
        if model_name:
            try:
                from app.services.usage_tracker import log_model_usage
                from app.models.models import Session
                # Session'dan user_id al
                result = await db.execute(select(Session).where(Session.id == session_id))
                session = result.scalar_one_or_none()
                user_id = session.user_id if session else None
                await log_model_usage(db, user_id, model_name, asset_type)
            except Exception:
                pass  # Loglama hatası ana işlemi bozmamalı
        
        return asset
    
    async def get_session_assets(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        entity_tag: Optional[str] = None,
        asset_type: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 20,
    ) -> list[GeneratedAsset]:
        """
        Session'daki assetleri getir.
        
        Args:
            session_id: Oturum ID
            entity_tag: Belirli entity'ye ait olanlar (opsiyonel)
            asset_type: "image" veya "video" filtresi
            favorites_only: Sadece favoriler
            limit: Maksimum sayı
        
        Returns:
            list[GeneratedAsset]: Asset listesi
        """
        query = select(GeneratedAsset).where(
            GeneratedAsset.session_id == session_id
        )
        
        # Filtreler
        if asset_type:
            query = query.where(GeneratedAsset.asset_type == asset_type)
        
        if favorites_only:
            query = query.where(GeneratedAsset.is_favorite == True)
        
        # Entity filtresi
        if entity_tag:
            # Entity'yi bul
            entity_query = select(Entity).where(
                and_(
                    Entity.session_id == session_id,
                    Entity.tag == entity_tag
                )
            )
            entity_result = await db.execute(entity_query)
            entity = entity_result.scalar_one_or_none()
            
            if entity:
                # Bu entity'ye bağlı assetleri getir
                query = query.join(EntityAsset).where(
                    EntityAsset.entity_id == entity.id
                )
        
        # Sırala ve limitle
        query = query.order_by(desc(GeneratedAsset.created_at)).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def get_recent_assets(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        limit: int = 5,
    ) -> list[GeneratedAsset]:
        """Son N asset'i getir."""
        return await self.get_session_assets(db, session_id, limit=limit)
    
    async def get_asset_by_id(
        self,
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> Optional[GeneratedAsset]:
        """ID ile asset getir."""
        result = await db.execute(
            select(GeneratedAsset).where(GeneratedAsset.id == asset_id)
        )
        return result.scalar_one_or_none()
    
    async def mark_favorite(
        self,
        db: AsyncSession,
        asset_id: uuid.UUID,
        is_favorite: bool = True,
    ) -> Optional[GeneratedAsset]:
        """Asset'i favori olarak işaretle/kaldır."""
        asset = await self.get_asset_by_id(db, asset_id)
        
        if asset:
            asset.is_favorite = is_favorite
            await db.commit()
            await db.refresh(asset)
        
        return asset
    
    async def get_favorites(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
    ) -> list[GeneratedAsset]:
        """Session'daki favori assetleri getir."""
        return await self.get_session_assets(
            db, session_id, favorites_only=True, limit=100
        )
    
    async def get_asset_history(
        self,
        db: AsyncSession,
        asset_id: uuid.UUID,
    ) -> list[GeneratedAsset]:
        """
        Asset'in parent chain'ini getir (edit/upscale geçmişi).
        
        Returns:
            list: [current, parent, grandparent, ...] sırasında
        """
        history = []
        current_id = asset_id
        
        while current_id:
            asset = await self.get_asset_by_id(db, current_id)
            if asset:
                history.append(asset)
                current_id = asset.parent_asset_id
            else:
                break
        
        return history
    
    async def get_last_asset(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
    ) -> Optional[GeneratedAsset]:
        """Session'daki son asset'i getir."""
        assets = await self.get_session_assets(db, session_id, limit=1)
        return assets[0] if assets else None


# Singleton instance
asset_service = AssetService()
