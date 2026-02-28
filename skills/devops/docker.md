# Docker Containerization

## Description
Expertise in Docker containerization, including image creation,
container management, and Docker Compose.

## When to Use
- User asks about Docker
- Need to containerize applications
- Docker Compose configuration
- Container orchestration questions

## Tools
- `run_shell`: Execute Docker commands
- `read_file`: Read Dockerfiles and configs
- `write_file`: Create Docker configurations

## Patterns

### Multi-stage Builds
Reduce image size with multi-stage builds:
```dockerfile
FROM python:3.11 as builder
# Build steps

FROM python:3.11-slim
# Copy only necessary files
```

### Docker Compose
Define multi-container applications:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
```

## Related Skills
- devops
- deployment
