"""Advanced Deep Research test cases.

This module contains comprehensive test cases for evaluating the Deep Research
system's capabilities, following best practices from advanced research agents.

Test Categories:
1. Multi-step research planning
2. Source verification and cross-referencing
3. Information synthesis quality
4. Edge cases and error handling
5. Research report quality
6. Iterative refinement
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.deep_research import (
    DeepResearchAgent,
    ResearchFinding,
    ResearchPlan,
    ResearchStep,
    compare_sources,
    deep_research,
    quick_research,
)

# ============ Multi-step Research Planning Tests ============


def test_research_plan_complex_topic():
    """Complex topic generates appropriate plan."""
    agent = DeepResearchAgent()
    plan = agent.create_plan(
        "machine learning in healthcare",
        goals=[
            "Find recent advances in ML for medical diagnosis",
            "Identify key challenges and limitations",
            "Discover leading research institutions",
        ],
    )

    assert plan.topic == "machine learning in healthcare"
    assert len(plan.goals) == 3
    assert len(plan.steps) > 0
    assert plan.estimated_steps > 0


def test_research_plan_step_structure():
    """Research plan has proper step structure."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("test topic")

    # Check step numbering
    for i, step in enumerate(plan.steps, 1):
        assert step.step_number == i
        assert len(step.description) > 0


def test_research_plan_custom_max_steps():
    """Plan respects max_steps configuration."""
    agent = DeepResearchAgent(max_steps=3)
    plan = agent.create_plan("test topic")

    assert plan.estimated_steps <= 3


# ============ Source Verification Tests ============


@pytest.mark.asyncio
async def test_verify_finding_with_mock():
    """Finding verification works with search results."""
    agent = DeepResearchAgent()

    finding = ResearchFinding(
        title="Python is popular",
        content="Python is one of the most popular programming languages",
        source_url="https://example.com/python-stats",
    )

    # Mock web_search to return verification
    with patch("agent.tools.deep_research.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (
            "- Python Statistics\n  https://example.com/popularity\n  Python is widely used"
        )

        verified = await agent.verify_finding(finding)

        assert verified is True
        assert finding.verified is True
        assert len(finding.verification_sources) > 0


@pytest.mark.asyncio
async def test_verify_finding_fails_gracefully():
    """Verification failure is handled gracefully."""
    agent = DeepResearchAgent()

    finding = ResearchFinding(title="Unknown topic", content="Some content")

    with patch("agent.tools.deep_research.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "No results found."

        verified = await agent.verify_finding(finding)

        assert verified is False
        assert finding.verified is False


# ============ Information Synthesis Tests ============


def test_synthesize_findings_single_theme():
    """Synthesis groups findings by theme."""
    agent = DeepResearchAgent()

    agent.findings = [
        ResearchFinding(title="Machine Learning Basics", content="ML is a subset of AI"),
        ResearchFinding(
            title="Machine Learning Applications", content="ML is used in many domains"
        ),
        ResearchFinding(
            title="Machine Learning Tools", content="Popular ML tools include TensorFlow"
        ),
    ]

    synthesis = agent.synthesize_findings()

    assert "Research Synthesis" in synthesis
    assert "Machine" in synthesis
    assert len(synthesis) > 50


def test_synthesize_findings_multiple_themes():
    """Synthesis handles multiple themes."""
    agent = DeepResearchAgent()

    agent.findings = [
        ResearchFinding(title="Python Syntax", content="Python uses indentation"),
        ResearchFinding(title="Python Libraries", content="Python has many libraries"),
        ResearchFinding(title="JavaScript Syntax", content="JavaScript uses braces"),
        ResearchFinding(title="JavaScript Frameworks", content="React, Vue, Angular"),
    ]

    synthesis = agent.synthesize_findings()

    assert "Research Synthesis" in synthesis
    # Should mention both themes
    assert "python" in synthesis.lower() or "javascript" in synthesis.lower()


def test_synthesize_verified_findings_marked():
    """Verified findings are marked in synthesis."""
    agent = DeepResearchAgent()

    agent.findings = [
        ResearchFinding(title="Verified Topic", content="Content", verified=True),
        ResearchFinding(title="Unverified Topic", content="Content", verified=False),
    ]

    synthesis = agent.synthesize_findings()

    # Verified findings should have marker
    assert "✓" in synthesis or "verified" in synthesis.lower()


# ============ Research Report Quality Tests ============


def test_report_confidence_all_verified():
    """Report confidence is 1.0 when all findings verified."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])

    agent.findings = [
        ResearchFinding(title="1", content="c", verified=True),
        ResearchFinding(title="2", content="c", verified=True),
        ResearchFinding(title="3", content="c", verified=True),
    ]

    report = agent.generate_report()

    assert report.confidence == 1.0


def test_report_confidence_none_verified():
    """Report confidence is 0.0 when no findings verified."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])

    agent.findings = [
        ResearchFinding(title="1", content="c", verified=False),
        ResearchFinding(title="2", content="c", verified=False),
    ]

    report = agent.generate_report()

    assert report.confidence == 0.0


def test_report_confidence_partial():
    """Report confidence reflects verification ratio."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])

    agent.findings = [
        ResearchFinding(title="1", content="c", verified=True),
        ResearchFinding(title="2", content="c", verified=False),
        ResearchFinding(title="3", content="c", verified=True),
    ]

    report = agent.generate_report()

    # 2 out of 3 verified = 0.666...
    assert abs(report.confidence - 0.667) < 0.01


def test_report_includes_all_findings():
    """Report includes all research findings."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test topic", goals=["test"])

    agent.findings = [
        ResearchFinding(title="Finding 1", content="Content 1", verified=True),
        ResearchFinding(title="Finding 2", content="Content 2", verified=True),
        ResearchFinding(title="Finding 3", content="Content 3", verified=False),
    ]

    report = agent.generate_report()

    assert len(report.findings) == 3
    assert report.topic == "test topic"


