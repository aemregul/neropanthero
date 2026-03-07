from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.stats_service import StatsService


@pytest.mark.asyncio
async def test_get_or_create_today_stats_uses_first_aggregate_row_when_duplicates_exist():
    older = SimpleNamespace(
        id="older",
        model_name=None,
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    newer = SimpleNamespace(
        id="newer",
        model_name=None,
        created_at=datetime.now(UTC),
    )

    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(first=lambda: newer)
    )

    db = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        add=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    stats = await StatsService.get_or_create_today_stats(db=db, user_id=None)

    assert stats is newer
    db.add.assert_not_called()
    executed_query = db.execute.await_args.args[0]
    assert "usage_stats.model_name IS NULL" in str(executed_query)
