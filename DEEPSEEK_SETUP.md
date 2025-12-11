# DeepSeek API Setup for RAG Chatbot

This document describes the DeepSeek API integration for the RAG chatbot.

## Overview

The chatbot uses a **hybrid architecture**:
- **DeepSeek V3** for chat completions and function calling
- **OpenAI** for embeddings (more reliable than DeepSeek's embedding API)

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
| `OPENAI_API_KEY` | **Yes** | - | Your OpenAI API key (for embeddings) |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | DeepSeek API base URL |
| `DEEPSEEK_CHAT_MODEL` | No | `deepseek-chat` | Chat model to use |
| `OPENAI_EMBED_MODEL` | No | `text-embedding-3-small` | Embedding model |
| `USE_OPENAI_EMBEDDINGS` | No | `true` | Use OpenAI for embeddings |

### Getting API Keys

**DeepSeek:**
1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Create an account and navigate to API Keys
3. Create and copy your API key

**OpenAI:**
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Go to API Keys section
3. Create and copy your API key

## Local Development Setup

### Option 1: Export in Terminal
```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
export OPENAI_API_KEY="sk-your-openai-key"
python app.py
```

### Option 2: Create a .env File
```bash
# Create .env file (don't commit this!)
cat > .env << 'EOF'
DEEPSEEK_API_KEY=sk-your-deepseek-key
OPENAI_API_KEY=sk-your-openai-key
EOF
```

### Option 3: Use direnv (Recommended)
```bash
# Create .envrc file
cat > .envrc << 'EOF'
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
export OPENAI_API_KEY="sk-your-openai-key"
EOF

# Allow direnv
direnv allow
```

## AWS Elastic Beanstalk Setup

### Set Environment Variables

Using EB CLI:
```bash
eb setenv DEEPSEEK_API_KEY="sk-your-deepseek-key" OPENAI_API_KEY="sk-your-openai-key"
```

Or via AWS Console:
1. Go to Elastic Beanstalk → your environment
2. Configuration → Software → Edit
3. Add both API keys under Environment properties
4. Click Apply

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

## Pricing (as of Dec 2024)

| Service | Model | Cost |
|---------|-------|------|
| DeepSeek | deepseek-chat | $0.14/M input, $0.28/M output |
| OpenAI | text-embedding-3-small | $0.02/M tokens |

**Estimated monthly cost** (moderate usage): $5-20

## Syncing Embeddings

**Important:** Embedding dimension changed from 768 → 1536. You must re-sync!

```bash
# Sync all embeddings
python scripts/sync_embeddings.py --type all --verbose

# Check status
python scripts/sync_embeddings.py --status
```

## Database Schema Update

If your `embedding` columns are still 768-dimensional, you may need to update them:

```sql
-- Check current dimension
SELECT array_length(embedding, 1) FROM customer_embeddings LIMIT 1;

-- If 768, the sync script will handle it automatically
-- Just clear old embeddings and re-sync
TRUNCATE customer_embeddings, work_order_embeddings, item_embeddings;
```

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
  "embed_model": "text-embedding-3-small"
}
```

## Troubleshooting

### "DEEPSEEK_API_KEY environment variable is not set"
- Ensure the environment variable is exported
- On EB, verify via `eb printenv`

### "OPENAI_API_KEY environment variable is not set"
- OpenAI key is required for embeddings
- Set it alongside the DeepSeek key

### "Failed to generate embedding"
- Check OpenAI API key is valid
- Verify OpenAI API status
- Check rate limits

### Tool calls not working
- Ensure DeepSeek API key is valid
- `deepseek-chat` model supports function calling
- Check the response metadata for tool call info

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
│     (Semantic search mode - legacy)     │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌──────────┐         ┌──────────────┐
│  OpenAI  │         │   pgvector   │
│ Embeddings│        │    Search    │
└──────────┘         └──────────────┘
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
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
