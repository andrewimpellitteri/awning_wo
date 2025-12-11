# DeepSeek API Setup for RAG Chatbot

This document describes the DeepSeek API integration for the RAG chatbot.

## Overview

The chatbot uses a **hybrid architecture**:
- **DeepSeek V3** for chat completions and function calling (paid API)
- **Local embeddings** via sentence-transformers (free, no API needed)

### Two Chat Modes

| Mode | Function | Use Case |
|------|----------|----------|
| `chat_with_rag()` | Semantic search + context injection | General questions, fuzzy matching |
| `chat_with_tools()` | Function calling with database queries | Specific lookups, precise queries |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | **Yes** | - | Your DeepSeek API key (for chat) |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | DeepSeek API base URL |
| `DEEPSEEK_CHAT_MODEL` | No | `deepseek-chat` | Chat model to use |
| `LOCAL_EMBED_MODEL` | No | `all-MiniLM-L6-v2` | Local embedding model |

### Getting a DeepSeek API Key

1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Create an account and navigate to API Keys
3. Create and copy your API key

## Local Embedding Models

Embeddings run **locally** using sentence-transformers - no API or payment needed!

| Model | Dimensions | Size | Quality | Speed |
|-------|------------|------|---------|-------|
| `all-MiniLM-L6-v2` (default) | 384 | ~80MB | Good | Very Fast |
| `all-mpnet-base-v2` | 768 | ~420MB | Better | Fast |
| `all-MiniLM-L12-v2` | 384 | ~120MB | Good | Fast |

The model downloads automatically on first use and is cached locally.

To change the model:
```bash
export LOCAL_EMBED_MODEL="all-mpnet-base-v2"
```

## Local Development Setup

### Option 1: Export in Terminal
```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
python app.py
```

### Option 2: Create a .env File
```bash
# Create .env file (don't commit this!)
echo 'DEEPSEEK_API_KEY=sk-your-deepseek-key' > .env
```

### Option 3: Use direnv (Recommended)
```bash
# Create .envrc file
echo 'export DEEPSEEK_API_KEY="sk-your-deepseek-key"' > .envrc

# Allow direnv
direnv allow
```

## AWS Elastic Beanstalk Setup

### Set Environment Variables

Using EB CLI:
```bash
eb setenv DEEPSEEK_API_KEY="sk-your-deepseek-key"
```

Or via AWS Console:
1. Go to Elastic Beanstalk → your environment
2. Configuration → Software → Edit
3. Add `DEEPSEEK_API_KEY` under Environment properties
4. Click Apply

**Note:** The embedding model (~80MB) will be downloaded on first request. Consider using a larger instance type if memory is constrained.

## Available Tools (Function Calling)

The chatbot has these read-only tools for database queries:

| Tool | Description |
|------|-------------|
| `search_customers` | Search customers by name, ID, contact, email |
| `get_customer_details` | Get full customer info + work order history |
| `search_work_orders` | Search work orders by number, status, customer |
| `get_work_order_details` | Get work order with all items |
| `get_customer_work_orders` | List all work orders for a customer |
| `search_items` | Search items by description, material, color |
| `get_work_order_stats` | Get counts and statistics |

### Example Queries

The chatbot will automatically use tools for questions like:
- "Find customer John Smith" → `search_customers`
- "Show me work order WO12345" → `get_work_order_details`
- "How many work orders does ABC Corp have?" → `get_customer_work_orders`
- "Find all blue canvas items" → `search_items`

## Pricing

| Service | Cost |
|---------|------|
| DeepSeek chat | $0.14/M input, $0.28/M output |
| Local embeddings | **Free** |

**Estimated monthly cost** (moderate usage): $2-10

## Syncing Embeddings

**Important:** Embedding dimension is now 384 (was 768/1536). You must re-sync!

```bash
# Sync all embeddings
python scripts/sync_embeddings.py --type all --verbose

# Check status
python scripts/sync_embeddings.py --status
```

## Database Schema Update

If your `embedding` columns were sized for a different dimension:

```sql
-- Check current dimension
SELECT array_length(embedding, 1) FROM customer_embeddings LIMIT 1;

-- If not 384, clear and re-sync
TRUNCATE customer_embeddings, work_order_embeddings, item_embeddings;
```

Then run the sync script.

## Health Monitoring

Check chatbot status:
```bash
curl http://localhost:5000/api/chat/status
```

Returns:
```json
{
  "api_available": true,
  "api_configured": true,
  "chat_model": "deepseek-chat",
  "embed_model": "all-MiniLM-L6-v2",
  "embed_model_local": true,
  "embed_dimension": 384
}
```

## Troubleshooting

### "DEEPSEEK_API_KEY environment variable is not set"
- Ensure the environment variable is exported
- On EB, verify via `eb printenv`

### "Failed to generate embedding"
- The sentence-transformers model may need to download (~80MB)
- Check disk space and network connectivity
- Verify PyTorch/sentence-transformers are installed

### Tool calls not working
- Ensure DeepSeek API key is valid
- `deepseek-chat` model supports function calling
- Check the response metadata for tool call info

### Slow first request
- The embedding model downloads on first use
- Subsequent requests will be fast (model is cached)

## Architecture Diagram

```
User Question
      │
      ▼
┌─────────────────────────────────────────┐
│           chat_with_tools()             │
│  (Function calling mode - preferred)    │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌──────────┐         ┌──────────────┐
│ DeepSeek │         │   Database   │
│   Chat   │◄───────►│   Queries    │
│   API    │  tools  │  (read-only) │
└──────────┘         └──────────────┘
      │
      ▼
   Response

--- OR ---

User Question
      │
      ▼
┌─────────────────────────────────────────┐
│            chat_with_rag()              │
│     (Semantic search mode)              │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌──────────────┐     ┌──────────────┐
│    Local     │     │   pgvector   │
│  Embeddings  │     │    Search    │
│ (free, fast) │     └──────────────┘
└──────────────┘            │
      │                     │
      └──────────┬──────────┘
                 ▼
          ┌──────────┐
          │ DeepSeek │
          │   Chat   │
          │   API    │
          └──────────┘
                 │
                 ▼
             Response
```

## Further Reading

- [DeepSeek API Documentation](https://api-docs.deepseek.com/)
- [DeepSeek Function Calling](https://api-docs.deepseek.com/guides/function_calling)
- [Sentence Transformers](https://www.sbert.net/)
- [Hugging Face Model Hub](https://huggingface.co/sentence-transformers)
