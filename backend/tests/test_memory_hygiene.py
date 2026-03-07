import os
import uuid

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.services.conversation_memory_service import ConversationMemoryService
from app.services.episodic_memory_service import EpisodicMemoryService
from app.services.preferences_service import PreferencesService


@pytest.mark.asyncio
async def test_preferences_prompt_excludes_transient_learned_memory(monkeypatch):
    service = PreferencesService()

    async def fake_get_preferences(db, user_id):
        return {
            "aspect_ratio": "16:9",
            "style": "realistic",
            "image_model": "nano_banana",
            "video_model": "veo",
            "video_duration": 5,
            "auto_face_swap": True,
            "auto_upscale": False,
            "auto_translate": True,
            "language": "tr",
            "favorite_entities": [],
            "learned": {
                "workflow": ["Once plani yaz, sonra uretime gec"],
                "general": ["Kullanici 5 saniyelik video istiyor"],
                "brand": ["Veo ile uret"],
            },
        }

    monkeypatch.setattr(service, "get_preferences", fake_get_preferences)

    prompt = await service.get_preferences_for_prompt(db=None, user_id=uuid.uuid4())

    assert "Once plani yaz, sonra uretime gec" in prompt
    assert "5 saniyelik" not in prompt
    assert "Veo ile uret" not in prompt


@pytest.mark.asyncio
async def test_find_similar_prompts_ignores_conflicting_duration():
    service = ConversationMemoryService()
    user_id = uuid.uuid4()

    async def fake_get_user_memory(_user_id):
        return {
            "successful_prompts": [
                {
                    "prompt": "5 saniyelik sinematik kedi videosu olustur",
                    "score": 1,
                    "asset_type": "video",
                },
                {
                    "prompt": "Sinematik kedi videosu, altin saat isigi, yumusak kamera hareketi",
                    "score": 1,
                    "asset_type": "video",
                },
            ]
        }

    service.get_user_memory = fake_get_user_memory

    similar = await service.find_similar_prompts(user_id, "30 saniyelik kedi videosu olustur", limit=3)

    assert len(similar) == 1
    assert similar[0]["prompt"] == "Sinematik kedi videosu, altin saat isigi, yumusak kamera hareketi"
    assert "5 saniyelik" not in similar[0]["memory_prompt"]


@pytest.mark.asyncio
async def test_build_memory_context_filters_transient_prompt_like_memory():
    service = ConversationMemoryService()

    async def fake_get_user_memory(_user_id):
        return {
            "summaries": [
                {"summary": "Bu projede 5 saniyelik kedi videosu denendi, kullanici daha sinematik atmosfer istedi."}
            ],
            "preferences": {"video_duration": "5"},
            "successful_prompts": [
                {"prompt": "5 saniyelik kedi videosu"}
            ],
            "style_preferences": {"active_style": "cinematic", "temporary_duration": "5 saniye"},
            "core_memories": [
                {"category": "workflow", "fact": "Once plani yaz, sonra uretime gec"},
                {"category": "general", "fact": "Kullanici 5 saniyelik videolari seviyor"},
            ],
        }

    service.get_user_memory = fake_get_user_memory

    context = await service.build_memory_context(uuid.uuid4())

    assert "Once plani yaz, sonra uretime gec" in context
    assert "5 saniyelik" not in context
    assert "⭐ BAŞARILI PROMPTLAR" not in context
    assert "temporary_duration" not in context


@pytest.mark.asyncio
async def test_episodic_memory_context_skips_model_success_and_transient_feedback():
    service = EpisodicMemoryService()
    user_id = str(uuid.uuid4())

    await service.remember(
        user_id=user_id,
        event_type="model_success",
        content="kling modeli ile 5 saniyelik kedi videosu basarili oldu",
    )
    await service.remember(
        user_id=user_id,
        event_type="feedback",
        content="Yanlis stil kullanildi",
    )
    await service.remember(
        user_id=user_id,
        event_type="feedback",
        content="Kullanici 5 saniyelik video sevdi",
    )

    context = await service.get_context_for_prompt(user_id)

    assert "Yanlis stil kullanildi" in context
    assert "kling" not in context
    assert "5 saniyelik" not in context
