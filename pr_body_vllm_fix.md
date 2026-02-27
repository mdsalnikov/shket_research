## Summary

Fixed issue where agent was using OpenRouter instead of local VLLM endpoint due to environment variable override.

## Problem

- Environment variable `AGENT_MODEL=z-ai/glm-5` was overriding `.env` file settings
- Agent tried to use wrong model (`z-ai/glm-5`) with VLLM endpoint
- This caused 404 errors: "The model `z-ai/glm-5` does not exist"

## Solution

Added separate model configuration for VLLM and OpenRouter:

- `VLLM_MODEL` - model name for VLLM (used when `USE_VLLM=true`)
- `OPENROUTER_MODEL` - model name for OpenRouter (used when `USE_VLLM=false`)
- Dynamic model selection in `config.py` based on `USE_VLLM` flag

## Changes

- `agent/config.py`: Added `VLLM_MODEL`, `OPENROUTER_MODEL` and `get_model_name()` function
- `.env.example`: Updated with new model configuration options
- `VERSION`: Bumped to 0.2.1

## Testing

```bash
# Test agent with VLLM
python -m agent run "status"

# Expected output:
# Using VLLM local endpoint: http://localhost:8000/v1
# Model: openai/gpt-oss-120b
# HTTP Request: POST http://localhost:8000/v1/chat/completions "HTTP/1.1 200 OK"
```

## Configuration

Add to `.env`:
```
VLLM_BASE_URL=http://localhost:8000/v1
USE_VLLM=true
VLLM_MODEL=openai/gpt-oss-120b
```

## Related

Fixes #16 (request_limit error when using OpenRouter)
