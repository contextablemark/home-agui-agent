"""Pytest configuration for AG-UI Agent tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


def pytest_configure(config: Any) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_llm_api() -> MagicMock:
    """Create a mock LLM API instance."""
    api = MagicMock()
    api.tools = []
    return api
