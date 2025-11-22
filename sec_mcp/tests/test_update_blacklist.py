from unittest.mock import ANY, AsyncMock, MagicMock  # Added ANY

import pytest

from sec_mcp.storage import Storage
from sec_mcp.update_blacklist import BlacklistUpdater


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

    # Based on the test data and current parsing logic for PhishStats:
    # "https://malicious.com" (no path) -> add_domain("malicious.com"), add_ip("1.2.3.4")
    # "https://phishing.com" (no path) -> add_domain("phishing.com"), add_ip("2.2.2.2")
    assert storage.add_domain.call_count == 2
    assert storage.add_ip.call_count == 2
    assert storage.add_url.call_count == 0  # add_url is not called for domain-only entries

    storage.add_domain.assert_any_call("malicious.com", "2025-04-18T00:00:00", 9.0, "PhishStats")
    storage.add_ip.assert_any_call("1.2.3.4", "2025-04-18T00:00:00", 9.0, "PhishStats")

    # For the second entry, date is now_str (mocked by ANY) and score is default 8.0
    storage.add_domain.assert_any_call("phishing.com", ANY, 8.0, "PhishStats")
    storage.add_ip.assert_any_call("2.2.2.2", ANY, 8.0, "PhishStats")


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
    assert not storage.add_domain.called
    assert not storage.add_ip.called
    assert not storage.add_url.called


# More tests can be added for CSV parsing and error logging
