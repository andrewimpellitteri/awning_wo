# Operations Runbook

## Overview

This runbook provides step-by-step procedures for common operational tasks, troubleshooting, and incident response for the Awning Management System running on AWS Elastic Beanstalk.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Deployment Procedures](#deployment-procedures)
- [Database Operations](#database-operations)
- [Monitoring & Alerts](#monitoring--alerts)
- [Incident Response](#incident-response)
- [Backup & Recovery](#backup--recovery)
- [Performance Tuning](#performance-tuning)
- [Maintenance Tasks](#maintenance-tasks)

---

## Daily Operations

### Health Checks

**Check application health:**
```bash
# Via browser
https://your-app-url.elasticbeanstalk.com/health

# Via curl
curl https://your-app-url.elasticbeanstalk.com/health

# Expected response:
# {"status": "healthy", "database": "connected", "timestamp": "2025-11-16T10:30:00Z"}
```

**Check EB environment status:**
```bash
eb status

# Expected output:
# Environment details for: awning-prod
# Status: Ready
# Health: Green
```

**Monitor logs:**
```bash
# Stream real-time logs
eb logs --stream

# Get recent logs
eb logs --all

# Check specific log file on instance
eb ssh
tail -f /var/log/eb-engine.log
tail -f /var/log/ml-retrain.log
```

### Database Health

**Check database connections:**
```bash
# SSH into EB instance
eb ssh

# Check PostgreSQL connectivity
python3 << EOF
from app import app, db
with app.app_context():
    try:
        db.session.execute('SELECT 1')
        print("✓ Database connected")
    except Exception as e:
        print(f"✗ Database error: {e}")
EOF
```

**Monitor RDS metrics (AWS Console):**
- CPU utilization (should be < 70%)
- Database connections (should be < max_connections * 0.8)
- Free storage space (should be > 20%)
- Read/write latency

### ML Model Status

**Check last model training:**
```bash
eb ssh
cat /var/log/ml-retrain.log | tail -50

# Look for:
# [2025-11-16 02:00:15] INFO: Model training completed
# [2025-11-16 02:00:15] INFO: MAE: 1.2, R2: 0.89
```

**Trigger manual retraining if needed:**
```bash
curl -X POST http://localhost/ml/cron/retrain \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: YOUR_CRON_SECRET" \
  -d '{"config": "baseline"}'
```

---

## Deployment Procedures

### Standard Deployment (No Schema Changes)

**Pre-deployment checklist:**
- [ ] All tests passing locally (`pytest`)
- [ ] Code reviewed and approved
- [ ] Changes committed to git
- [ ] No database schema changes

**Steps:**
```bash
# 1. Verify current state
eb status
git status

# 2. Ensure on correct branch
git checkout main
git pull origin main

# 3. Run tests
pytest

# 4. Deploy to EB
eb deploy

# 5. Monitor deployment
eb health --refresh

# 6. Verify deployment
curl https://your-app-url.com/health

# 7. Check logs for errors
eb logs --stream

# 8. Test critical functionality
# - Login
# - Create work order
# - View analytics dashboard
```

**Estimated downtime:** 0-2 minutes

**Rollback procedure:**
```bash
# List recent deployments
eb appversion lifecycle

# Rollback to previous version
eb use <previous-version-name>
eb deploy --version <previous-version-name>
```

### Deployment with Database Schema Changes

**Pre-deployment checklist:**
- [ ] Alembic migration created and tested
- [ ] Migration tested on test database
- [ ] Backup of production database created
- [ ] Downtime window scheduled (if needed)

**Steps:**
```bash
# 1. Test migration on test database
./alembic_db.sh test upgrade head

# 2. Verify migration succeeded
./alembic_db.sh test current

# 3. Backup production database (via RDS)
# AWS Console > RDS > Snapshots > Create Snapshot

# 4. Run migration on production
./alembic_db.sh prod upgrade head

# 5. Verify migration
./alembic_db.sh prod current

# 6. Deploy application code
git commit -am "Add new feature with migration"
eb deploy

# 7. Verify deployment
eb logs --stream
curl https://your-app-url.com/health

# 8. Test new feature
# Manual testing of affected functionality
```

**Rollback procedure:**
```bash
# 1. Rollback migration
./alembic_db.sh prod downgrade -1

# 2. Deploy previous version
eb deploy --version <previous-version>

# 3. If data corruption, restore RDS snapshot
# AWS Console > RDS > Snapshots > Restore
```

### Zero-Downtime Deployment (Blue/Green)

**For critical updates:**
```bash
# 1. Create new environment (green)
eb clone awning-prod --clone_name awning-prod-green

# 2. Deploy to green environment
eb use awning-prod-green
eb deploy

# 3. Test green environment
curl https://awning-prod-green.elasticbeanstalk.com/health

# 4. Swap CNAMEs (switch traffic)
eb swap awning-prod --destination_name awning-prod-green

# 5. Monitor for issues
eb logs --stream

# 6. If successful, terminate old environment
eb terminate awning-prod-old
```

---

## Database Operations

### Running Migrations

**Check current migration status:**
```bash
# Production database
./alembic_db.sh prod current

# Test database
./alembic_db.sh test current

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# abc123def456 (head)
```

**Create new migration:**
```bash
# 1. Modify model in models/
# 2. Generate migration
./alembic_db.sh test revision --autogenerate -m "add_new_field"

# 3. Review generated migration
cat alembic/versions/abc123_add_new_field.py

# 4. Test migration
./alembic_db.sh test upgrade head

# 5. Apply to production (after deployment)
./alembic_db.sh prod upgrade head
```

**Rollback migration:**
```bash
# Downgrade one version
./alembic_db.sh prod downgrade -1

# Downgrade to specific version
./alembic_db.sh prod downgrade abc123

# View migration history
./alembic_db.sh prod history
```

### Database Backup

**Manual backup (RDS snapshot):**
```bash
# Via AWS CLI
aws rds create-db-snapshot \
  --db-instance-identifier awning-prod-db \
  --db-snapshot-identifier awning-prod-manual-$(date +%Y%m%d-%H%M%S)

# Verify snapshot
aws rds describe-db-snapshots \
  --db-instance-identifier awning-prod-db
```

**Export data to CSV:**
```bash
eb ssh

# Export work orders
python3 << EOF
from app import app, db
from models.work_order import WorkOrder
import csv

with app.app_context():
    orders = WorkOrder.query.all()
    with open('/tmp/work_orders_backup.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['WorkOrderNo', 'CustomerName', 'Status', 'Price'])
        for order in orders:
            writer.writerow([
                order.WorkOrderNo,
                order.customer.CustomerName,
                order.Status,
                order.Price
            ])
    print("Backup saved to /tmp/work_orders_backup.csv")
EOF

# Download backup
exit  # Exit SSH
eb ssh --command "cat /tmp/work_orders_backup.csv" > work_orders_backup.csv
```

### Database Restore

**Restore from RDS snapshot:**
```bash
# 1. List available snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier awning-prod-db

# 2. Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier awning-prod-db-restored \
  --db-snapshot-identifier <snapshot-id>

# 3. Update DATABASE_URL in EB
eb setenv DATABASE_URL="postgresql://user:pass@new-host:5432/dbname"

# 4. Restart application
eb restart
```

### Database Maintenance

**Analyze and vacuum (PostgreSQL):**
```bash
# Connect to database
eb ssh
psql $DATABASE_URL

# Run maintenance
VACUUM ANALYZE;

# Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Monitoring & Alerts

### CloudWatch Dashboards

**Key metrics to monitor:**
- Application health status
- HTTP 4xx/5xx error rates
- Database CPU utilization
- Database connections
- Disk space usage
- Memory utilization

**Access CloudWatch:**
```bash
# Via AWS Console
AWS Console > CloudWatch > Dashboards > Awning-Prod

# Via CLI
aws cloudwatch get-dashboard \
  --dashboard-name Awning-Prod
```

### Setting Up Alarms

**Create CloudWatch alarm for 500 errors:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name awning-prod-5xx-errors \
  --alarm-description "Alert on high 5xx errors" \
  --metric-name ApplicationRequests5xx \
  --namespace AWS/ElasticBeanstalk \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789:awning-alerts
```

**Database connection alarm:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name awning-prod-db-connections \
  --alarm-description "Alert on high DB connections" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Log Analysis

**Search logs for errors:**
```bash
# Get last 500 lines of logs
eb logs --all > logs.txt

# Search for errors
grep -i "error" logs.txt
grep -i "exception" logs.txt
grep "500 Internal Server Error" logs.txt

# Count errors by type
grep -i "error" logs.txt | cut -d' ' -f5- | sort | uniq -c | sort -rn
```

**CloudWatch Insights queries:**
```sql
-- Top errors in last hour
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() by @message
| sort count desc
| limit 20

-- Slow requests (>1 second)
fields @timestamp, @message
| filter @message like /request took/
| parse @message /request took * ms/ as duration
| filter duration > 1000
| sort duration desc
```

---

## Incident Response

### Application Down

**Symptoms:**
- Health check returning 503/504
- Users unable to access application
- EB environment status "Degraded" or "Severe"

**Immediate actions:**
```bash
# 1. Check EB environment health
eb health --refresh

# 2. Check logs for errors
eb logs --stream | grep -i "error\|exception\|critical"

# 3. Check database connectivity
eb ssh
python3 -c "from app import app, db; app.app_context().push(); db.session.execute('SELECT 1')"

# 4. Restart application
eb restart

# 5. If restart fails, deploy last known good version
eb deploy --version <last-good-version>
```

**Common causes:**
- Database connection pool exhausted
- Out of memory
- Unhandled exception in critical code path
- RDS maintenance window

### Database Connection Issues

**Symptoms:**
- "Could not connect to database" errors
- Slow page loads
- Timeout errors

**Diagnosis:**
```bash
# 1. Check RDS status
aws rds describe-db-instances \
  --db-instance-identifier awning-prod-db \
  --query 'DBInstances[0].DBInstanceStatus'

# 2. Check database connections
eb ssh
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# 3. Check for long-running queries
psql $DATABASE_URL -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;"
```

**Resolution:**
```bash
# 1. Kill long-running queries
psql $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '5 minutes';"

# 2. Increase connection pool size (if needed)
eb setenv SQLALCHEMY_POOL_SIZE=20 SQLALCHEMY_MAX_OVERFLOW=30
eb restart

# 3. Scale RDS instance (if persistent)
aws rds modify-db-instance \
  --db-instance-identifier awning-prod-db \
  --db-instance-class db.t3.medium \
  --apply-immediately
```

### High Memory Usage

**Symptoms:**
- Application becomes slow
- Out of memory errors
- EC2 instance health degraded

**Diagnosis:**
```bash
eb ssh
free -h
top -o %MEM

# Check Python memory usage
ps aux | grep python | awk '{print $2, $4, $11}' | sort -k2 -rn
```

**Resolution:**
```bash
# 1. Restart application (temporary fix)
eb restart

# 2. Scale instance type (permanent fix)
eb scale --instance-type t3.medium

# 3. Review code for memory leaks
# Check for:
# - Large query result sets not paginated
# - Unclosed file handles
# - Circular references preventing garbage collection
```

### ML Model Training Failure

**Symptoms:**
- Cron job logs show failures
- Prediction endpoint returns old results

**Diagnosis:**
```bash
eb ssh
cat /var/log/ml-retrain.log

# Check cron job status
sudo systemctl status cron
sudo journalctl -u cron -n 50
```

**Resolution:**
```bash
# 1. Manually trigger retraining
curl -X POST http://localhost/ml/cron/retrain \
  -H "X-Cron-Secret: $CRON_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"config": "baseline"}'

# 2. Check for insufficient training data
python3 << EOF
from app import app, db
from models.work_order import WorkOrder

with app.app_context():
    count = WorkOrder.query.count()
    print(f"Total work orders: {count}")
    if count < 100:
        print("⚠️  Insufficient data for training (need >100)")
EOF

# 3. Check disk space
df -h

# 4. Review model training code for errors
cat /var/log/ml-retrain.log | grep -i "error\|exception"
```

---

## Backup & Recovery

### Backup Strategy

**What to backup:**
1. **Database** - Daily automated RDS snapshots (retained 7 days)
2. **S3 files** - Versioning enabled on S3 bucket
3. **Configuration** - Git repository (code + `.ebextensions/`)
4. **Environment variables** - Documented in runbook

**Backup schedule:**
- RDS automated backups: Daily at 3:00 AM UTC
- Manual snapshots: Before each deployment
- S3 versioning: Continuous
- Code: Git commits

### Full System Recovery

**Scenario: Complete AWS region failure**

**Steps:**
```bash
# 1. Create new RDS instance in different region
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier awning-prod-db-new \
  --db-snapshot-identifier <latest-snapshot> \
  --region us-west-2

# 2. Create new EB environment in new region
cd awning_wo/
eb init -p python-3.11 awning-wo --region us-west-2
eb create awning-prod-new \
  --database.engine postgres \
  --database.username postgres

# 3. Configure environment variables
eb setenv \
  SECRET_KEY="$SECRET_KEY" \
  DATABASE_URL="$NEW_DATABASE_URL" \
  AWS_S3_BUCKET="$S3_BUCKET" \
  # ... other env vars

# 4. Deploy application
eb deploy

# 5. Update DNS to point to new environment
# Update Route 53 or your DNS provider

# 6. Verify functionality
curl https://new-app-url.com/health

# 7. Test critical functions
# - Login
# - Create/view work orders
# - Analytics dashboard
```

### Point-in-Time Recovery

**Restore to specific time:**
```bash
# Restore RDS to 2 hours ago
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier awning-prod-db \
  --target-db-instance-identifier awning-prod-db-restored \
  --restore-time 2025-11-16T08:00:00Z

# Wait for instance to be available
aws rds wait db-instance-available \
  --db-instance-identifier awning-prod-db-restored

# Update application to use restored database
eb setenv DATABASE_URL="postgresql://user:pass@restored-host:5432/db"
eb restart
```

---

## Performance Tuning

### Query Optimization

**Identify slow queries:**
```bash
# Enable PostgreSQL slow query logging
# Add to RDS parameter group:
# log_min_duration_statement = 1000  # Log queries >1 second

# View slow query log
eb ssh
psql $DATABASE_URL

# Find slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;
```

**Add database indexes:**
```bash
# Create migration for new index
./alembic_db.sh test revision -m "add_index_to_customer_name"

# Edit migration file
# def upgrade():
#     op.create_index('idx_customer_name', 'customers', ['customer_name'])

# Apply migration
./alembic_db.sh prod upgrade head
```

### Application Performance

**Enable caching:**
```python
# Already configured in config.py
CACHE_TYPE = "SimpleCache"
CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

# Use cache in routes
from extensions import cache

@cache.cached(timeout=300, key_prefix='dashboard_stats')
def get_dashboard_stats():
    # Expensive query
    return stats
```

**Optimize large queries:**
```python
# Bad: Load all related objects
customers = Customer.query.all()
for customer in customers:
    print(customer.work_orders)  # N+1 query!

# Good: Use eager loading
from sqlalchemy.orm import joinedload

customers = Customer.query.options(
    joinedload(Customer.work_orders)
).all()
```

### Scaling Strategies

**Vertical scaling (larger instance):**
```bash
# Scale to t3.medium
eb scale --instance-type t3.medium

# Or manually via AWS Console
AWS Console > Elastic Beanstalk > Environment > Configuration > Capacity
```

**Horizontal scaling (multiple instances):**
```bash
# Enable auto-scaling
eb config

# Update configuration:
# aws:autoscaling:asg:
#   MinSize: 2
#   MaxSize: 4

# Save and apply
eb deploy
```

**Database read replicas:**
```bash
# Create read replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier awning-prod-db-replica \
  --source-db-instance-identifier awning-prod-db

# Use for analytics queries
ANALYTICS_DATABASE_URL = "postgresql://user:pass@replica-host:5432/db"
```

---

## Maintenance Tasks

### Weekly Tasks

- [ ] Review application logs for errors
- [ ] Check RDS performance metrics
- [ ] Verify automated backups completed
- [ ] Review CloudWatch alarms
- [ ] Check disk space usage

### Monthly Tasks

- [ ] Review and update dependencies (`pip list --outdated`)
- [ ] Run security scan (`pip-audit` or `safety check`)
- [ ] Review CloudWatch costs
- [ ] Analyze slow queries and optimize
- [ ] Review and cleanup old RDS snapshots
- [ ] Update documentation

### Quarterly Tasks

- [ ] Penetration testing or security audit
- [ ] Review and update disaster recovery plan
- [ ] Performance testing and benchmarking
- [ ] Review and optimize AWS costs
- [ ] Database vacuum and analyze (PostgreSQL)
- [ ] Review and update monitoring dashboards

### Annual Tasks

- [ ] Rotate all secrets (SECRET_KEY, database passwords, API keys)
- [ ] Review and update security policies
- [ ] Comprehensive disaster recovery drill
- [ ] Major version upgrades (Python, Flask, PostgreSQL)
- [ ] Review and update SLAs

---

## Emergency Contacts

**On-Call Rotation:**
- Primary: [Name] - [Phone] - [Email]
- Secondary: [Name] - [Phone] - [Email]

**Escalation Path:**
1. On-call engineer (respond within 15 minutes)
2. Team lead (escalate if unresolved in 1 hour)
3. CTO (escalate if critical and unresolved in 2 hours)

**External Support:**
- AWS Support: AWS Console > Support Center
- Database DBA: [Contact info]
- Security team: security@yourdomain.com

---

## Useful Commands Reference

### EB CLI
```bash
eb status                    # Check environment status
eb health --refresh          # Monitor health in real-time
eb logs --stream             # Stream logs
eb ssh                       # SSH into instance
eb deploy                    # Deploy application
eb restart                   # Restart application
eb setenv KEY=value          # Set environment variable
eb printenv                  # View environment variables
eb scale --instance-type t3.medium  # Change instance type
```

### Alembic
```bash
./alembic_db.sh prod current           # Current migration version
./alembic_db.sh prod upgrade head      # Apply all migrations
./alembic_db.sh prod downgrade -1      # Rollback one migration
./alembic_db.sh prod history           # View migration history
```

### AWS CLI
```bash
# RDS
aws rds describe-db-instances --db-instance-identifier awning-prod-db
aws rds create-db-snapshot --db-instance-identifier awning-prod-db --db-snapshot-identifier manual-snapshot-$(date +%Y%m%d)

# CloudWatch
aws cloudwatch get-metric-statistics --metric-name CPUUtilization --namespace AWS/RDS --dimensions Name=DBInstanceIdentifier,Value=awning-prod-db --start-time 2025-11-16T00:00:00Z --end-time 2025-11-16T23:59:59Z --period 3600 --statistics Average

# S3
aws s3 ls s3://awning-cleaning-data/
aws s3 cp s3://awning-cleaning-data/file.pdf ./
```

---

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-16 | 1.0 | Initial runbook creation | Claude |

