#!/bin/bash
# Setup Ollama on Elastic Beanstalk instance for local AI inference
# This installs Ollama and pulls a small 1B model for the chatbot

set -e

echo "Starting Ollama setup..."

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "Ollama is already installed at $(which ollama)"
    OLLAMA_VERSION=$(ollama --version 2>&1 || echo "unknown")
    echo "Version: $OLLAMA_VERSION"
else
    echo "Installing Ollama..."

    # Download and install Ollama
    curl -fsSL https://ollama.com/install.sh | sh

    if [ $? -eq 0 ]; then
        echo "Ollama installed successfully"
    else
        echo "ERROR: Failed to install Ollama"
        exit 1
    fi
fi

# Start Ollama service in background if not already running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service..."
    nohup ollama serve > /var/log/ollama.log 2>&1 &
    OLLAMA_PID=$!
    echo "Ollama started with PID: $OLLAMA_PID"

    # Wait for Ollama to be ready
    echo "Waiting for Ollama to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "ERROR: Ollama failed to start within 30 seconds"
            exit 1
        fi
        sleep 1
    done
else
    echo "Ollama is already running"
fi

# Determine which model to use based on environment variable or default to qwen2.5:0.5b
CHAT_MODEL=${OLLAMA_CHAT_MODEL:-"qwen2.5:0.5b"}
EMBED_MODEL=${OLLAMA_EMBED_MODEL:-"nomic-embed-text"}

echo "Checking for chat model: $CHAT_MODEL"

# Check if chat model is already pulled
MODEL_EXISTS=$(ollama list | grep -c "${CHAT_MODEL%:*}" || echo "0")

if [ "$MODEL_EXISTS" -eq "0" ]; then
    echo "Pulling chat model: $CHAT_MODEL (this may take a few minutes)..."
    ollama pull "$CHAT_MODEL"

    if [ $? -eq 0 ]; then
        echo "Chat model $CHAT_MODEL pulled successfully"
    else
        echo "WARNING: Failed to pull chat model $CHAT_MODEL"
        # Try fallback to tinyllama
        echo "Attempting fallback to tinyllama:1.1b..."
        ollama pull tinyllama:1.1b
    fi
else
    echo "Chat model $CHAT_MODEL is already available"
fi

echo "Checking for embedding model: $EMBED_MODEL"

# Check if embedding model is already pulled
EMBED_EXISTS=$(ollama list | grep -c "${EMBED_MODEL%:*}" || echo "0")

if [ "$EMBED_EXISTS" -eq "0" ]; then
    echo "Pulling embedding model: $EMBED_MODEL..."
    ollama pull "$EMBED_MODEL"

    if [ $? -eq 0 ]; then
        echo "Embedding model $EMBED_MODEL pulled successfully"
    else
        echo "WARNING: Failed to pull embedding model $EMBED_MODEL"
    fi
else
    echo "Embedding model $EMBED_MODEL is already available"
fi

# List all available models
echo "Available Ollama models:"
ollama list

echo "Ollama setup complete!"
echo "Chat model: $CHAT_MODEL"
echo "Embed model: $EMBED_MODEL"
echo "Ollama is running on http://localhost:11434"