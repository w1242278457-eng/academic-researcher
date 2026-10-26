import hashlib

import pytest

from backend.server.report_context import resolve_report_context


@pytest.fixture
def reports(tmp_path):
    outputs = tmp_path / 'outputs'
    outputs.mkdir()
    (outputs / 'selected.md').write_text('# Selected report\nBM25 evidence.', encoding='utf-8')
    (outputs / 'other.md').write_text('# Another report', encoding='utf-8')
    return tmp_path


def test_selected_report_overrides_stale_client_and_connection(reports):
    text, meta = resolve_report_context(
        {'report_path': '/outputs/selected.md', 'report': 'stale client body'},
        reports, {'report': 'another connection report'},
    )
    assert text == '# Selected report\nBM25 evidence.'
    assert meta == {
        'source': 'saved_markdown', 'report_id': 'selected', 'characters': len(text),
        'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
    }


def test_explicit_report_id(reports):
    text, meta = resolve_report_context({'report_id': 'selected'}, reports)
    assert 'BM25' in text
    assert meta['report_id'] == 'selected'


@pytest.mark.parametrize('reference', [
    'outputs/../secret.md', 'outputs/%2e%2e/secret.md',
    'outputs/..\\secret.md', 'https://example.com/report.md',
    'outputs/secret.env', 'outputs/missing.md', 42,
])
def test_invalid_reference_does_not_fall_back_to_supplied_report(reports, reference):
    with pytest.raises(ValueError):
        resolve_report_context({'report_path': reference, 'report': 'fallback'}, reports)


def test_empty_request_never_chooses_another_saved_report(reports):
    with pytest.raises(ValueError):
        resolve_report_context({'message': 'Summarize'}, reports)


def test_legacy_body_and_same_connection_are_supported(reports):
    text, meta = resolve_report_context({'report': 'explicit report'}, reports,
                                        {'report': 'connection report'})
    assert text == 'explicit report'
    assert meta['source'] == 'request_body'
    text, meta = resolve_report_context({}, reports,
                                        {'report': 'connection report', 'report_id': 'bound'})
    assert text == 'connection report'
    assert meta['source'] == 'same_connection'
    assert meta['report_id'] == 'bound'
