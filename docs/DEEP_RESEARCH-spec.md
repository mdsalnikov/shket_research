# Deep Research Specification

## Overview

The Deep Research system provides advanced multi-step autonomous research capabilities for the Shket Research Agent. It follows patterns from OpenAI Deep Research and other advanced agent systems.

## Features

- **Multi-step planning**: Automatic research plan generation based on topic and goals
- **Iterative refinement**: Follow-up searches based on findings
- **Source verification**: Cross-reference information across sources
- **Synthesis**: Combine findings into coherent reports
- **Confidence scoring**: Quantitative measure of finding reliability

## Architecture

### Components

1. **ResearchStep**: A single step in the research process
2. **ResearchPlan**: Overall plan with multiple steps
3. **ResearchFinding**: Individual finding with metadata
4. **ResearchReport**: Final synthesized report
5. **DeepResearchAgent**: Orchestrates the research process

### Data Flow

```
Topic + Goals → ResearchPlan → [ResearchSteps] → Findings → Verification → Report
```

## API

### deep_research()

```python
async def deep_research(
    topic: str,
    goals: list[str] | None = None,
    max_steps: int = 10,
    max_depth: int = 3,
) -> str:
    """Conduct deep research on a topic."""
```

**Parameters:**
- `topic`: Main research topic
- `goals`: Specific research goals or questions
- `max_steps`: Maximum research steps (default: 10)
- `max_depth`: Maximum branching depth for follow-ups (default: 3)

**Returns:**
- Formatted research report as string

**Example:**
```python
result = await deep_research(
    "machine learning trends 2024",
    goals=["find latest developments", "identify key players"],
    max_steps=10,
    max_depth=3
)
```

### quick_research()

```python
async def quick_research(topic: str) -> str:
    """Perform a quick single-step research query."""
```

**Parameters:**
- `topic`: Research topic or question

**Returns:**
- Quick research results

**Example:**
```python
result = await quick_research("python async await")
```

### compare_sources()

```python
async def compare_sources(query: str, sources: list[str] | None = None) -> str:
    """Compare information across multiple sources."""
```

**Parameters:**
- `query`: What to compare
- `sources`: Optional list of specific sources

**Returns:**
- Comparison of findings

**Example:**
```python
result = await compare_sources("react vs vue")
```

## Research Report Format

```markdown
# Deep Research Report: {topic}

**Completed:** {timestamp}
**Confidence:** {percentage}
**Findings:** {count}
**Verified:** {count}

## Summary

{brief summary}

## Key Findings

1. ✓ {title}
   {content}
   Source: {url}

## Sources

- [{title}]({url})

## Limitations

- {limitation}

## Recommendations

- {recommendation}
```

## Confidence Scoring

Confidence is calculated as:
```
confidence = verified_findings / total_findings
```

A finding is considered verified when:
- It appears in multiple independent sources
- Cross-referencing confirms the information
- Sources are credible and recent

## Limitations

1. **Web-only**: Limited to web-accessible sources
2. **No direct access**: Cannot visit paywalled content
3. **Time-sensitive**: Information may become outdated
4. **Verification depth**: Limited by max_depth parameter

## Best Practices

1. **Use specific goals**: Provide clear research objectives
2. **Adjust step limits**: Use fewer steps for quick answers
3. **Verify critical info**: Use compare_sources for important findings
4. **Check timestamps**: Note when research was conducted
5. **Cross-reference**: Don't rely on single sources

## Testing

```bash
pytest tests/test_deep_research.py -v
```

## Future Enhancements

1. **Domain-specific search**: Academic, news, technical sources
2. **Citation extraction**: Automatic citation formatting
3. **Trend analysis**: Identify patterns over time
4. **Visual summaries**: Generate charts and graphs
5. **Collaborative research**: Multi-agent research teams
