import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sec_mcp.update_blacklist import BlacklistUpdater
from sec_mcp.storage import Storage

@pytest.mark.asyncio
async def test_update_source_success():
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "url,ip,date,score\nhttps://malicious.com,1.2.3.4,2025-04-18T00:00:00,9.0\nhttps://phishing.com,2.2.2.2,,\n"
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    await updater._update_source(mock_client, "PhishStats", "http://fake-url")
    assert storage.add_entries.called
    assert storage.log_update.called
    # Check the structure of entries
    args, kwargs = storage.add_entries.call_args
    entries = args[0]
    assert all(len(e) == 4 for e in entries)
    assert entries[0][0] == "https://malicious.com"
    assert entries[0][1] == "1.2.3.4"
    assert entries[0][2] == "2025-04-18T00:00:00"
    assert entries[0][3] == 9.0
    # Second entry: no date/score provided, so should be filled in by update_blacklist logic

@pytest.mark.asyncio
async def test_update_source_network_error():
    storage = MagicMock(spec=Storage)
    updater = BlacklistUpdater(storage)
    mock_client = MagicMock()
    async def raise_exc(*args, **kwargs):
        raise Exception("Network error")
    mock_client.get = AsyncMock(side_effect=raise_exc)
    await updater._update_source(mock_client, "OpenPhish", "http://fake-url")
    # No entries should be added
    assert not storage.add_entries.called

# More tests can be added for CSV parsing and error logging
