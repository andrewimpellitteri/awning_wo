#!/bin/bash
set -e

CRON_DIR="/etc/cron.d"
CRON_FILE_RETRAIN="$CRON_DIR/ml-cron-retrain"
CRON_FILE_PREDICT="$CRON_DIR/ml-cron-weekly-predict"
CRON_FILE_HEALTH="$CRON_DIR/ml-cron-health"

SCRIPT_RETRAIN="/usr/local/bin/ml-cron-retrain.sh"
SCRIPT_PREDICT="/usr/local/bin/ml-cron-weekly-predict.sh"
SCRIPT_HEALTH="/usr/local/bin/ml-cron-health.sh"
LOG_FILE="/var/log/ml-retrain.log"
PREDICT_LOG="/var/log/ml-weekly-predict.log"
HEALTH_LOG="/var/log/ml-cron-health.log"

# Copy scripts from app directory to /usr/local/bin (EB doesn't auto-copy .platform/files)
cp -f /var/app/current/.platform/files/usr/local/bin/ml-cron-retrain.sh "$SCRIPT_RETRAIN"
cp -f /var/app/current/.platform/files/usr/local/bin/ml-cron-weekly-predict.sh "$SCRIPT_PREDICT"
cp -f /var/app/current/.platform/files/usr/local/bin/ml-cron-health.sh "$SCRIPT_HEALTH"

# Ensure scripts are executable
chmod +x "$SCRIPT_RETRAIN" "$SCRIPT_PREDICT" "$SCRIPT_HEALTH"

# PRODUCTION MODE: Run daily at 2:00 AM
cat <<EOF > "$CRON_FILE_RETRAIN"
CRON_SECRET=${CRON_SECRET}
0 2 * * * root $SCRIPT_RETRAIN >> $LOG_FILE 2>&1
EOF

# [TESTING MODE] Run every 2 minutes for verification
cat <<EOF > "$CRON_FILE_PREDICT"
CRON_SECRET=${CRON_SECRET}
*/2 * * * * root $SCRIPT_PREDICT >> $PREDICT_LOG 2>&1
EOF

# Health check runs daily at 3:00 AM (after retrain)
cat <<EOF > "$CRON_FILE_HEALTH"
0 3 * * * root $SCRIPT_HEALTH >> $HEALTH_LOG 2>&1
EOF

# Set permissions and ownership
chmod 644 "$CRON_FILE_RETRAIN" "$CRON_FILE_PREDICT" "$CRON_FILE_HEALTH"
chown root:root "$CRON_FILE_RETRAIN" "$CRON_FILE_PREDICT" "$CRON_FILE_HEALTH"

# Create log files
touch "$LOG_FILE" "$PREDICT_LOG" "$HEALTH_LOG"
chmod 644 "$LOG_FILE" "$PREDICT_LOG" "$HEALTH_LOG"

# Make sure cron service is running
service crond restart || systemctl restart crond || true

echo "✅ ML cron jobs installed successfully (PREDICT: */2 * * * *)"
echo "Retrain Cron:"
cat "$CRON_FILE_RETRAIN"
echo "Predict Cron:"
cat "$CRON_FILE_PREDICT"
