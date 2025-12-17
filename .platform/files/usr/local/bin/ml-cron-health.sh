# Health check script for ML cron jobs
LOG_RETRAIN="/var/log/ml-retrain.log"
LOG_PREDICT="/var/log/ml-daily-predict.log"
HEALTH_LOG="/var/log/ml-cron-health.log"

log_health() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $HEALTH_LOG
}

# Check Retrain Job
if [ -f "$LOG_RETRAIN" ]; then
    LAST_RUN=$(tail -10 $LOG_RETRAIN | grep "Starting daily ML" | tail -1)
    if [ ! -z "$LAST_RUN" ]; then
        log_health "HEALTH: ML Retrain job log found with recent activity"
    else
        log_health "WARNING: ML Retrain job log exists but no recent activity found"
    fi
else
    log_health "ERROR: ML Retrain job log file not found at $LOG_RETRAIN"
fi

# Check Prediction (Daily) Job
if [ -f "$LOG_PREDICT" ]; then
    LAST_RUN=$(tail -10 $LOG_PREDICT | grep "Starting daily ML prediction snapshot" | tail -1)
    if [ ! -z "$LAST_RUN" ]; then
        log_health "HEALTH: ML Daily Prediction job log found with recent activity"
    else
        log_health "WARNING: ML Daily Prediction job log exists but no recent activity found"
    fi
else
    log_health "ERROR: ML Daily Prediction job log file not found at $LOG_PREDICT"
fi

# Check crontab files
for job in "ml-cron-retrain" "ml-cron-daily-predict"; do
    if [ -f "/etc/cron.d/$job" ]; then
        log_health "HEALTH: Cron job $job found in /etc/cron.d/"
    else
        log_health "ERROR: Cron job $job NOT found in /etc/cron.d/"
    fi
done
