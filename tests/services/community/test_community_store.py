# tests/services/community/test_community_store.py
# MIT License

import pytest
from unittest.mock import MagicMock, patch
from app.services.community.community_store import KiwiCommunityStore, get_or_create_pseudonym


def test_get_or_create_pseudonym_new_user():
    """First-time publish: creates a new pseudonym in per-user SQLite."""
    mock_store = MagicMock()
    mock_store.get_current_pseudonym.return_value = None
    result = get_or_create_pseudonym(
        store=mock_store,
        directus_user_id="user-123",
        requested_name="PastaWitch",
    )
    mock_store.set_pseudonym.assert_called_once_with("user-123", "PastaWitch")
    assert result == "PastaWitch"


def test_get_or_create_pseudonym_existing():
    """If user already has a pseudonym, return it without creating a new one."""
    mock_store = MagicMock()
    mock_store.get_current_pseudonym.return_value = "PastaWitch"
    result = get_or_create_pseudonym(
        store=mock_store,
        directus_user_id="user-123",
        requested_name=None,
    )
    mock_store.set_pseudonym.assert_not_called()
    assert result == "PastaWitch"


def test_kiwi_community_store_list_meal_plans():
    """KiwiCommunityStore.list_meal_plans filters by post_type='plan'."""
    mock_db = MagicMock()
    store = KiwiCommunityStore(mock_db)
    with patch.object(store, "list_posts", return_value=[]) as mock_list:
        result = store.list_meal_plans(limit=10)
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("post_type") == "plan"
