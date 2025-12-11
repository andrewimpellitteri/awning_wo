# DeepSeek API Setup for RAG Chatbot

This document describes the DeepSeek API integration for the RAG chatbot.

## Overview

The chatbot uses **DeepSeek V3** via their OpenAI-compatible API for:
- **Chat completions**: Answering user questions with RAG context
- **Embeddings**: Generating vector embeddings for semantic search

## Configuration

### Environment Variables

Set the following environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | - | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | API base URL |
| `DEEPSEEK_CHAT_MODEL` | No | `deepseek-chat` | Chat model to use |
| `DEEPSEEK_EMBED_MODEL` | No | `deepseek-embedding` | Embedding model |

### Getting an API Key

1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Create an account or sign in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (it won't be shown again)

## Local Development Setup

### Option 1: Export in Terminal
```bash
export DEEPSEEK_API_KEY="your-api-key-here"
python app.py
```

### Option 2: Create a .env File
```bash
# Create .env file (don't commit this!)
echo 'DEEPSEEK_API_KEY=your-api-key-here' > .env
```

Then load it in your shell:
```bash
source .env
# or use python-dotenv in the app
```

### Option 3: Use direnv (Recommended)
```bash
# Install direnv: brew install direnv (Mac) or apt install direnv (Linux)

# Create .envrc file
echo 'export DEEPSEEK_API_KEY="your-api-key-here"' > .envrc

# Allow direnv for this directory
direnv allow
```

## AWS Elastic Beanstalk Setup

### Set Environment Variables

Using EB CLI:
```bash
eb setenv DEEPSEEK_API_KEY="your-api-key-here"
```

Or via AWS Console:
1. Go to Elastic Beanstalk Console
2. Select your environment
3. Click "Configuration" in the left menu
4. Under "Software", click "Edit"
5. Scroll to "Environment properties"
6. Add `DEEPSEEK_API_KEY` with your key value
7. Click "Apply"

### Verify Configuration
```bash
# SSH into instance
eb ssh

# Check environment variable is set
echo $DEEPSEEK_API_KEY

# Test API access
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hi"}]}'
```

## Models

### Chat Model: `deepseek-chat`
- **DeepSeek V3** - Latest generation model
- High-quality reasoning and context understanding
- Supports function calling/tools
- Fast inference speeds

### Embedding Model: `deepseek-embedding`
- 768-dimensional vectors
- Optimized for semantic search
- Compatible with existing pgvector storage

## Pricing (as of Dec 2024)

DeepSeek offers very competitive pricing:

| Model | Input | Output |
|-------|-------|--------|
| deepseek-chat | $0.14/M tokens | $0.28/M tokens |
| deepseek-embedding | ~$0.01/M tokens | - |

*Prices may vary. Check [DeepSeek Pricing](https://platform.deepseek.com/pricing) for current rates.*

## Syncing Embeddings

After setting up the API key, re-sync your embeddings:

```bash
# Sync all embeddings
python scripts/sync_embeddings.py --type all --verbose

# Check status
python scripts/sync_embeddings.py --status

# Sync specific types
python scripts/sync_embeddings.py --type customers --verbose
python scripts/sync_embeddings.py --type work_orders --verbose
python scripts/sync_embeddings.py --type items --verbose
```

## Health Monitoring

Check chatbot status via the API:
```bash
curl http://localhost:5000/api/chat/status
```

Returns:
```json
{
  "api_available": true,
  "api_configured": true,
  "chat_model": "deepseek-chat",
  "embed_model": "deepseek-embedding"
}
```

## Troubleshooting

### "DEEPSEEK_API_KEY environment variable is not set"
- Ensure the environment variable is exported
- Check for typos in the variable name
- On EB, verify via `eb printenv`

### "Failed to generate embedding"
- Verify API key is valid
- Check DeepSeek service status
- Review rate limits on your account

### "Authentication failed"
- API key may be invalid or expired
- Generate a new key on the DeepSeek platform
- Check you're using the correct base URL

### Slow Responses
- DeepSeek V3 is fast, but network latency varies
- Consider caching frequent queries
- Monitor token usage for cost optimization

## Migration from Ollama

If you're migrating from the previous Ollama setup:

1. **No local installation needed** - DeepSeek is cloud-based
2. **Remove Ollama hooks** - Delete `.platform/hooks/postdeploy/02_setup_ollama.sh` etc.
3. **Re-sync embeddings** - Embedding dimensions may differ
4. **Update environment** - Remove `OLLAMA_*` variables, add `DEEPSEEK_*`

## Security Best Practices

- **Never commit API keys** to version control
- Use environment variables or secrets management
- Rotate API keys periodically
- Monitor usage for unexpected spikes
- Use IAM roles on AWS when possible

## Further Reading

- [DeepSeek API Documentation](https://api-docs.deepseek.com/)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [OpenAI SDK Compatibility](https://api-docs.deepseek.com/guides/openai-compatibility)
