import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sec_mcp.update_blacklist import BlacklistUpdater
from sec_mcp.storage import Storage

@pytest.mark.asyncio
async def test_update_source_success():
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    async with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "https://malicious.com\nhttps://phishing.com"
        await updater._update_source(mock_get, "OpenPhish", "http://fake-url")
        assert storage.add_entries.called
        assert storage.log_update.called

@pytest.mark.asyncio
async def test_update_source_network_error():
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    async with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Network error")
        # Should not raise
        await updater._update_source(mock_get, "OpenPhish", "http://fake-url")
        # No entries should be added
        assert not storage.add_entries.called

# More tests can be added for CSV parsing and error logging
