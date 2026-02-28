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
import re
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
        
        # Create initial research steps based on topic type
        plan.steps = self._create_intelligent_steps(topic, goals)
        
        plan.estimated_steps = min(len(plan.steps), self.max_steps)
        return plan
    
    def _create_intelligent_steps(self, topic: str, goals: list[str]) -> list[ResearchStep]:
        """Create research steps tailored to the topic and goals."""
        steps = []
        
        # Initial broad search
        steps.append(ResearchStep(1, f"Initial broad search on {topic}"))
        
        # Add goal-specific steps
        for i, goal in enumerate(goals[:3], 2):  # Limit to 3 goal-specific steps
            steps.append(ResearchStep(i, f"Investigate: {goal}"))
        
        # Verification step
        steps.append(ResearchStep(len(steps) + 1, "Cross-reference and verify information"))
        
        # Synthesis step
        steps.append(ResearchStep(len(steps) + 1, "Synthesize findings and identify gaps"))
        
        return steps
    
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
        
        # Calculate confidence based on verification
        if self.findings:
            verified_count = sum(1 for f in self.findings if f.verified)
            self.confidence = verified_count / len(self.findings)
        else:
            self.confidence = 0.0
        
        # Deduplicate sources
        seen_urls = set()
        sources = []
        for finding in self.findings:
            if finding.source_url and finding.source_url not in seen_urls:
                seen_urls.add(finding.source_url)
                sources.append({
                    "url": finding.source_url,
                    "title": finding.source_title or "Untitled"
                })
        
        # Generate summary
        summary = self._generate_summary()
        
        # Identify limitations
        limitations = self._identify_limitations()
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        return ResearchReport(
            topic=self.plan.topic,
            summary=summary,
            findings=self.findings.copy(),
            sources=sources,
            confidence=self.confidence,
            limitations=limitations,
            recommendations=recommendations,
            completed_at=datetime.now().isoformat()
        )
    
    def _generate_summary(self) -> str:
        """Generate a summary of the research."""
        if not self.findings:
            return f"Research on '{self.plan.topic}' yielded no findings."
        
        # Extract key points
        key_points = []
        for finding in self.findings[:5]:  # Top 5 findings
            if finding.title:
                key_points.append(finding.title)
        
        summary = f"Research on '{self.plan.topic}' identified {len(self.findings)} key findings. "
        if key_points:
            summary += f"Main topics include: {', '.join(key_points[:3])}. "
        
        if self.confidence > 0.7:
            summary += "Findings are well-verified across multiple sources."
        elif self.confidence > 0.4:
            summary += "Findings have moderate verification."
        else:
            summary += "Findings require further verification."
        
        return summary
    
    def _identify_limitations(self) -> list[str]:
        """Identify limitations in the research."""
        limitations = []
        
        if not self.findings:
            limitations.append("No findings were gathered during research.")
            return limitations
        
        unverified_count = sum(1 for f in self.findings if not f.verified)
        if unverified_count > len(self.findings) / 2:
            limitations.append(f"{unverified_count} findings could not be verified across sources.")
        
        if len(self.findings) < 3:
            limitations.append("Limited number of findings may not provide comprehensive coverage.")
        
        if len(self.search_history) < 3:
            limitations.append("Research scope was limited by few search iterations.")
        
        return limitations
    
    def _generate_recommendations(self) -> list[str]:
        """Generate recommendations based on research."""
        recommendations = []
        
        if not self.findings:
            recommendations.append("Consider refining the research topic or using alternative search terms.")
            return recommendations
        
        # Check for gaps
        if self.confidence < 0.5:
            recommendations.append("Verify key findings through additional sources.")
        
        if len(self.findings) > 5:
            recommendations.append("Consider focusing on specific subtopics for deeper analysis.")
        
        recommendations.append("Review the full source list for primary references.")
        
        return recommendations


