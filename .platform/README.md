# Platform Hooks and Files

This directory contains Elastic Beanstalk platform hooks and files that are deployed to the EC2 instances.

## Structure

```
.platform/
├── hooks/
│   └── postdeploy/
│       └── 01_setup_ml_cron.sh    # Sets up ML model retraining cron jobs
└── files/
    └── usr/local/bin/
        ├── ml-cron-retrain.sh     # Daily ML model retraining script
        └── ml-cron-health.sh      # Cron job health check script
```

## ML Cron Jobs

### Test Mode (Current)
- **Retrain**: Runs every 5 minutes for immediate verification
- **Health Check**: Runs every 10 minutes

### Production Mode
To switch to production schedule, edit `01_setup_ml_cron.sh` and change:
- Retrain: `*/5 * * * *` → `0 2 * * *` (daily at 2:00 AM)
- Health: `*/10 * * * *` → `0 3 * * *` (daily at 3:00 AM)

### Logs
- **Retrain log**: `/var/log/ml-retrain.log`
- **Health log**: `/var/log/ml-cron-health.log`

View logs with: `eb logs` or in EB Console → Logs → Request Logs

### Environment Variables Required
- `CRON_SECRET`: Authentication secret for cron endpoint (set in EB console)

## Why Platform Hooks?

Previously used `.ebextensions/cron.config` with `container_commands`, but these run in a temporary deploy container and don't persist on the actual EC2 instance. Platform hooks run directly on the instance after deployment.
