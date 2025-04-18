import pytest
from unittest.mock import MagicMock, patch
from sec_mcp.sec_mcp import SecMCP, CheckResult, StatusInfo

@pytest.fixture
def secmcp():
    with patch('sec_mcp.sec_mcp.Storage') as MockStorage:
        with patch('sec_mcp.sec_mcp.BlacklistUpdater'):
            yield SecMCP()

def test_check_blacklisted_and_safe(secmcp):
    # Mock storage behavior
    secmcp.storage.is_blacklisted.side_effect = lambda v: v == 'bad.com'
    secmcp.storage.get_blacklist_source.return_value = 'TestSource'

    result = secmcp.check('bad.com')
    assert isinstance(result, CheckResult)
    assert result.blacklisted is True
    assert 'TestSource' in result.explanation

    result2 = secmcp.check('good.com')
    assert isinstance(result2, CheckResult)
    assert result2.blacklisted is False
    assert 'Not blacklisted' in result2.explanation

def test_check_batch(secmcp):
    secmcp.storage.is_blacklisted.side_effect = lambda v: v == 'bad.com'
    secmcp.storage.get_blacklist_source.return_value = 'BatchSource'
    results = secmcp.check_batch(['bad.com', 'good.com'])
    assert len(results) == 2
    assert results[0].blacklisted is True
    assert results[1].blacklisted is False

def test_get_status(secmcp):
    secmcp.storage.count_entries.return_value = 42
    secmcp.storage.get_last_update.return_value = pytest.approx(1713465600, rel=1e-3)  # mock timestamp
    secmcp.storage.get_active_sources.return_value = ['S1', 'S2']
    status = secmcp.get_status()
    assert isinstance(status, StatusInfo)
    assert status.entry_count == 42
    assert isinstance(status.sources, list)
    assert status.server_status == 'Running (STDIO)'

def test_update_calls_updater(secmcp):
    secmcp.updater.force_update = MagicMock()
    secmcp.update()
    secmcp.updater.force_update.assert_called_once()

def test_sample_entries(secmcp):
    secmcp.storage.sample_entries.return_value = ['a', 'b']
    sample = secmcp.sample(2)
    assert sample == ['a', 'b']
