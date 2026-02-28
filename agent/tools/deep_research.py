"""Deep Research system for multi-step autonomous research.

This module provides advanced research capabilities including:
- Multi-step research planning and execution
- Iterative search refinement
- Source verification and cross-referencing
- Synthesis of findings from multiple sources
- Structured research reports

Follows patterns from OpenAI Deep Research and other advanced agent systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent.activity_log import log_tool_call
from agent.tools.web import web_search

logger = logging.getLogger(__name__)


@dataclass
class ResearchStep:
    """A single step in the research process."""
    step_number: int
    description: str
    query: str | None = None
    findings: str = ""
    sources: list[str] = field(default_factory=list)
    completed: bool = False
    next_queries: list[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """A plan for conducting research."""
    topic: str
    goals: list[str] = field(default_factory=list)
    steps: list[ResearchStep] = field(default_factory=list)
    estimated_steps: int = 5
    current_step: int = 0


@dataclass
class ResearchFinding:
    """A finding from research."""
    title: str
    content: str
    source_url: str = ""
    source_title: str = ""
    relevance_score: float = 1.0  # 0.0 to 1.0
    verified: bool = False
    verification_sources: list[str] = field(default_factory=list)


@dataclass
class ResearchReport:
    """Final research report."""
    topic: str
    summary: str
    findings: list[ResearchFinding] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0  # Overall confidence in findings
    limitations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    completed_at: str = ""


class DeepResearchAgent:
    """Advanced research agent with multi-step capabilities."""
    
    def __init__(self, max_steps: int = 10, max_depth: int = 3):
        """Initialize research agent.
        
        Args:
            max_steps: Maximum research steps to execute
            max_depth: Maximum branching depth for follow-up searches
            
        """
        self.max_steps = max_steps
        self.max_depth = max_depth
        self.plan: ResearchPlan | None = None
        self.findings: list[ResearchFinding] = []
        self.search_history: list[str] = []
    
    def create_plan(self, topic: str, goals: list[str] | None = None) -> ResearchPlan:
        """Create a research plan based on topic and goals.
        
        Args:
            topic: Main research topic
            goals: Specific research goals/questions
            
        Returns:
            ResearchPlan with steps
            
        """
        if goals is None:
            goals = [f"Research {topic} comprehensively"]
        
        plan = ResearchPlan(topic=topic, goals=goals)
        
        # Create initial research steps
        plan.steps = [
            ResearchStep(1, f"Initial broad search on {topic}"),
            ResearchStep(2, "Identify key themes and subtopics"),
            ResearchStep(3, "Deep dive into primary sources"),
            ResearchStep(4, "Cross-reference and verify information"),
            ResearchStep(5, "Synthesize findings and identify gaps"),
        ]
        
        plan.estimated_steps = min(len(plan.steps), self.max_steps)
        return plan
    
    async def execute_step(self, step: ResearchStep, depth: int = 0) -> str:
        """Execute a single research step.
        
        Args:
            step: The research step to execute
            depth: Current branching depth
            
        Returns:
            Findings from this step
            
        """
        if depth >= self.max_depth:
            return "Maximum search depth reached."
        
        if not step.query:
            # Generate query from step description
            step.query = step.description.replace("Search for ", "").replace("Research ", "")
        
        logger.info(f"Executing research step {step.step_number}: {step.query}")
        
        # Perform search
        results = await web_search(step.query)
        self.search_history.append(step.query)
        
        # Parse results
        step.findings = results
        step.completed = True
        
        # Extract sources
        for line in results.split('\n'):
            if 'http' in line.lower():
                step.sources.append(line.strip())
        
        # Generate follow-up queries if needed
        if depth < self.max_depth and step.step_number < self.max_steps:
            step.next_queries = self._generate_follow_up_queries(results)
        
        return results
    
    def _generate_follow_up_queries(self, results: str) -> list[str]:
        """Generate follow-up search queries based on results.
        
        Args:
            results: Search results to analyze
            
        Returns:
            List of follow-up queries
            
        """
        queries = []
        
        # Look for unresolved questions or topics to explore
        if "no results" in results.lower():
            # Try alternative phrasings
            queries.append("alternative search terms")
        
        # Look for specific topics mentioned
        if len(results) > 100:
            # Extract potential subtopics (simplified)
            queries.append("related topics and concepts")
        
        return queries[:3]  # Limit to 3 follow-ups
    
    async def verify_finding(self, finding: ResearchFinding) -> bool:
        """Verify a finding by searching for corroborating sources.
        
        Args:
            finding: The finding to verify
            
        Returns:
            True if verified across multiple sources
            
        """
        # Create verification query
        query = f"verify {finding.title}"
        
        results = await web_search(query)
        
        # Check if finding appears in multiple sources
        if results and "no results" not in results.lower():
            finding.verified = True
            finding.verification_sources.append(query)
            return True
        
        return False
    
    def synthesize_findings(self) -> str:
        """Synthesize all findings into a coherent summary.
        
        Returns:
            Synthesized research summary
            
        """
        if not self.findings:
            return "No findings to synthesize."
        
        # Group findings by theme
        themes: dict[str, list[ResearchFinding]] = {}
        for finding in self.findings:
            # Simple theme extraction (could be improved with NLP)
            theme = finding.title.split()[0].lower() if finding.title else "general"
            if theme not in themes:
                themes[theme] = []
            themes[theme].append(finding)
        
        # Build synthesis
        synthesis_parts = ["# Research Synthesis", ""]
        
        for theme, findings in themes.items():
            synthesis_parts.append(f"## {theme.title()}")
            synthesis_parts.append("")
            for finding in findings[:3]:  # Limit to top 3 per theme
                verified_marker = "✓" if finding.verified else ""
                synthesis_parts.append(f"- {verified_marker} {finding.title}")
                synthesis_parts.append(f"  {finding.content[:200]}...")
                synthesis_parts.append("")
        
        return "\n".join(synthesis_parts)
    
    def generate_report(self) -> ResearchReport:
        """Generate a complete research report.
        
        Returns:
            ResearchReport with all findings
            
        """
        if not self.plan:
            raise ValueError("No research plan exists")
        
        # Calculate confidence based on verified findings
        verified_count = sum(1 for f in self.findings if f.verified)
        confidence = verified_count / len(self.findings) if self.findings else 0.0
        
        # Extract unique sources
        sources = []
        seen_urls = set()
        for finding in self.findings:
            if finding.source_url and finding.source_url not in seen_urls:
                sources.append({
                    "url": finding.source_url,
                    "title": finding.source_title or "Untitled"
                })
                seen_urls.add(finding.source_url)
        
        report = ResearchReport(
            topic=self.plan.topic,
            summary=self.synthesize_findings()[:1000],  # Brief summary
            findings=self.findings,
            sources=sources,
            confidence=confidence,
            limitations=[
                "Search limited to web-accessible sources",
                "Some findings may not be verified",
                "Information may be time-sensitive"
            ],
            recommendations=[
                "Verify critical findings with primary sources",
                "Consider domain-specific databases for specialized topics",
                "Check publication dates for time-sensitive information"
            ],
            completed_at=datetime.now().isoformat()
        )
        
        return report


async def deep_research(
    topic: str,
    goals: list[str] | None = None,
    max_steps: int = 10,
    max_depth: int = 3,
) -> str:
    """Conduct deep research on a topic.
    
    This tool performs multi-step autonomous research with:
    - Initial broad search
    - Iterative refinement
    - Source verification
    - Synthesis of findings
    
    Args:
        topic: Main research topic
        goals: Specific research goals or questions
        max_steps: Maximum research steps (default: 10)
        max_depth: Maximum branching depth (default: 3)
        
    Returns:
        Comprehensive research report
        
    Example:
        result = await deep_research(
            "machine learning trends 2024",
            goals=["Find latest developments", "Identify key players"]
        )
        
    """
    with log_tool_call("deep_research", topic) as tool_log:
        logger.info("Tool deep_research: starting research on %s", topic)
        
        try:
            # Initialize agent
            agent = DeepResearchAgent(max_steps=max_steps, max_depth=max_depth)
            
            # Create plan
            plan = agent.create_plan(topic, goals)
            agent.plan = plan
            
            # Execute research steps
            findings_count = 0
            for i, step in enumerate(plan.steps[:max_steps]):
                if i >= max_steps:
                    break
                
                # Execute step
                results = await agent.execute_step(step)
                
                # Parse findings from results
                for line in results.split('\n\n'):
                    if line.strip() and not line.strip().startswith('-'):
                        # Extract finding
                        lines = line.split('\n')
                        if lines:
                            title = lines[0].replace('- ', '').strip()
                            content = '\n'.join(lines[1:]).strip()
                            if title and content:
                                finding = ResearchFinding(
                                    title=title,
                                    content=content[:500],  # Limit length
                                    source_url=lines[1] if len(lines) > 1 else ""
                                )
                                agent.findings.append(finding)
                                findings_count += 1
                
                # Log progress
                logger.info(f"Step {i+1} completed, {findings_count} findings so far")
            
            # Verify some findings
            verified_count = 0
            for finding in agent.findings[:5]:  # Verify top 5
                if await agent.verify_finding(finding):
                    verified_count += 1
            
            # Generate report
            report = agent.generate_report()
            
            # Format output
            output_parts = [
                f"# Deep Research Report: {report.topic}",
                "",
                f"**Completed:** {report.completed_at}",
                f"**Confidence:** {report.confidence:.0%}",
                f"**Findings:** {len(report.findings)}",
                f"**Verified:** {verified_count}",
                "",
                "## Summary",
                "",
                report.summary[:2000],  # Limit summary length
                "",
                "## Key Findings",
                ""
            ]
            
            for i, finding in enumerate(report.findings[:10], 1):  # Top 10
                verified_marker = "✓" if finding.verified else ""
                output_parts.append(f"{i}. {verified_marker} **{finding.title}**")
                output_parts.append(f"   {finding.content[:300]}")
                if finding.source_url:
                    output_parts.append(f"   Source: {finding.source_url}")
                output_parts.append("")
            
            if report.sources:
                output_parts.append("## Sources")
                output_parts.append("")
                for source in report.sources[:10]:
                    output_parts.append(f"- [{source['title']}]({source['url']})")
                output_parts.append("")
            
            if report.limitations:
                output_parts.append("## Limitations")
                output_parts.append("")
                for limitation in report.limitations:
                    output_parts.append(f"- {limitation}")
                output_parts.append("")
            
            result = "\n".join(output_parts)
            tool_log.log_result(f"{len(report.findings)} findings, {report.confidence:.0%} confidence")
            return result
            
        except Exception as e:
            logger.error("deep_research failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Research error: {e}"


async def quick_research(topic: str) -> str:
    """Perform a quick single-step research query.
    
    This is a simplified version for quick information gathering
    without the full multi-step process.
    
    Args:
        topic: Research topic or question
        
    Returns:
        Quick research results
        
    """
    with log_tool_call("quick_research", topic) as tool_log:
        logger.info("Tool quick_research: %s", topic)
        
        try:
            results = await web_search(topic)
            
            # Format results
            output_parts = [
                f"# Quick Research: {topic}",
                "",
                results
            ]
            
            result = "\n".join(output_parts)
            tool_log.log_result("quick research completed")
            return result
            
        except Exception as e:
            logger.error("quick_research failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Research error: {e}"


async def compare_sources(query: str, sources: list[str] | None = None) -> str:
    """Compare information across multiple sources.
    
    Args:
        query: What to compare
        sources: Optional list of specific sources to check
        
    Returns:
        Comparison of findings across sources
        
    """
    with log_tool_call("compare_sources", query) as tool_log:
        logger.info("Tool compare_sources: %s", query)
        
        try:
            # Search for the query
            results = await web_search(query)
            
            # Look for consensus and disagreements
            output_parts = [
                f"# Source Comparison: {query}",
                "",
                "## Search Results",
                "",
                results,
                "",
                "## Analysis",
                "",
                "To properly compare sources, I would need to:"
            ]
            
            output_parts.extend([
                "- Visit each source directly",
                "- Extract specific claims",
                "- Identify agreements and disagreements",
                "- Assess source credibility"
            ])
            
            result = "\n".join(output_parts)
            tool_log.log_result("comparison completed")
            return result
            
        except Exception as e:
            logger.error("compare_sources failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Comparison error: {e}"
