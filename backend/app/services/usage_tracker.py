"""
Model Kullanım Geçmişi Tracking Servisi.
Her AI model çağrısını UsageStats tablosuna kaydeder.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import UsageStats


async def log_model_usage(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    model_name: str,
    usage_type: str = "image",  # image, video, audio, llm
) -> None:
    """
    Bir model kullanımını logla.
    Bugünün kaydı varsa güncelle, yoksa yeni oluştur.
    """
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Bugünkü kayıt var mı?
        result = await db.execute(
            select(UsageStats).where(
                UsageStats.user_id == user_id,
                UsageStats.model_name == model_name,
                UsageStats.date >= today_start,
            )
        )
        stats = result.scalar_one_or_none()

        if stats:
            # Güncelle
            stats.api_calls += 1
            if usage_type == "image":
                stats.images_generated += 1
            elif usage_type == "video":
                stats.videos_generated += 1
        else:
            # Yeni kayıt
            stats = UsageStats(
                user_id=user_id,
                model_name=model_name,
                api_calls=1,
                images_generated=1 if usage_type == "image" else 0,
                videos_generated=1 if usage_type == "video" else 0,
                tokens_used=0,
            )
            db.add(stats)

        await db.commit()
    except Exception as e:
        # Loglama hatası ana işlemi bozmamalı
        print(f"⚠️ Kullanım logu yazılamadı: {e}")
        await db.rollback()


async def get_usage_summary(db: AsyncSession, user_id: uuid.UUID | None) -> dict:
    """Kullanıcının toplam kullanım özetini döndür."""
    try:
        result = await db.execute(
            select(
                sa_func.sum(UsageStats.api_calls).label("total_calls"),
                sa_func.sum(UsageStats.images_generated).label("total_images"),
                sa_func.sum(UsageStats.videos_generated).label("total_videos"),
            ).where(UsageStats.user_id == user_id)
        )
        row = result.one()
        return {
            "total_api_calls": row.total_calls or 0,
            "total_images": row.total_images or 0,
            "total_videos": row.total_videos or 0,
        }
    except Exception:
        return {"total_api_calls": 0, "total_images": 0, "total_videos": 0}


async def get_model_breakdown(db: AsyncSession, user_id: uuid.UUID | None) -> list[dict]:
    """Hangi modelin ne kadar kullanıldığının dağılımını döndür."""
    try:
        result = await db.execute(
            select(
                UsageStats.model_name,
                sa_func.sum(UsageStats.api_calls).label("calls"),
                sa_func.sum(UsageStats.images_generated).label("images"),
                sa_func.sum(UsageStats.videos_generated).label("videos"),
            )
            .where(UsageStats.user_id == user_id)
            .group_by(UsageStats.model_name)
            .order_by(sa_func.sum(UsageStats.api_calls).desc())
        )
        return [
            {
                "model": row.model_name,
                "calls": row.calls or 0,
                "images": row.images or 0,
                "videos": row.videos or 0,
            }
            for row in result
        ]
    except Exception:
        return []