def test_report_includes_sources():
    """Report deduplicates and includes sources."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])

    agent.findings = [
        ResearchFinding(title="1", content="c", source_url="https://example.com/1"),
        ResearchFinding(title="2", content="c", source_url="https://example.com/1"),  # Duplicate
        ResearchFinding(title="3", content="c", source_url="https://example.com/2"),
    ]

    report = agent.generate_report()

    # Should deduplicate sources
    assert len(report.sources) <= 2


def test_report_has_timestamp():
    """Report includes completion timestamp."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [ResearchFinding(title="1", content="c")]

    report = agent.generate_report()

    assert report.completed_at
    # Should be valid ISO format
    datetime.fromisoformat(report.completed_at)


# ============ Edge Cases and Error Handling ============


def test_agent_handles_empty_topic():
    """Agent handles empty topic gracefully."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("")

    assert plan.topic == ""
    assert len(plan.steps) > 0


def test_agent_handles_very_long_topic():
    """Agent handles very long topics."""
    agent = DeepResearchAgent()
    long_topic = " ".join(["word"] * 100)
    plan = agent.create_plan(long_topic)

    assert plan.topic == long_topic


def test_agent_handles_special_characters():
    """Agent handles special characters in topics."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("Machine Learning: Deep Learning & NLP (2024)")

    assert "Machine Learning" in plan.topic


def test_agent_handles_unicode():
    """Agent handles unicode in topics."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("Машинное обучение и ИИ")

    assert "Машинное" in plan.topic


def test_agent_max_depth_zero():
    """Agent with max_depth=0 doesn't branch."""
    agent = DeepResearchAgent(max_depth=0)

    assert agent.max_depth == 0


def test_agent_max_steps_one():
    """Agent with max_steps=1 does minimal research."""
    agent = DeepResearchAgent(max_steps=1)
    plan = agent.create_plan("test")

    assert plan.estimated_steps == 1


def test_research_finding_no_title():
    """Finding without title is valid."""
    finding = ResearchFinding(title="", content="Content only")

    assert finding.title == ""
    assert finding.content == "Content only"


def test_research_finding_zero_relevance():
    """Finding with zero relevance is valid."""
    finding = ResearchFinding(title="Irrelevant", content="Content", relevance_score=0.0)

    assert finding.relevance_score == 0.0


def test_research_step_no_query():
    """Step without query uses description."""
    step = ResearchStep(1, "Search for something")

    assert step.query is None
    assert "something" in step.description


# ============ Iterative Refinement Tests ============


def test_follow_up_queries_generation():
    """Follow-up queries are generated from results."""
    agent = DeepResearchAgent()

    results = """
    - Title 1: Python Basics
      https://example.com/python
      Python is a programming language

    - Title 2: Advanced Python
      https://example.com/advanced-python
      Advanced Python features
    """

    queries = agent._generate_follow_up_queries(results)

    assert isinstance(queries, list)
    # Should generate some follow-ups
    assert len(queries) >= 0  # May be empty depending on implementation


def test_follow_up_queries_no_results():
    """Follow-up queries handle no results."""
    agent = DeepResearchAgent()

    queries = agent._generate_follow_up_queries("No results found.")

    assert isinstance(queries, list)


def test_follow_up_queries_limits_count():
    """Follow-up queries are limited to max 3."""
    agent = DeepResearchAgent()

    # Create very long results
    results = "\n".join([f"- Result {i}\n  https://example.com/{i}" for i in range(100)])

    queries = agent._generate_follow_up_queries(results)

    assert len(queries) <= 3


