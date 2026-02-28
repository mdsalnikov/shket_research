# Git Version Control

## Description
Expertise in Git version control, including branching strategies, 
merge conflicts, and collaborative workflows.

## When to Use
- User asks about Git operations
- Need to manage version control
- Branching and merging tasks
- Git history analysis

## Tools
- `git_status`: Check repository status
- `git_add`: Stage files
- `git_commit`: Create commits
- `git_push`: Push to remote
- `git_pull`: Pull from remote
- `git_checkout`: Switch branches

## Patterns

### Feature Branch Workflow
1. Create feature branch: `git checkout -b feature/name`
2. Make changes and commit
3. Push branch: `git push -u origin feature/name`
4. Create pull request
5. After merge: `git checkout main && git pull`

### Commit Message Convention
- Use present tense: "Add feature" not "Added feature"
- Keep subject line under 50 characters
- Reference issues: "Fix #123"

## Related Skills
- development
- code_review
