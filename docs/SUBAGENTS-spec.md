# SUBAGENTS System Specification

## Overview

The SUBAGENTS system enables hierarchical agent architectures where specialized subagents handle specific tasks, delegating from a main orchestrator agent. This follows patterns used by Claude Code and other advanced agent systems.

## Motivation

- **Focused context**: Each subagent works with relevant context only
- **Specialization**: Different agents optimized for different tasks
- **Parallel execution**: Multiple subagents can work simultaneously
- **Modularity**: Easy to add new specialized agents
- **Error isolation**: Failures contained within subagent scope

## Architecture

```
┌────────────────────────────────────────┐
│         Main Agent (Orchestrator)      │
│  - Task decomposition                  │
│  - Subagent selection                  │
│  - Result synthesis                     │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│        Subagent Manager                │
│  - Subagent registry                   │
│  - Task routing                        │
│  - Result aggregation                  │
└──────────────┬─────────────────────────┘
               │
       ┌───────┼───────┬────────────┐
       ▼       ▼       ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Coder   │ │Research│ │Reviewer│ │Debugger  │
│Agent   │ │Agent   │ │Agent   │ │Agent     │
└────────┘ └────────┘ └────────┘ └──────────┘
```

## Subagent Types

### Built-in Subagents

1. **Coder Agent**
   - Task: Code generation and modification
   - Tools: filesystem, shell, git
   - Context: Codebase structure, coding standards

2. **Research Agent**
   - Task: Information gathering and synthesis
   - Tools: web_search, filesystem
   - Context: Research methodology, source evaluation

3. **Reviewer Agent**
   - Task: Code review and quality assurance
   - Tools: filesystem, git
   - Context: Review guidelines, best practices

4. **Debugger Agent**
   - Task: Bug investigation and fixing
   - Tools: shell, filesystem, todo
   - Context: Debugging patterns, error analysis

### Custom Subagents

Users can define custom subagents for specific domains:
- Data Analysis Agent
- DevOps Agent
- Documentation Agent
- Testing Agent

## Subagent Definition Format

Subagents are defined in YAML or JSON files:

```yaml
name: coder_agent
description: Specialized agent for code generation and modification
version: 1.0.0

# System prompt customization
system_prompt: |
  You are a specialized coding agent. Focus on:
  - Writing clean, maintainable code
  - Following project conventions
  - Adding appropriate tests

# Tools available to this subagent
tools:
  - read_file
  - write_file
  - list_dir
  - run_shell
  - git_status
  - git_add
  - git_commit

# Context files to load
context_files:
  - AGENTS.md
  - README.md

# When to use this subagent
triggers:
  - "write code"
  - "implement feature"
  - "refactor"
  - "add function"

# Related subagents for handoff
related:
  - reviewer_agent
  - tester_agent
```

## Task Delegation Pattern

### 1. Task Analysis
Main agent analyzes the task:
```python
task = "Add a new API endpoint for user authentication"
analysis = {
    "type": "coding",
    "complexity": "medium",
    "required_skills": ["api", "authentication"],
    "recommended_subagent": "coder_agent"
}
```

### 2. Subagent Selection
Choose appropriate subagent(s):
```python
subagent = select_subagent(task, analysis)
# Returns: coder_agent
```

### 3. Context Preparation
Prepare context for subagent:
```python
context = prepare_context(subagent, task)
# Loads: system prompt, tools, context files
```

### 4. Task Execution
Run subagent with prepared context:
```python
result = await run_subagent(subagent, task, context)
```

### 5. Result Synthesis
Main agent synthesizes results:
```python
final_result = synthesize_results([result])
```

## API Design

### Core Functions

```python
# Subagent registry
async def list_subagents() -> list[Subagent]
async def get_subagent(name: str) -> Subagent | None

# Task delegation
async def delegate_task(
    subagent_name: str,
    task: str,
    context: dict | None = None
) -> str

# Auto-routing
async def route_task(task: str) -> tuple[str, str]
# Returns: (subagent_name, delegated_task)

# Parallel execution
async def execute_parallel(
    tasks: list[tuple[str, str]]  # (subagent_name, task)
) -> list[str]
```

### Subagent Class

```python
@dataclass
class Subagent:
    name: str
    description: str
    version: str
    system_prompt: str
    tools: list[str]
    context_files: list[str]
    triggers: list[str]
    related: list[str]
    config: dict  # Additional configuration
```

## Implementation Details

### Subagent Directory
- Located at `subagents/` in project root
- Each subagent defined in `.yaml` file
- Optional custom prompts in `.md` files

### Context Management
- Each subagent has isolated context
- Shared memory via main agent
- Context files loaded on initialization

### Execution Model
- Subagents run in same process (lightweight)
- Separate session contexts
- Shared tool registry

## Example Workflow

### Multi-Step Feature Development

1. **Planning Phase**
   - Main agent: Decompose feature into tasks
   - Output: Task list with dependencies

2. **Implementation Phase**
   - Coder subagent: Implement each task
   - Parallel execution for independent tasks

3. **Review Phase**
   - Reviewer subagent: Review code changes
   - Output: Review comments and suggestions

4. **Testing Phase**
   - Tester subagent: Create and run tests
   - Output: Test results and coverage

5. **Synthesis Phase**
   - Main agent: Combine all results
   - Output: Final summary and next steps

## Error Handling

### Subagent Failure
```python
try:
    result = await delegate_task("coder_agent", task)
except SubagentError as e:
    # Log error
    # Try alternative subagent
    # Or escalate to main agent
    result = await handle_subagent_failure(e, task)
```

### Timeout Handling
- Each subagent has configurable timeout
- Main agent monitors execution
- Graceful degradation on timeout

## Best Practices

### Designing Subagents
1. **Single Responsibility**: Each subagent does one thing well
2. **Clear Triggers**: Well-defined when to use each subagent
3. **Minimal Context**: Load only necessary context
4. **Explicit Handoffs**: Clear interfaces between subagents

### Using Subagents
1. **Analyze First**: Understand task before delegating
2. **Prepare Context**: Provide relevant information
3. **Monitor Execution**: Track subagent progress
4. **Synthesize Results**: Combine outputs meaningfully

## Future Enhancements

- **Learning**: Subagents learn from past tasks
- **Dynamic Creation**: Create subagents on-the-fly
- **Federated Agents**: Subagents across multiple systems
- **Performance Metrics**: Track subagent effectiveness
- **Auto-optimization**: Improve subagent selection

## Integration with Existing Systems

### AGENTS.md
Subagents reference AGENTS.md for project context.

### SKILLS System
Subagents can load relevant skills for their domain.

### Memory System
Subagents share memory via main agent coordination.

### Self-Healing
Subagents inherit self-healing capabilities from main agent.
