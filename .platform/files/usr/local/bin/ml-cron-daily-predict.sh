#!/bin/bash

# Source environment variables (Elastic Beanstalk specific)
# This is critical for CRON_SECRET and other env vars to be available to cron
export $(/opt/elasticbeanstalk/bin/get-config environment | jq -r 'to_entries | .[] | "\(.key)=\(.value)"') 2>/dev/null || true

# Fallback for older Amazon Linux 2 platforms if method above fails
if [ -z "$CRON_SECRET" ]; then
    source /opt/elasticbeanstalk/support/envvars 2>/dev/null || true
fi

# Configuration
LOG_FILE="/var/log/ml-daily-predict.log"
APP_URL="http://localhost"
CRON_SECRET="${CRON_SECRET:-your-secret-key}" # Will use env var if sourced correctly

# Function to log with timestamp
log_with_timestamp() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

# Ensure log file exists and is writable
touch $LOG_FILE
chmod 644 $LOG_FILE

log_with_timestamp "=== Starting daily ML prediction snapshot ==="
log_with_timestamp "Using CRON_SECRET: ${CRON_SECRET:0:5}..." # Log first 5 chars only
log_with_timestamp "Target URL: $APP_URL/ml/cron/predict_daily"
log_with_timestamp "Env check: CRON_SECRET is present? $([ -z "$CRON_SECRET" ] && echo "NO" || echo "YES")"

# Check if the application is running
if ! curl -s --connect-timeout 5 $APP_URL/health > /dev/null 2>&1; then
    log_with_timestamp "WARNING: Application health check failed, proceeding anyway..."
else
    log_with_timestamp "Application health check passed"
fi

# Make the API call to generate daily predictions
log_with_timestamp "Generating predictions..."

# Increased timeout for prediction generation (can take a while)
RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
  --connect-timeout 30 \
  --max-time 600 \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: $CRON_SECRET" \
  $APP_URL/ml/cron/predict_daily 2>&1)

# Parse response
HTTP_STATUS=$(echo $RESPONSE | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
HTTP_BODY=$(echo $RESPONSE | sed -e 's/HTTPSTATUS:.*//g')

# Log results
if [ "$HTTP_STATUS" -eq 200 ]; then
    log_with_timestamp "SUCCESS: Daily predictions generated successfully (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response details: $HTTP_BODY"

    # Extract key metrics from response if available
    if echo "$HTTP_BODY" | grep -q "records"; then
        RECORDS=$(echo "$HTTP_BODY" | grep -o '"records":[0-9]*' | cut -d: -f2)
        S3_KEY=$(echo "$HTTP_BODY" | grep -o '"s3_key":"[^"]*"' | cut -d: -f2 | tr -d '"')

        if [ ! -z "$RECORDS" ]; then
            log_with_timestamp "Saved $RECORDS work order predictions"
        fi
        if [ ! -z "$S3_KEY" ]; then
            log_with_timestamp "Saved to S3: $S3_KEY"
        fi
    fi

elif [ "$HTTP_STATUS" -eq 401 ]; then
    log_with_timestamp "ERROR: Authentication failed - check CRON_SECRET (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ "$HTTP_STATUS" -eq 400 ]; then
    log_with_timestamp "ERROR: Bad request - possibly no model loaded (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ "$HTTP_STATUS" -eq 500 ]; then
    log_with_timestamp "ERROR: Server error during prediction (HTTP $HTTP_STATUS)"
    log_with_timestamp "Response: $HTTP_BODY"

elif [ -z "$HTTP_STATUS" ]; then
    log_with_timestamp "ERROR: No response from server - connection failed"
    log_with_timestamp "Full response: $RESPONSE"

else
    log_with_timestamp "ERROR: Unexpected HTTP status $HTTP_STATUS"
    log_with_timestamp "Response: $HTTP_BODY"
fi

# Log completion
log_with_timestamp "=== Daily ML prediction snapshot completed ==="
log_with_timestamp ""
