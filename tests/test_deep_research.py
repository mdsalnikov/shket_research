"""Tests for Deep Research system."""

import pytest
from pathlib import Path
from datetime import datetime

from agent.tools.deep_research import (
    ResearchStep,
    ResearchPlan,
    ResearchFinding,
    ResearchReport,
    DeepResearchAgent,
    deep_research,
    quick_research,
    compare_sources,
)


# ============ Dataclass Tests ============

def test_research_step():
    """ResearchStep dataclass works correctly."""
    step = ResearchStep(
        step_number=1,
        description="Initial search",
        query="test query",
        findings="Some findings",
        sources=["http://example.com"],
        completed=True
    )
    
    assert step.step_number == 1
    assert step.completed is True
    assert len(step.sources) == 1


def test_research_plan():
    """ResearchPlan dataclass works correctly."""
    plan = ResearchPlan(
        topic="test topic",
        goals=["goal 1", "goal 2"],
        estimated_steps=5
    )
    
    assert plan.topic == "test topic"
    assert len(plan.goals) == 2
    assert plan.estimated_steps == 5


def test_research_finding():
    """ResearchFinding dataclass works correctly."""
    finding = ResearchFinding(
        title="Test Finding",
        content="Test content",
        source_url="http://example.com",
        source_title="Example",
        relevance_score=0.9,
        verified=True
    )
    
    assert finding.title == "Test Finding"
    assert finding.verified is True
    assert finding.relevance_score == 0.9


def test_research_report():
    """ResearchReport dataclass works correctly."""
    report = ResearchReport(
        topic="test topic",
        summary="Test summary",
        confidence=0.8,
        completed_at=datetime.now().isoformat()
    )
    
    assert report.topic == "test topic"
    assert report.confidence == 0.8
    assert report.completed_at


# ============ DeepResearchAgent Tests ============

def test_agent_create_plan():
    """Agent creates research plan correctly."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("test topic", ["goal 1"])
    
    assert plan.topic == "test topic"
    assert len(plan.steps) > 0
    assert len(plan.goals) >= 1


def test_agent_create_plan_default_goals():
    """Agent creates plan with default goals."""
    agent = DeepResearchAgent()
    plan = agent.create_plan("test topic")
    
    assert len(plan.goals) > 0
    assert "test topic" in plan.goals[0].lower()


def test_agent_step_execution():
    """Agent step has correct structure."""
    agent = DeepResearchAgent()
    step = ResearchStep(1, "Test step", query="test")
    
    assert step.step_number == 1
    assert not step.completed


def test_agent_follow_up_queries():
    """Agent generates follow-up queries."""
    agent = DeepResearchAgent()
    
    # Test with normal results
    results = "- Title 1\n  http://example.com\n  Some content"
    queries = agent._generate_follow_up_queries(results)
    
    assert isinstance(queries, list)
    
    # Test with no results
    no_results = "No results found."
    queries = agent._generate_follow_up_queries(no_results)
    
    assert isinstance(queries, list)


def test_agent_synthesize_findings():
    """Agent synthesizes findings."""
    agent = DeepResearchAgent()
    
    # Add some findings
    agent.findings = [
        ResearchFinding(title="Machine Learning", content="ML content"),
        ResearchFinding(title="Deep Learning", content="DL content"),
    ]
    
    synthesis = agent.synthesize_findings()
    
    assert isinstance(synthesis, str)
    assert len(synthesis) > 0
    assert "Research Synthesis" in synthesis


def test_agent_synthesize_no_findings():
    """Agent handles no findings."""
    agent = DeepResearchAgent()
    
    synthesis = agent.synthesize_findings()
    
    assert "No findings" in synthesis


def test_agent_generate_report():
    """Agent generates report."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [
        ResearchFinding(title="Test", content="Test content", verified=True),
        ResearchFinding(title="Test 2", content="Test content 2", verified=False),
    ]
    
    report = agent.generate_report()
    
    assert report.topic == "test"
    assert len(report.findings) == 2
    assert 0.0 <= report.confidence <= 1.0


