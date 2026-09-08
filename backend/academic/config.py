"""Academic research request validation and prompt adaptation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

ALLOWED_TYPES = {"literature_review", "state_of_art", "method_comparison", "research_gaps", "reproduction", "topic_selection"}
ALLOWED_STANDARDS = {"peer_reviewed", "highly_cited", "recent", "preprints_allowed", "web_allowed"}
ALLOWED_CITATION_STYLES = {"APA 7", "MLA", "Chicago", "IEEE"}


@dataclass(frozen=True)
class AcademicResearchConfig:
    domain: str = "computer_science"
    research_type: str = "literature_review"
    evidence_standard: str = "peer_reviewed"
    year_from: int | None = None
    citation_style: str = "APA 7"
    include_research_gaps: bool = True
    include_comparison_matrix: bool = True
    include_bibliography: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "AcademicResearchConfig":
        value = value or {}
        raw_year = value.get("year_from")
        try:
            year = int(raw_year) if raw_year not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            year = None
        if year is not None:
            year = max(1900, min(year, datetime.now().year))
        research_type = str(value.get("research_type", cls.research_type))
        standard = str(value.get("evidence_standard", cls.evidence_standard))
        citation = str(value.get("citation_style", cls.citation_style))
        return cls(
            domain=str(value.get("domain", cls.domain)).strip() or cls.domain,
            research_type=research_type if research_type in ALLOWED_TYPES else cls.research_type,
            evidence_standard=standard if standard in ALLOWED_STANDARDS else cls.evidence_standard,
            year_from=year,
            citation_style=citation if citation in ALLOWED_CITATION_STYLES else cls.citation_style,
            include_research_gaps=bool(value.get("include_research_gaps", True)),
            include_comparison_matrix=bool(value.get("include_comparison_matrix", True)),
            include_bibliography=bool(value.get("include_bibliography", True)),
        )


def build_academic_task(task: str, config: AcademicResearchConfig | Mapping[str, Any] | None) -> str:
    """Turn a free-form question into an explicit academic research brief."""
    if not isinstance(config, AcademicResearchConfig):
        config = AcademicResearchConfig.from_mapping(config)
    year_rule = f"Prioritize papers published since {config.year_from}." if config.year_from else "No year limit; always include publication years."
    outputs = ["provide verifiable, source-linked claims"]
    if config.include_research_gaps:
        outputs.append("identify evidence-backed research gaps")
    if config.include_comparison_matrix:
        outputs.append("compare methods, datasets, metrics, strengths, and limitations")
    if config.include_bibliography:
        outputs.append(f"generate a {config.citation_style} bibliography")
    return (
        "[ACADEMIC PAPER RESEARCH]\n"
        f"Research question: {task}\nDomain: {config.domain}\n"
        f"Research type: {config.research_type}\n"
        f"Evidence standard: {config.evidence_standard}; {year_rule}\n"
        f"Required outputs: {'; '.join(outputs)}.\n"
        "Academic rules: do not fabricate papers, authors, DOIs, or results; distinguish "
        "peer-reviewed papers, preprints, and web sources; attach sources to important claims; "
        "state evidence strength; separate source statements from inference."
    )
