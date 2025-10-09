#!/bin/bash

# Configuration
LOG_FILE="/var/log/ml-retrain.log"
APP_URL="http://localhost"
CRON_SECRET="${CRON_SECRET:-your-secret-key}"

# Function to log with timestamp
log_with_timestamp() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

# Ensure log file exists and is writable
touch $LOG_FILE
chmod 644 $LOG_FILE

log_with_timestamp "=== Starting daily ML model retraining ==="
log_with_timestamp "Using CRON_SECRET: ${CRON_SECRET:0:10}..." # Log first 10 chars only
log_with_timestamp "Target URL: $APP_URL/ml/cron/retrain"

# Check if the application is running
if ! curl -s --connect-timeout 5 $APP_URL/health > /dev/null 2>&1; then
    log_with_timestamp "WARNING: Application health check failed, proceeding anyway..."
else
    log_with_timestamp "Application health check passed"
fi

# Make the API call to retrain the model
log_with_timestamp "Initiating model retraining..."

RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
  --connect-timeout 30 \
  --max-time 600 \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: $CRON_SECRET" \
  -d '{"config": "deep_wide"}' \
  $APP_URL/ml/cron/retrain 2>&1)

# Parse response
HTTP_STATUS=$(echo $RESPONSE | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
HTTP_BODY=$(echo $RESPONSE | sed -e 's/HTTPSTATUS:.*//g')

# Log results
if [ "$HTTP_STATUS" -eq 200 ]; then
    log_with_timestamp "SUCCESS: Model retrained successfully (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response details: $HTTP_BODY"

    # Extract key metrics from response if available
    if echo "$HTTP_BODY" | grep -q "mae"; then
        MAE=$(echo "$HTTP_BODY" | grep -o '"mae":[0-9.]*' | cut -d: -f2)
        SAMPLES=$(echo "$HTTP_BODY" | grep -o '"samples_trained":[0-9]*' | cut -d: -f2)
        MODEL_NAME=$(echo "$HTTP_BODY" | grep -o '"model_name":"[^"]*"' | cut -d: -f2 | tr -d '"')

        if [ ! -z "$MAE" ] && [ ! -z "$SAMPLES" ]; then
            log_with_timestamp "Training metrics - MAE: $MAE, Samples: $SAMPLES"
        fi
        if [ ! -z "$MODEL_NAME" ]; then
            log_with_timestamp "Model saved as: $MODEL_NAME"
        fi
    fi

elif [ "$HTTP_STATUS" -eq 401 ]; then
    log_with_timestamp "ERROR: Authentication failed - check CRON_SECRET (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ "$HTTP_STATUS" -eq 400 ]; then
    log_with_timestamp "ERROR: Bad request - possibly insufficient data (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ "$HTTP_STATUS" -eq 500 ]; then
    log_with_timestamp "ERROR: Server error during training (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ -z "$HTTP_STATUS" ]; then
    log_with_timestamp "ERROR: No response from server - connection failed"
    log_with_timestamp "Full response: $RESPONSE"

else
    log_with_timestamp "ERROR: Unexpected HTTP status $HTTP_STATUS"
    log_with_timestamp "Response: $HTTP_BODY"
fi

# Log completion
log_with_timestamp "=== Daily ML model retraining completed ==="
log_with_timestamp ""
