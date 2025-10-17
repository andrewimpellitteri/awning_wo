# AWS Elastic Beanstalk Deployment

Complete guide to deploying the Awning Management System on AWS Elastic Beanstalk.

## Overview

The application is deployed on AWS Elastic Beanstalk with:
- **Platform:** Python 3.11
- **Instance Type:** t3.small
- **Database:** PostgreSQL on RDS
- **Storage:** S3 for file uploads
- **Server:** Gunicorn (WSGI)

---

## Prerequisites

### Required Tools

```bash
# AWS CLI
pip install awscli

# EB CLI
pip install awsebcli

# Configure AWS credentials
aws configure
```

### Required AWS Resources

Before deployment, ensure you have:
- AWS account with appropriate permissions
- RDS PostgreSQL database (or create during EB setup)
- S3 bucket for file storage
- IAM credentials with S3 and RDS access

---

## Initial Setup

### 1. Initialize Elastic Beanstalk

```bash
# Navigate to project directory
cd awning_wo

# Initialize EB application
eb init -p python-3.11 awning-wo --region us-east-1
```

You'll be prompted for:
- Application name (e.g., `awning-wo`)
- Platform (Python 3.11)
- SSH key pair (optional but recommended)

### 2. Create Environment

```bash
# Create production environment with database
eb create awning-prod \
  --instance-type t3.small \
  --database.engine postgres \
  --database.username postgres \
  --database.password <secure-password>
```

This creates:
- EC2 instance (t3.small)
- RDS PostgreSQL database
- Security groups
- Load balancer (if needed)
- Auto-scaling configuration

### 3. Set Environment Variables

```bash
eb setenv \
  SECRET_KEY="<generate-secure-key>" \
  FLASK_ENV="production" \
  AWS_ACCESS_KEY_ID="<your-access-key>" \
  AWS_SECRET_ACCESS_KEY="<your-secret-key>" \
  AWS_S3_BUCKET="awning-cleaning-data" \
  AWS_REGION="us-east-1" \
  CRON_SECRET="<secure-cron-secret>"
```

!!! warning "Security"
    Never commit credentials to git. Use environment variables only.

---

## Application Configuration

### Entry Point

EB looks for `application.py` as the WSGI entry point:

```python
# application.py
from app import app as application

if __name__ == "__main__":
    application.run()
```

### WSGI Configuration

The WSGI path is configured in `.ebextensions/01_flask.config`:

```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: app.py
```

---

## EB Extensions Configuration

### Flask Configuration (`.ebextensions/01_flask.config`)

```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    PYTHONPATH: /var/app/current
    FLASK_ENV: production
    DATABASE_URL: "postgresql://..."

  aws:autoscaling:launchconfiguration:
    InstanceType: t3.small

  aws:elasticbeanstalk:environment:process:default:
    Port: "80"
    HealthCheckPath: "/health"
```

**Key Settings:**
- `PYTHONPATH`: Points to application directory
- `HealthCheckPath`: Health check endpoint
- `InstanceType`: EC2 instance size

### Cron Jobs (`.ebextensions/cron.config`)

Sets up daily ML model retraining at 2:00 AM:

```yaml
container_commands:
  01_setup_cron_job:
    command: |
      # Add cron job - runs daily at 2:00 AM
      (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/ml-cron-retrain.sh") | crontab -
      service crond start || service cron start || true
```

**Cron Script:** `/usr/local/bin/ml-cron-retrain.sh`
- Calls `/ml/cron/retrain` endpoint
- Authenticates with `X-Cron-Secret` header
- Logs to `/var/log/ml-retrain.log`

---

## Database Setup

### Connection String

EB automatically provides RDS connection details as environment variables:
- `RDS_HOSTNAME`
- `RDS_USERNAME`
- `RDS_PASSWORD`
- `RDS_PORT`
- `RDS_DB_NAME`

The application uses `DATABASE_URL` for simplicity:

```python
# config.py
DATABASE_URL = os.environ.get('DATABASE_URL') or \
    f"postgresql://{os.environ.get('RDS_USERNAME')}:..."
```

### Run Migrations

After deployment, SSH into the instance and run migrations:

```bash
# SSH into instance
eb ssh

# Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# Run migrations
alembic upgrade head

# Verify
alembic current
```

---

## Deployment Workflow

### Standard Deployment

