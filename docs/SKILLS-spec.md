# SKILLS System Specification

## Overview

The SKILLS system provides a structured way to define, discover, and use specialized capabilities for the agent. Each skill represents a specific domain expertise or task pattern that the agent can leverage.

## Motivation

- **Modular expertise**: Break down complex capabilities into discrete, reusable skills
- **Discoverability**: Agent can find relevant skills for a given task
- **Extensibility**: New skills can be added without modifying core code
- **Context management**: Skills provide focused context without overwhelming the agent

## Architecture

```
┌─────────────────────────────────────┐
│          Agent Core                 │
│         (Orchestrator)              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Skills Manager               │
│  - Skill Discovery                  │
│  - Context Loading                  │
│  - Skill Selection                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Skills Directory             │
│  skills/                            │
│  ├── programming/                   │
│  │   ├── python.md                  │
│  │   └── javascript.md              │
│  ├── research/                      │
│  │   ├── web_research.md            │
│  │   └── data_analysis.md           │
│  └── devops/                        │
│      ├── git.md                     │
│      └── docker.md                  │
└─────────────────────────────────────┘
```

## Skill File Format

Skills are defined in Markdown files with a standard structure:

```markdown
# Skill Name

## Description
Brief description of what this skill enables.

## When to Use
- Condition 1 for using this skill
- Condition 2 for using this skill

## Tools
List of tools commonly used with this skill:
- tool_name: how to use it

## Patterns
Common patterns and best practices:

### Pattern 1
Description and example.

### Pattern 2
Description and example.

## Examples

### Example 1
Task: What the user wants
Approach: How to solve it
Steps:
1. Step one
2. Step two

## Related Skills
- other_skill_name
```

## Skill Categories

### Programming
- `python`: Python development, debugging, testing
- `javascript`: JavaScript/TypeScript development
- `bash`: Shell scripting and system administration
- `sql`: Database queries and optimization

### Research
- `web_research`: Multi-step web research
- `data_analysis`: Data processing and analysis
- `literature_review`: Academic research

### Development
- `git`: Version control workflows
- `testing`: Test creation and execution
- `debugging`: Systematic debugging approaches

### DevOps
- `docker`: Containerization
- `deployment`: Deployment workflows
- `monitoring`: System monitoring

## Skills API

### Core Functions

```python
# Discover available skills
async def list_skills() -> list[str]

# Get skill details
async def get_skill(skill_name: str) -> str

# Find relevant skills for a task
async def find_relevant_skills(task: str) -> list[str]

# Load skill context into agent
async def load_skill_context(skill_name: str) -> str
```

## Implementation Details

### Skills Directory
- Located at `skills/` in project root
- Organized by category in subdirectories
- Each skill is a `.md` file

### Skill Discovery
- Scan `skills/` directory for `.md` files
- Parse skill metadata (name, category, description)
- Build index for fast lookup

### Context Loading
- Load full skill content when needed
- Cache frequently used skills
- Provide summarized view for discovery

## Example Skill File

```markdown
# Python Development

## Description
Expertise in Python programming, including modern Python 3.x features, 
best practices, debugging, and testing.

## When to Use
- User asks about Python code
- Need to write or debug Python scripts
- Python package management questions
- Async Python programming

## Tools
- `run_shell`: Execute Python scripts and commands
- `read_file`: Read Python source files
- `write_file`: Create or modify Python files
- `run_tests`: Run pytest test suites

## Patterns

### Virtual Environment Setup
Always use virtual environments for Python projects:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testing Pattern
Write tests before or alongside code:
```python
def test_function():
    assert function(input) == expected
```

## Examples

### Example 1: Script Creation
Task: Create a Python script to process CSV files
Approach: Use pandas for data processing
Steps:
1. Create virtual environment
2. Install pandas
3. Write script with error handling
4. Test with sample data

## Related Skills
- data_analysis
- testing
- bash
```

## Integration with Agent

### System Prompt Integration
Skills are referenced in the system prompt:
```
Available skills: python, git, web_research, ...
Use get_skill() to load detailed guidance for a task.
```

### Automatic Skill Suggestion
The agent can suggest relevant skills:
```python
relevant = await find_relevant_skills("write a python script")
# Returns: ["python", "testing", "bash"]
```

## Best Practices

### Writing Skills
1. Be specific and actionable
2. Include concrete examples
3. Reference related skills
4. Update regularly

### Using Skills
1. Load skills before starting related tasks
2. Combine multiple skills for complex tasks
3. Refer to skill patterns for consistency

## Future Enhancements

- Skill versioning
- Skill dependencies
- Skill ratings and feedback
- Dynamic skill generation
- Skill sharing between projects
