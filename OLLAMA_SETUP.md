# Ollama Local Setup for Elastic Beanstalk

This document describes the local Ollama installation for the RAG chatbot on AWS Elastic Beanstalk.

## Overview

The chatbot now runs **entirely on the EB instance** using a small 1B language model, eliminating the need for external Ollama servers.

## Configuration

### Default Models
- **Chat Model**: `qwen2.5:0.5b` (500MB, ultra-fast 0.5B parameter model)
- **Embedding Model**: `nomic-embed-text` (274MB, specialized for semantic search)

### Fallback Chain
If the primary chat model fails, the system automatically tries:
1. `qwen2.5:0.5b` (default)
2. `tinyllama:1.1b`
3. `llama3.2:1b`
4. `llama3.2` (full size)

## Installation

Ollama is automatically installed and configured during EB deployment via hooks in `.platform/hooks/postdeploy/`:

- `02_setup_ollama.sh` - Installs Ollama and pulls models
- `03_install_ollama_service.sh` - Sets up systemd service for persistence

## Systemd Service

Ollama runs as a systemd service (`ollama.service`) that:
- Starts automatically on boot
- Restarts on failure
- Logs to `/var/log/ollama.log`

### Service Management
```bash
# Check status
sudo systemctl status ollama

# View logs
sudo journalctl -u ollama -f

# Restart service
sudo systemctl restart ollama

# View Ollama application logs
tail -f /var/log/ollama.log
```

## Changing Models

### Via Environment Variables

Set these in EB configuration:

```bash
eb setenv OLLAMA_CHAT_MODEL="tinyllama:1.1b"
eb setenv OLLAMA_EMBED_MODEL="nomic-embed-text"
```

### Recommended Small Models

**Chat Models (ordered by size):**
- `qwen2.5:0.5b` - 500MB (default, fastest)
- `tinyllama:1.1b` - 637MB (good balance)
- `llama3.2:1b` - 1.3GB (better quality)
- `phi3:mini` - 2.2GB (higher quality, slower)

**Embedding Models:**
- `nomic-embed-text` - 274MB (default, specialized for semantic search)
- `all-minilm` - 46MB (faster, lower quality)

### Manual Model Management

SSH into EB instance:
```bash
eb ssh

# List available models
ollama list

# Pull a new model
ollama pull qwen2.5:0.5b

# Remove a model
ollama rm llama3.2

# Test a model
ollama run qwen2.5:0.5b "Hello, world!"
```

## Performance Characteristics

### qwen2.5:0.5b (Default)
- **Size**: 500MB
- **Speed**: ~100 tokens/second on t3.small
- **Quality**: Good for simple queries, may struggle with complex reasoning
- **Best for**: Quick responses, simple Q&A

### tinyllama:1.1b
- **Size**: 637MB
- **Speed**: ~80 tokens/second on t3.small
- **Quality**: Better reasoning than 0.5B models
- **Best for**: General purpose, balanced quality/speed

### llama3.2:1b
- **Size**: 1.3GB
- **Speed**: ~50 tokens/second on t3.small
- **Quality**: Significantly better reasoning and coherence
- **Best for**: Complex queries, better context understanding

## Troubleshooting

### Ollama Not Starting
```bash
# Check service status
sudo systemctl status ollama

# View service logs
sudo journalctl -u ollama -n 50

# Manually start
sudo systemctl start ollama

# Check if port is in use
sudo lsof -i:11434
```

### Model Download Failures
```bash
# Check disk space
df -h

# Check network connectivity
curl -I https://ollama.com

# Manually pull with verbose output
ollama pull qwen2.5:0.5b --verbose
```

### High Memory Usage
- Switch to smaller model (`qwen2.5:0.5b`)
- Increase instance size (t3.small → t3.medium)
- Monitor with: `htop` or `free -h`

### Slow Responses
- Use smaller model (0.5b instead of 1b)
- Reduce context window in chat prompts
- Check CPU with: `top` or `htop`

## Health Monitoring

Check chatbot status via the application:
```bash
curl http://localhost/chatbot/status
```

This returns:
- Ollama running status
- Available models
- Current configuration

## Costs

Running Ollama locally on EB adds:
- **Storage**: ~1GB for models
- **Memory**: ~500MB-1GB RAM usage
- **CPU**: Minimal when idle, ~30-50% during generation

**Recommended Instance**: t3.small (2GB RAM, 2 vCPUs) - ~$15/month

## Fallback Behavior

If Ollama is unavailable, the chatbot will:
1. Check cache for recent status (60-second TTL)
2. Attempt connection to Ollama
3. Try fallback models in sequence
4. Return graceful error if all models fail

Error messages to users are clear and actionable.

## Security

- Ollama listens on `localhost:11434` only
- Not exposed to public internet
- Systemd service runs as `root` (required for Ollama)

## Further Reading

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Qwen2.5 Model Card](https://ollama.com/library/qwen2.5)
- [Nomic Embed Text](https://ollama.com/library/nomic-embed-text)