```bash
# 1. Make code changes
git add .
git commit -m "Your changes"

# 2. Test locally
python app.py

# 3. Deploy to EB
eb deploy

# 4. Monitor deployment
eb status
eb health
```

### Deployment with Schema Changes

```bash
# 1. Create and test migration locally
./alembic_db.sh test revision --autogenerate -m "add_field"
./alembic_db.sh test upgrade head

# 2. Commit migration file
git add alembic/versions/*.py
git commit -m "Add database migration"

# 3. Apply migration to production
./alembic_db.sh prod upgrade head

# 4. Deploy application code
eb deploy

# 5. Monitor
eb logs --stream
```

!!! danger "Important"
    Always apply database migrations BEFORE deploying code that depends on them.

---

## Monitoring & Logs

### View Logs

```bash
# Stream real-time logs
eb logs --stream

# Get recent logs
eb logs

# Download all logs
eb logs --all
```

### Log Locations on Instance

```bash
# Application logs
/var/log/eb-engine.log          # EB deployment logs
/var/log/web.stdout.log         # Application output
/var/log/httpd/error_log        # Apache/nginx errors

# Custom logs
/var/log/ml-retrain.log         # ML cron job logs
/var/log/ml-cron-health.log     # Cron health checks
```

### Check Application Status

```bash
# Environment status
eb status

# Health status
eb health

# Environment info
eb printenv
```

---

## Health Checks

EB monitors application health via the `/health` endpoint:

```python
# routes/dashboard.py
@dashboard_bp.route('/health')
def health():
    """Health check endpoint for AWS ELB"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200
```

**Configuration:**
- Path: `/health`
- Expected Status: `200 OK`
- Check Interval: 30 seconds
- Timeout: 5 seconds
- Healthy Threshold: 3 consecutive successes
- Unhealthy Threshold: 5 consecutive failures

---

## SSL/HTTPS Setup

### Using AWS Certificate Manager (ACM)

```bash
# 1. Request certificate in ACM
aws acm request-certificate \
  --domain-name yourdomain.com \
  --domain-name www.yourdomain.com \
  --validation-method DNS

# 2. Configure load balancer
eb config

# Add to configuration:
aws:elbv2:listener:443:
  Protocol: HTTPS
  SSLCertificateArns: arn:aws:acm:...
```

### Force HTTPS Redirect

Add to `.ebextensions/https-redirect.config`:

```yaml
files:
  "/etc/httpd/conf.d/ssl_rewrite.conf":
    mode: "000644"
    owner: root
    group: root
    content: |
      RewriteEngine On
      RewriteCond %{HTTP:X-Forwarded-Proto} !https
      RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
```

---

## Scaling Configuration

### Auto Scaling

Configure auto-scaling in `.ebextensions/autoscaling.config`:

```yaml
option_settings:
  aws:autoscaling:asg:
    MinSize: 1
    MaxSize: 4
  aws:autoscaling:trigger:
    MeasureName: CPUUtilization
    Statistic: Average
    Unit: Percent
    UpperThreshold: 75
    LowerThreshold: 25
```

### Manual Scaling

```bash
# Scale up
eb scale 2

# Scale down
eb scale 1
```

---

## Environment Management

### Multiple Environments

```bash
# Create staging environment
eb create awning-staging --instance-type t3.micro

# Create production environment
eb create awning-prod --instance-type t3.small

# Switch between environments
eb use awning-staging
eb use awning-prod

# Deploy to specific environment
eb deploy awning-prod
```

### Environment Variables

```bash
# Set variables
eb setenv VAR_NAME=value

# View all variables
eb printenv

# Set multiple variables
eb setenv VAR1=val1 VAR2=val2
```

---

## Database Management

### Access RDS Instance

```bash
# Get RDS endpoint
eb printenv | grep RDS

# Connect from local machine (requires security group access)
psql "postgresql://user:pass@host:5432/dbname"

# Connect from EB instance
eb ssh
psql -h $RDS_HOSTNAME -U $RDS_USERNAME -d $RDS_DB_NAME
```

### Backup Database

```bash
# Manual backup via pg_dump
eb ssh
pg_dump -h $RDS_HOSTNAME -U $RDS_USERNAME $RDS_DB_NAME > backup.sql

# Automated backups (RDS)
aws rds create-db-snapshot \
  --db-instance-identifier database-1 \
  --db-snapshot-identifier backup-$(date +%Y%m%d)
```

