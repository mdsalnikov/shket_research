## Changes

This PR enhances the self-healing system with improved error classification and recovery:

### New Features

- **Network Error Handling**: Added NETWORK_ERROR type for connection issues with exponential backoff
- **Timeout Handling**: Added TIMEOUT type for request timeouts with exponential backoff  
- **Enhanced Context Compression**: 
  - System messages are now preserved during compression
  - Topic extraction from messages for better summarization
  - New compress_to_token_limit for iterative compression
- **Improved Fallback Responses**:
  - More error types with specific messages
  - Progress tracking from assistant messages
  - Better error details for each type

### Tests

Added 9 new tests:
- test_classifier_network_error
- test_classifier_timeout
- test_classifier_get_backoff_time
- test_fallback_network_error
- test_fallback_timeout
- test_compressor_keeps_system_messages
- test_compressor_extract_topics
- test_compressor_summarize_messages
- test_compressor_compress_to_token_limit

### Version

Bumped to 0.4.2

All tests pass (36 tests in test_healing.py).