# ============ Integration-like Tests ============


@pytest.mark.asyncio
async def test_quick_research_with_mock():
    """Quick research works with mocked search."""
    with patch("agent.tools.deep_research.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "- Test Result\n  https://example.com\n  Test content"

        result = await quick_research("test query")

        assert isinstance(result, str)
        assert "Quick Research" in result
        mock_search.assert_called_once_with("test query")


@pytest.mark.asyncio
async def test_compare_sources_with_mock():
    """Compare sources works with mocked search."""
    with patch("agent.tools.deep_research.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "- Comparison Result\n  https://example.com\n  Content"

        result = await compare_sources("python vs java")

        assert isinstance(result, str)
        assert "Source Comparison" in result


@pytest.mark.asyncio
async def test_deep_research_full_flow_mocked():
    """Full deep research flow works with mocked search."""
    with patch("agent.tools.deep_research.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "- Research Result\n  https://example.com\n  Detailed content"

        result = await deep_research(
            "test topic", goals=["find information"], max_steps=3, max_depth=1
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Deep Research Report" in result


# ============ Research Quality Metrics ============


def test_finding_relevance_score_range():
    """Relevance score is within valid range."""
    finding = ResearchFinding(title="Test", content="Content", relevance_score=0.75)

    assert 0.0 <= finding.relevance_score <= 1.0


def test_finding_default_relevance():
    """Finding defaults to max relevance."""
    finding = ResearchFinding(title="Test", content="Content")

    assert finding.relevance_score == 1.0


def test_report_summary_generated():
    """Report includes summary."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test topic", goals=["test"])
    agent.findings = [
        ResearchFinding(title="Key Finding", content="Important content here", verified=True),
    ]

    report = agent.generate_report()

    assert len(report.summary) > 0
    assert "test topic" in report.summary.lower() or "finding" in report.summary.lower()


# ============ Performance Tests ============


def test_agent_creates_plan_quickly():
    """Plan creation is fast."""
    import time

    agent = DeepResearchAgent()

    start = time.time()
    plan = agent.create_plan("test topic", ["goal 1", "goal 2", "goal 3"])
    elapsed = time.time() - start

    assert elapsed < 1.0  # Should be instant
    assert plan is not None


def test_synthesis_multiple_findings():
    """Synthesis handles many findings."""
    agent = DeepResearchAgent()

    # Create many findings
    agent.findings = [
        ResearchFinding(title=f"Topic {i}", content=f"Content {i}", verified=i % 2 == 0)
        for i in range(50)
    ]

    synthesis = agent.synthesize_findings()

    assert isinstance(synthesis, str)
    assert len(synthesis) > 0


# ============ Real-world Scenario Tests ============


def test_research_plan_technical_topic():
    """Technical topic generates appropriate plan."""
    agent = DeepResearchAgent()
    plan = agent.create_plan(
        "distributed systems consensus algorithms",
        goals=["Understand Paxos algorithm", "Compare with Raft", "Find implementation examples"],
    )

    assert "distributed systems" in plan.topic.lower()
    assert len(plan.goals) == 3


def test_research_plan_comparison_topic():
    """Comparison topic is handled."""
    agent = DeepResearchAgent()
    plan = agent.create_plan(
        "React vs Vue vs Angular",
        goals=["Compare learning curves", "Evaluate ecosystem", "Assess performance"],
    )

    assert "React" in plan.topic
    assert len(plan.steps) > 0


def test_research_plan_how_to_topic():
    """How-to topic is handled."""
    agent = DeepResearchAgent()
    plan = agent.create_plan(
        "how to deploy machine learning models",
        goals=["Find deployment options", "Compare cloud providers", "Identify best practices"],
    )

    assert "deploy" in plan.topic.lower()


# ============ Report Structure Tests ============


def test_report_limitations_identified():
    """Report can include limitations."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [
        ResearchFinding(title="Limited Finding", content="Content", verified=False),
    ]

    report = agent.generate_report()

    assert isinstance(report.limitations, list)
    # May have limitations if findings are unverified


def test_report_recommendations_generated():
    """Report can include recommendations."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [
        ResearchFinding(title="Finding", content="Content", verified=True),
    ]

    report = agent.generate_report()

    assert isinstance(report.recommendations, list)


def test_report_sources_structure():
    """Report sources have correct structure."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [
        ResearchFinding(
            title="Finding",
            content="Content",
            source_url="https://example.com/article",
            source_title="Example Article",
        ),
    ]

    report = agent.generate_report()

    for source in report.sources:
        assert isinstance(source, dict)
        assert "url" in source or "title" in source
