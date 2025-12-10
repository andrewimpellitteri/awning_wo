#!/bin/bash
# Setup Ollama on Elastic Beanstalk instance for local AI inference
# This installs Ollama from S3 and pulls a small 1B model for the chatbot

set -e

echo "Starting Ollama setup..."

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "Ollama is already installed at $(which ollama)"
    OLLAMA_VERSION=$(ollama --version 2>&1 || echo "unknown")
    echo "Version: $OLLAMA_VERSION"
else
    echo "Installing Ollama from S3..."

    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    cd $TEMP_DIR

    # Download Ollama binary from S3 (replace with your bucket name and path)
    S3_BUCKET="awning-cleaning-data"  # REPLACE WITH YOUR ACTUAL BUCKET NAME
    S3_KEY="ollama/ollama-linux-amd64.tgz"  # REPLACE WITH YOUR ACTUAL PATH
    
    echo "Downloading Ollama binary from s3://$S3_BUCKET/$S3_KEY"
    aws s3 cp "s3://$S3_BUCKET/$S3_KEY" "ollama-linux-amd64.tgz" --region us-east-1
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to download Ollama binary from S3"
        exit 1
    fi
    
    echo "Extracting Ollama binary..."
    sudo tar -xzf ollama-linux-amd64.tgz -C /usr
    
    # Create symlink to make it accessible in PATH
    sudo ln -sf /usr/ollama /usr/local/bin/ollama
    
    # Create ollama user and set up permissions
    echo "Setting up ollama user and permissions..."
    sudo useradd -r -s /bin/false ollama 2>/dev/null || true
    sudo mkdir -p /etc/ollama
    sudo chown ollama:ollama /etc/ollama
    
    # Clean up
    cd ..
    rm -rf $TEMP_DIR
    
    if command -v ollama &> /dev/null; then
        echo "Ollama installed successfully from S3"
    else
        echo "ERROR: Ollama installation failed"
        exit 1
    fi
fi

# Start Ollama service in background if not already running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service..."
    sudo systemctl start ollama 2>/dev/null || {
        echo "Systemd service not available, starting manually..."
        nohup ollama serve > /var/log/ollama.log 2>&1 &
        OLLAMA_PID=$!
        echo "Ollama started with PID: $OLLAMA_PID"
    }
    
    # Wait for Ollama to be ready
    echo "Waiting for Ollama to be ready..."
    for i in {1..60}; do  # Increased timeout to 60 seconds
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama is ready!"
            break
        fi
        if [ $i -eq 60 ]; then
            echo "ERROR: Ollama failed to start within 60 seconds"
            echo "Last 20 lines of ollama log:"
            tail -20 /var/log/ollama.log 2>/dev/null || echo "No log file found"
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
MODEL_EXISTS=$(ollama list 2>/dev/null | grep -c "${CHAT_MODEL%:*}" || echo "0")

if [ "$MODEL_EXISTS" -eq "0" ]; then
    echo "Pulling chat model: $CHAT_MODEL (this may take a few minutes)..."
    
    # Add retry logic for model pulling
    MAX_RETRIES=3
    RETRY_DELAY=10
    
    for attempt in $(seq 1 $MAX_RETRIES); do
        if ollama pull "$CHAT_MODEL"; then
            echo "Chat model $CHAT_MODEL pulled successfully on attempt $attempt"
            break
        else
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "WARNING: Failed to pull chat model $CHAT_MODEL after $MAX_RETRIES attempts"
                # Try fallback to tinyllama
                echo "Attempting fallback to tinyllama:1.1b..."
                ollama pull tinyllama:1.1b
            else
                echo "Attempt $attempt failed, retrying in $RETRY_DELAY seconds..."
                sleep $RETRY_DELAY
            fi
        fi
    done
else
    echo "Chat model $CHAT_MODEL is already available"
fi

echo "Checking for embedding model: $EMBED_MODEL"

# Check if embedding model is already pulled
EMBED_EXISTS=$(ollama list 2>/dev/null | grep -c "${EMBED_MODEL%:*}" || echo "0")

if [ "$EMBED_EXISTS" -eq "0" ]; then
    echo "Pulling embedding model: $EMBED_MODEL..."
    
    # Add retry logic for model pulling
    MAX_RETRIES=3
    RETRY_DELAY=10
    
    for attempt in $(seq 1 $MAX_RETRIES); do
        if ollama pull "$EMBED_MODEL"; then
            echo "Embedding model $EMBED_MODEL pulled successfully on attempt $attempt"
            break
        else
            if [ $attempt -eq $MAX_RETRIES ]; then
                echo "WARNING: Failed to pull embedding model $EMBED_MODEL after $MAX_RETRIES attempts"
            else
                echo "Attempt $attempt failed, retrying in $RETRY_DELAY seconds..."
                sleep $RETRY_DELAY
            fi
        fi
    done
else
    echo "Embedding model $EMBED_MODEL is already available"
fi

# List all available models
echo "Available Ollama models:"
ollama list 2>/dev/null || echo "No models available or ollama not responding"

echo "Ollama setup complete!"
echo "Chat model: $CHAT_MODEL"
echo "Embed model: $EMBED_MODEL"
echo "Ollama is running on http://localhost:11434"