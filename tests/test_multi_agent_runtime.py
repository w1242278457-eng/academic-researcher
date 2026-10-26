import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.academic.config import AcademicResearchConfig, build_academic_task
from multi_agents.agents.editor import EditorAgent
from multi_agents.agents.fact_checker import FactCheckerAgent
from multi_agents.agents.orchestrator import ChiefEditorAgent
from multi_agents.agents.reviewer import ReviewerAgent


@pytest.mark.parametrize('query', [
    build_academic_task('Compare TF-IDF and BM25', AcademicResearchConfig()),
    '[ACADEMIC PAPER RESEARCH]\nResearch question',
    'invalid: "file/name"? <topic> | * \\ \r\n\t\x00',
    'long query ' * 3000,
], ids=['academic-prompt', 'multiline-prompt', 'windows-characters', 'long-prompt'])
def test_output_directory_supports_multiline_and_invalid_windows_characters(tmp_path, monkeypatch, query):
    monkeypatch.chdir(tmp_path)
    agent = ChiefEditorAgent({'query': query})
    folder = Path(agent.output_dir).resolve()
    assert folder.is_dir()
    assert folder.parent == tmp_path / 'outputs'
    assert folder.name == 'run_' + agent.task_id


def test_repeated_queries_have_isolated_output_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = ChiefEditorAgent({'query': 'same query'})
    second = ChiefEditorAgent({'query': 'same query'})
    assert first.output_dir != second.output_dir


@pytest.mark.parametrize('response,accepted', [
    (' None ', True), ('None of the citations support this claim', False),
    ('', False), (None, False),
])
def test_chapter_review_requires_explicit_acceptance(monkeypatch, response, accepted):
    monkeypatch.setattr('multi_agents.agents.reviewer.call_model', AsyncMock(return_value=response))
    state = {'task': {'model': 'test-model', 'guidelines': [], 'verbose': False}, 'draft': {}}
    review = asyncio.run(ReviewerAgent().review_draft(state))
    assert (review is None) is accepted


def test_invalid_fact_check_is_not_accepted_and_stops_at_limit(monkeypatch):
    agent = FactCheckerAgent()
    monkeypatch.setattr(agent, 'check_facts', AsyncMock(return_value=None))
    result = asyncio.run(agent.run({'fact_check_count': 2}))
    assert result['fact_check_notes']
    assert result['fact_check_count'] == 3
    chief = ChiefEditorAgent.__new__(ChiefEditorAgent)
    chief.task = {'max_fact_checks': 3}
    with pytest.raises(RuntimeError, match='Fact-check limit'):
        chief._route_fact_check(result)


def test_unresolved_section_review_stops_at_revision_limit():
    with pytest.raises(RuntimeError, match='Section review limit'):
        EditorAgent._route_review({'review': 'Fix citations', 'revision_count': 2,
                                  'task': {'max_section_revisions': 2}})