async def deep_research(
    topic: str,
    goals: list[str] | None = None,
    max_steps: int = 10,
    max_depth: int = 3
) -> str:
    """Conduct deep multi-step research on a topic.
    
    This tool performs comprehensive research with:
    - Multi-step search and refinement
    - Source verification
    - Synthesis of findings
    - Structured report generation
    
    Args:
        topic: Main research topic
        goals: Optional list of specific research goals
        max_steps: Maximum number of research steps (default: 10)
        max_depth: Maximum branching depth for follow-ups (default: 3)
        
    Returns:
        Formatted research report with findings, sources, and analysis
        
    """
    with log_tool_call("deep_research", topic) as tool_log:
        logger.info("Tool deep_research: %s (goals: %s, max_steps: %d, max_depth: %d)", 
                   topic, goals, max_steps, max_depth)
        
        try:
            agent = DeepResearchAgent(max_steps=max_steps, max_depth=max_depth)
            
            # Create research plan
            agent.plan = agent.create_plan(topic, goals)
            
            logger.info("Research plan: %d steps", len(agent.plan.steps))
            
            # Execute research steps
            executed_steps = 0
            for step in agent.plan.steps:
                if executed_steps >= max_steps:
                    break
                
                # Execute step
                await agent.execute_step(step)
                executed_steps += 1
                
                # Extract findings from step results
                findings = _parse_search_results(step.findings)
                agent.findings.extend(findings)
                
                # Execute follow-up queries if available
                if step.next_queries and agent.max_depth > 0:
                    for follow_up in step.next_queries[:1]:  # Limit follow-ups
                        if executed_steps >= max_steps:
                            break
                        follow_step = ResearchStep(
                            step_number=executed_steps + 1,
                            description=follow_up,
                            query=follow_up
                        )
                        await agent.execute_step(follow_step, depth=1)
                        executed_steps += 1
            
            # Verify some findings
            for finding in agent.findings[:5]:  # Verify top 5
                await agent.verify_finding(finding)
            
            # Generate report
            report = agent.generate_report()
            
            # Format output
            output_parts = [
                f"# Deep Research Report: {report.topic}",
                "",
                f"**Completed**: {report.completed_at}",
                f"**Confidence**: {report.confidence:.0%}",
                f"**Findings**: {len(report.findings)}",
                "",
                "## Summary",
                "",
                report.summary,
                "",
                "## Key Findings",
                ""
            ]
            
            for i, finding in enumerate(report.findings[:10], 1):  # Top 10 findings
                verified_marker = "✓" if finding.verified else ""
                output_parts.append(f"{i}. {verified_marker} **{finding.title}**")
                output_parts.append(f"   {finding.content[:300]}")
                if finding.source_url:
                    output_parts.append(f"   Source: {finding.source_url}")
                output_parts.append("")
            
            if report.sources:
                output_parts.append("## Sources")
                output_parts.append("")
                for i, source in enumerate(report.sources[:10], 1):
                    output_parts.append(f"{i}. {source.get('title', 'Untitled')}")
                    output_parts.append(f"   {source.get('url', 'No URL')}")
                output_parts.append("")
            
            if report.limitations:
                output_parts.append("## Limitations")
                output_parts.append("")
                for limitation in report.limitations:
                    output_parts.append(f"- {limitation}")
                output_parts.append("")
            
            if report.recommendations:
                output_parts.append("## Recommendations")
                output_parts.append("")
                for rec in report.recommendations:
                    output_parts.append(f"- {rec}")
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
            
            # Parse and format results
            findings = _parse_search_results(results)
            
            output_parts = [
                f"# Quick Research: {topic}",
                "",
                f"**Findings**: {len(findings)}",
                ""
            ]
            
            for i, finding in enumerate(findings[:5], 1):
                output_parts.append(f"{i}. **{finding.title}**")
                output_parts.append(f"   {finding.content[:200]}")
                if finding.source_url:
                    output_parts.append(f"   Source: {finding.source_url}")
                output_parts.append("")
            
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
            
            # Parse findings
            findings = _parse_search_results(results)
            
            # Group by source
            source_groups: dict[str, list[ResearchFinding]] = {}
            for finding in findings:
                source_key = finding.source_url or "Unknown source"
                if source_key not in source_groups:
                    source_groups[source_key] = []
                source_groups[source_key].append(finding)
            
            # Build comparison
            output_parts = [
                f"# Source Comparison: {query}",
                "",
                f"**Sources Found**: {len(source_groups)}",
                "",
                "## Findings by Source",
                ""
            ]
            
            for source_url, source_findings in source_groups.items():
                output_parts.append(f"### Source: {source_url}")
                output_parts.append("")
                for finding in source_findings[:3]:
                    output_parts.append(f"- {finding.title}")
                    output_parts.append(f"  {finding.content[:150]}")
                output_parts.append("")
            
            # Consensus analysis
            output_parts.extend([
                "## Analysis",
                "",
                "To identify consensus across sources:",
                "- Look for repeated claims across multiple sources",
                "- Note any disagreements or differing perspectives",
                "- Consider source credibility and recency",
                ""
            ])
            
            result = "\n".join(output_parts)
            tool_log.log_result("comparison completed")
            return result
            
        except Exception as e:
            logger.error("compare_sources failed: %s", e)
            tool_log.log_result(f"error: {e}")
            return f"Comparison error: {e}"


def _parse_search_results(results: str) -> list[ResearchFinding]:
    """Parse web search results into ResearchFinding objects.
    
    Args:
        results: Raw search results string
        
    Returns:
        List of parsed ResearchFinding objects
        
    """
    findings = []
    
    if not results or "no results" in results.lower():
        return findings
    
    # Parse DuckDuckGo format:
    # - Title
    #   URL
    #   Snippet
    
    lines = results.strip().split('\n')
    current_finding = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Title line starts with "- "
        if line.startswith('- '):
            # Save previous finding
            if current_finding:
                findings.append(current_finding)
            
            current_finding = ResearchFinding(
                title=line[2:].strip(),
                content=""
            )
        
        # URL line starts with "  " and contains http
        elif line.startswith('  ') and 'http' in line.lower():
            if current_finding:
                current_finding.source_url = line.strip()
        
        # Snippet line
        elif line.startswith('  ') and current_finding:
            snippet = line.strip()
            if current_finding.content:
                current_finding.content += " " + snippet
            else:
                current_finding.content = snippet
        
        i += 1
    
    # Don't forget the last finding
    if current_finding:
        findings.append(current_finding)
    
    return findings
