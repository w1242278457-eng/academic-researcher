import unittest

from backend.academic import AcademicResearchConfig, build_academic_task


class AcademicConfigTests(unittest.TestCase):
    def test_invalid_values_fall_back_to_safe_defaults(self):
        config = AcademicResearchConfig.from_mapping({
            "research_type": "unknown",
            "evidence_standard": "unknown",
            "citation_style": "unknown",
            "year_from": "not-a-year",
        })
        self.assertEqual(config.research_type, "literature_review")
        self.assertEqual(config.evidence_standard, "peer_reviewed")
        self.assertEqual(config.citation_style, "APA 7")
        self.assertIsNone(config.year_from)

    def test_task_contains_academic_constraints(self):
        config = AcademicResearchConfig.from_mapping({"year_from": 2020, "citation_style": "IEEE"})
        task = build_academic_task("LLM evaluation", config)
        self.assertIn("Research question: LLM evaluation", task)
        self.assertIn("since 2020", task)
        self.assertIn("IEEE bibliography", task)
        self.assertIn("do not fabricate", task)


if __name__ == "__main__":
    unittest.main()