def test_agent_generate_report_no_plan():
    """Agent raises error when no plan exists."""
    agent = DeepResearchAgent()
    
    with pytest.raises(ValueError):
        agent.generate_report()


# ============ Async Tool Tests ============

@pytest.mark.asyncio
async def test_quick_research():
    """Quick research returns results."""
    result = await quick_research("python programming")
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Quick Research" in result


@pytest.mark.asyncio
async def test_quick_research_error_handling():
    """Quick research handles errors gracefully."""
    # This should not crash even if search fails
    result = await quick_research("test query")
    
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_compare_sources():
    """Compare sources returns comparison."""
    result = await compare_sources("python vs javascript")
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Source Comparison" in result


# ============ Integration Tests ============

@pytest.mark.asyncio
async def test_deep_research_basic():
    """Deep research completes successfully."""
    result = await deep_research(
        "python programming",
        goals=["find basics"],
        max_steps=3,
        max_depth=1
    )
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Deep Research Report" in result


@pytest.mark.asyncio
async def test_deep_research_with_goals():
    """Deep research uses provided goals."""
    result = await deep_research(
        "machine learning",
        goals=["find latest trends", "identify key players"],
        max_steps=3,
        max_depth=1
    )
    
    assert isinstance(result, str)
    assert "machine learning" in result.lower()


@pytest.mark.asyncio
async def test_deep_research_limited_steps():
    """Deep research respects step limit."""
    result = await deep_research(
        "test topic",
        max_steps=2,
        max_depth=1
    )
    
    assert isinstance(result, str)


# ============ Edge Cases ============

def test_research_step_empty():
    """Empty research step is valid."""
    step = ResearchStep(1, "")
    
    assert step.step_number == 1
    assert step.description == ""


def test_research_finding_no_source():
    """Finding without source is valid."""
    finding = ResearchFinding(
        title="Test",
        content="Content"
    )
    
    assert finding.source_url == ""
    assert finding.verified is False


def test_agent_max_depth():
    """Agent respects max depth."""
    agent = DeepResearchAgent(max_depth=1)
    
    assert agent.max_depth == 1


def test_agent_max_steps():
    """Agent respects max steps."""
    agent = DeepResearchAgent(max_steps=5)
    
    assert agent.max_steps == 5


# ============ Report Generation Tests ============

def test_report_confidence_calculation():
    """Report confidence is calculated correctly."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    
    # All verified
    agent.findings = [
        ResearchFinding(title="1", content="c", verified=True),
        ResearchFinding(title="2", content="c", verified=True),
    ]
    report = agent.generate_report()
    assert report.confidence == 1.0
    
    # None verified
    agent.findings = [
        ResearchFinding(title="1", content="c", verified=False),
        ResearchFinding(title="2", content="c", verified=False),
    ]
    report = agent.generate_report()
    assert report.confidence == 0.0
    
    # Mixed
    agent.findings = [
        ResearchFinding(title="1", content="c", verified=True),
        ResearchFinding(title="2", content="c", verified=False),
    ]
    report = agent.generate_report()
    assert report.confidence == 0.5


def test_report_source_deduplication():
    """Report deduplicates sources."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    
    agent.findings = [
        ResearchFinding(title="1", content="c", source_url="http://example.com"),
        ResearchFinding(title="2", content="c", source_url="http://example.com"),  # Duplicate
        ResearchFinding(title="3", content="c", source_url="http://other.com"),
    ]
    
    report = agent.generate_report()
    
    # Should have only 2 unique sources
    assert len(report.sources) == 2


def test_report_limitations_and_recommendations():
    """Report includes limitations and recommendations."""
    agent = DeepResearchAgent()
    agent.plan = ResearchPlan(topic="test", goals=["test"])
    agent.findings = [ResearchFinding(title="1", content="c")]
    
    report = agent.generate_report()
    
    assert len(report.limitations) > 0
    assert len(report.recommendations) > 0
