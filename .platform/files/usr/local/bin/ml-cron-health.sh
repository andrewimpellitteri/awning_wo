#!/bin/bash

# Health check script for ML cron job
LOG_FILE="/var/log/ml-retrain.log"
HEALTH_LOG="/var/log/ml-cron-health.log"

log_health() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $HEALTH_LOG
}

# Check if main log exists and has recent entries
if [ -f "$LOG_FILE" ]; then
    LAST_RUN=$(tail -10 $LOG_FILE | grep "Starting daily ML" | tail -1)
    if [ ! -z "$LAST_RUN" ]; then
        log_health "HEALTH: ML cron job log found with recent activity"
    else
        log_health "WARNING: ML cron job log exists but no recent activity found"
    fi
else
    log_health "ERROR: ML cron job log file not found at $LOG_FILE"
fi

# Check if cron job is in cron.d
if [ -f "/etc/cron.d/ml-cron-retrain" ]; then
    log_health "HEALTH: ML cron job found in /etc/cron.d/"
else
    log_health "ERROR: ML cron job not found in /etc/cron.d/"
fi