---

## S3 File Storage

### Bucket Configuration

Files are stored in S3 bucket: `awning-cleaning-data`

**Required IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::awning-cleaning-data/*",
        "arn:aws:s3:::awning-cleaning-data"
      ]
    }
  ]
}
```

### Access Files

```python
# Application uses boto3
import boto3

s3 = boto3.client('s3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Upload
s3.upload_fileobj(file, bucket, key)

# Download
s3.download_fileobj(bucket, key, file)

# Generate presigned URL
url = s3.generate_presigned_url('get_object',
    Params={'Bucket': bucket, 'Key': key},
    ExpiresIn=3600
)
```

---

## Troubleshooting

### Deployment Fails

```bash
# Check deployment logs
eb logs

# Check specific log file
eb ssh
tail -f /var/log/eb-engine.log
```

**Common Issues:**
- Missing dependencies in `requirements.txt`
- Invalid `.ebextensions` syntax
- Database connection issues
- Permission errors

### Application Won't Start

```bash
# Check WSGI configuration
eb config

# Verify entry point
eb ssh
ls -la /var/app/current/application.py

# Check Python path
echo $PYTHONPATH
```

### Database Connection Errors

```bash
# Verify environment variables
eb printenv | grep DATABASE

# Test connection from instance
eb ssh
psql -h $RDS_HOSTNAME -U $RDS_USERNAME -d $RDS_DB_NAME

# Check security groups
# RDS security group must allow inbound from EB instances
```

### Health Check Failures

```bash
# Test health endpoint
curl http://localhost/health

# Check logs
tail -f /var/log/web.stdout.log

# Verify endpoint returns 200
curl -I http://localhost/health
```

---

## Cost Optimization

### Development/Staging

- Use t3.micro instances
- Single instance (no load balancer)
- RDS t3.micro with minimal storage
- Delete when not in use

### Production

- t3.small instance (current configuration)
- Auto-scaling (1-4 instances)
- RDS backups enabled
- Reserved instances for cost savings

### Estimated Costs (Monthly)

| Resource | Configuration | Approximate Cost |
|----------|--------------|------------------|
| EC2 (t3.small) | 1 instance | $15-20 |
| RDS (db.t3.small) | PostgreSQL | $25-30 |
| S3 Storage | 10 GB | $0.25 |
| Data Transfer | < 1 TB | $10-15 |
| **Total** | | **$50-65/month** |

---

## Security Best Practices

### 1. Environment Variables

✅ **Do:** Store credentials in EB environment variables
❌ **Don't:** Commit credentials to `.ebextensions` files

### 2. Database Security

- Use strong RDS passwords
- Restrict RDS security group to EB instances only
- Enable RDS encryption at rest
- Regular backups

### 3. S3 Security

- Use IAM roles instead of access keys when possible
- Enable S3 bucket encryption
- Restrict bucket access
- Enable versioning for critical data

### 4. Application Security

- Use HTTPS only
- Set secure cookie flags
- Implement CSRF protection
- Keep dependencies updated

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to EB

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Install EB CLI
        run: pip install awsebcli

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy to EB
        run: |
          eb use awning-prod
          eb deploy
```

---

## Useful Commands Reference

```bash
# Deployment
eb init                 # Initialize EB application
eb create              # Create environment
eb deploy              # Deploy application
eb terminate           # Terminate environment

# Monitoring
eb status              # Environment status
eb health              # Health status
eb logs                # View logs
eb logs --stream       # Stream logs
eb ssh                 # SSH into instance

# Configuration
eb config              # Edit configuration
eb setenv KEY=VALUE    # Set environment variable
eb printenv            # View environment variables

# Scaling
eb scale 2             # Scale to 2 instances
eb scale 1             # Scale to 1 instance

# Environment management
eb list                # List environments
eb use <env>           # Switch environment
eb open                # Open in browser
```

---

## See Also

- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md) - Pre-deployment verification
- [Environment Variables](environment-variables.md) - Complete variable reference
- [Monitoring & Logging](monitoring.md) - Production monitoring
- [Rollback Procedures](rollback.md) - Emergency rollback guide
- [Database Migrations](../database/ALEMBIC_GUIDE.md) - Alembic workflow
