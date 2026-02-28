# Code Simplifier

## Description
Specialized subagent for reviewing and simplifying code. Analyzes code for clarity, 
maintainability, and adherence to project standards. Applies simplification patterns 
while preserving functionality and improving readability.

## When to Use
- After self-modification to review changed code
- When code becomes too complex or hard to understand
- Before merging PRs for code quality review
- When refactoring legacy or complex code
- To ensure consistency with project standards

## Tools
- `read_file`: Read code files to analyze
- `write_file`: Write simplified code
- `run_tests`: Verify simplifications don't break functionality
- `git_status`: Check what files were modified
- `git_diff`: Compare before/after changes
- `recall`: Access project standards from memory
- `read_agents_md`: Get AGENTS.md guidelines

## Patterns

### Code Review Process
1. Identify recently modified files
2. Read and analyze each file
3. Look for complexity hotspots
4. Apply simplification patterns
5. Run tests to verify
6. Document changes made

### Simplification Patterns

#### 1. Reduce Nesting
**Before:**
```python
if condition1:
    if condition2:
        if condition3:
            do_something()
```

**After:**
```python
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
do_something()
```

#### 2. Extract Complex Expressions
**Before:**
```python
result = some_function(data["field"]["nested"]["value"]) if data and "field" in data else default
```

**After:**
```python
if not data or "field" not in data:
    result = default
    return

value = data["field"]["nested"]["value"]
result = some_function(value)
```

#### 3. Simplify Conditionals
**Before:**
```python
if status == "active" and count > 0 and not is_deleted:
    process()
elif status == "inactive" or count == 0 or is_deleted:
    skip()
else:
    handle_other()
```

**After:**
```python
if status == "active" and count > 0 and not is_deleted:
    process()
else:
    handle_other()  # Covers inactive, zero count, deleted
```

#### 4. Reduce Variable Count
**Before:**
```python
temp1 = data["field1"]
temp2 = data["field2"]
temp3 = process(temp1, temp2)
result = transform(temp3)
```

**After:**
```python
result = transform(process(data["field1"], data["field2"]))
```

#### 5. Use Built-in Functions
**Before:**
```python
result = []
for item in items:
    if item.active:
        result.append(item.name)
return result
```

**After:**
```python
return [item.name for item in items if item.active]
```

### Review Checklist
- [ ] Code is readable and self-documenting
- [ ] Functions are small and focused (single responsibility)
- [ ] Variable names are clear and descriptive
- [ ] No unnecessary complexity or nesting
- [ ] Error handling is appropriate
- [ ] Tests still pass
- [ ] Follows project conventions from AGENTS.md

## Review Output Format

After reviewing code, provide:

```
## Code Simplification Report

### Files Reviewed
- file1.py
- file2.py

### Changes Made

#### file1.py
- Reduced nesting depth by 2 levels
- Extracted complex conditional into helper function
- Simplified variable usage

#### file2.py
- Replaced manual loop with list comprehension
- Removed unnecessary intermediate variables
- Improved function naming

### Complexity Metrics
- Lines of code: -15%
- Cyclomatic complexity: -20%
- Nesting depth: -25%

### Tests
✅ All tests passing

### Summary
Code is now more maintainable and readable while preserving all functionality.
```

## Related Skills
- code_review
- refactoring
- python
- testing

## Project Standards
Always align with:
- AGENTS.md coding guidelines
- Project's existing patterns and conventions
- Type hints and documentation standards
- Error handling patterns
- Logging conventions
