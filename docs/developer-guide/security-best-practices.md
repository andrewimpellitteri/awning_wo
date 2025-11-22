# Security and Best Practices

## Overview

This guide covers security best practices, common vulnerabilities to avoid, and recommended coding patterns for the Awning Management System.

## Table of Contents

- [Authentication & Authorization](#authentication--authorization)
- [Input Validation & Sanitization](#input-validation--sanitization)
- [SQL Injection Prevention](#sql-injection-prevention)
- [Cross-Site Scripting (XSS)](#cross-site-scripting-xss)
- [Cross-Site Request Forgery (CSRF)](#cross-site-request-forgery-csrf)
- [File Upload Security](#file-upload-security)
- [Session Management](#session-management)
- [Environment Variables & Secrets](#environment-variables--secrets)
- [Database Security](#database-security)
- [API Security](#api-security)
- [Logging & Monitoring](#logging--monitoring)
- [Dependencies & Updates](#dependencies--updates)

---

## Authentication & Authorization

### Current Implementation

The application uses **Flask-Login** for session-based authentication with role-based access control.

**Login Flow:**
```python
# routes/auth.py
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('dashboard.index'))
```

**Password Security:**
- Passwords are hashed using **Werkzeug's `generate_password_hash`**
- Uses PBKDF2 with SHA-256 by default
- Never store passwords in plaintext

### Role-Based Access Control

**Decorator Usage:**
```python
from decorators import role_required

@app.route('/admin/users')
@role_required('admin')
def admin_users():
    # Only accessible by admin users
    return render_template('admin/users.html')
```

**Available Roles:**
- `admin` - Full system access
- `user` - Standard user access

### Best Practices

✅ **DO:**
- Always use `@login_required` decorator on protected routes
- Use `role_required` for admin-only functionality
- Implement account lockout after N failed login attempts
- Use strong password requirements (min 8 chars, complexity)
- Implement session timeout for inactive users
- Hash passwords with modern algorithms (bcrypt, scrypt, or argon2)

❌ **DON'T:**
- Store passwords in plaintext or reversible encryption
- Use simple MD5 or SHA1 for password hashing (deprecated)
- Allow authentication without rate limiting
- Expose user enumeration via different error messages

### Recommended Improvements

```python
# Implement rate limiting on login endpoint
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@auth.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    # Login logic
    pass
```

---

## Input Validation & Sanitization

### Form Validation

**Always validate user input using WTForms:**

```python
from wtforms import StringField, validators

class CustomerForm(FlaskForm):
    customer_name = StringField('Name', [
        validators.DataRequired(),
        validators.Length(min=2, max=200)
    ])
    email = StringField('Email', [
        validators.Optional(),
        validators.Email()
    ])
    phone = StringField('Phone', [
        validators.Optional(),
        validators.Regexp(r'^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$')
    ])
```

### Server-Side Validation

**Never trust client-side validation alone:**

```python
@app.route('/customers/new', methods=['POST'])
@login_required
def create_customer():
    form = CustomerForm()

    # Server-side validation
    if not form.validate_on_submit():
        flash('Invalid form data', 'error')
        return render_template('customers/new.html', form=form)

    # Process validated data
    customer = Customer(
        customer_name=form.customer_name.data,
        email=form.email.data
    )
    db.session.add(customer)
    db.session.commit()
```

### Best Practices

✅ **DO:**
- Validate all user input on the server-side
- Use whitelist validation (allow known good) over blacklist
- Sanitize data before storing in database
- Validate data types, lengths, and formats
- Use parameterized queries (see SQL Injection section)

❌ **DON'T:**
- Trust data from client (including hidden fields, cookies)
- Rely only on JavaScript validation
- Accept arbitrary HTML from users without sanitization
- Allow unrestricted file uploads

---

## SQL Injection Prevention

### Safe Query Patterns

**Use SQLAlchemy ORM (Preferred):**

```python
# ✅ SAFE: Using ORM
customer = Customer.query.filter_by(customer_name=user_input).first()

# ✅ SAFE: Parameterized query
customer = Customer.query.filter(
    Customer.customer_name == user_input
).first()

# ❌ UNSAFE: String concatenation
query = f"SELECT * FROM customers WHERE name = '{user_input}'"
db.session.execute(query)  # NEVER DO THIS!
```

**Raw SQL with Parameters:**

```python
# ✅ SAFE: Using bound parameters
result = db.session.execute(
    text("SELECT * FROM customers WHERE customer_name = :name"),
    {"name": user_input}
)

# ❌ UNSAFE: String formatting
query = text(f"SELECT * FROM customers WHERE name = '{user_input}'")
result = db.session.execute(query)  # VULNERABLE!
```

### Best Practices

✅ **DO:**
- Use SQLAlchemy ORM methods for all database operations
- Use parameterized queries for raw SQL
- Validate and sanitize user input
- Use query.filter() instead of string concatenation
- Enable query logging in development to spot issues

❌ **DON'T:**
- Build SQL queries with string concatenation
- Use Python f-strings or .format() for SQL queries
- Trust user input in database queries
- Disable SQLAlchemy's built-in protections

### Example: Search Functionality

```python
# ✅ SAFE: Proper search implementation
def search_customers(search_term):
    """Search customers by name (SQL injection safe)."""
    return Customer.query.filter(
        Customer.customer_name.ilike(f'%{search_term}%')
    ).all()

# The ilike() method automatically escapes special characters
```

---

## Cross-Site Scripting (XSS)

### Jinja2 Auto-Escaping

Flask/Jinja2 **automatically escapes** variables by default:

```html
<!-- ✅ SAFE: Auto-escaped -->
<p>Customer: {{ customer.customer_name }}</p>

<!-- ❌ UNSAFE: Manual escaping disabled -->
<p>Customer: {{ customer.customer_name | safe }}</p>
```

### When to Use `| safe`

**Only use `| safe` for trusted, pre-sanitized HTML:**

```python
# Sanitize user-generated HTML before marking safe
from bleach import clean

allowed_tags = ['b', 'i', 'u', 'p', 'br']
notes_html = clean(user_input, tags=allowed_tags, strip=True)
```

```html
<!-- Now safe to render -->
<div class="notes">{{ notes_html | safe }}</div>
```

### Best Practices

✅ **DO:**
- Rely on Jinja2's automatic escaping
- Sanitize user input before storing
- Use Content Security Policy (CSP) headers
- Escape data in JavaScript contexts differently

❌ **DON'T:**
- Use `| safe` on user-generated content
- Concatenate user input into JavaScript
- Trust data from external APIs without validation
- Disable auto-escaping globally

### JavaScript Context Escaping

```html
<!-- ❌ UNSAFE: Direct variable insertion -->
<script>
var customerName = "{{ customer.customer_name }}";
</script>

<!-- ✅ SAFE: JSON encoding -->
<script>
var customerData = {{ customer_dict | tojson }};
</script>
```

---

## Cross-Site Request Forgery (CSRF)

### CSRF Protection

The application uses **Flask-WTF** for CSRF protection.

**Form Protection:**
```html
<!-- All forms must include CSRF token -->
<form method="POST" action="/customers/new">
    {{ form.hidden_tag() }}  <!-- Includes CSRF token -->
    {{ form.customer_name.label }}
    {{ form.customer_name() }}
    <button type="submit">Submit</button>
</form>
```

**AJAX Requests:**
```javascript
// Include CSRF token in AJAX requests
$.ajax({
    url: '/api/endpoint',
    method: 'POST',
    headers: {
        'X-CSRFToken': $('meta[name=csrf-token]').attr('content')
    },
    data: { key: 'value' }
});
```

**Meta Tag in Base Template:**
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

### Best Practices

✅ **DO:**
- Enable CSRF protection on all state-changing requests (POST, PUT, DELETE)
- Use `form.hidden_tag()` in all forms
- Include CSRF tokens in AJAX requests
- Use SameSite cookie attribute

❌ **DON'T:**
- Disable CSRF protection (`WTF_CSRF_ENABLED = False`) in production
- Exclude CSRF tokens from forms
- Use GET requests for state-changing operations
- Allow CSRF exemptions without careful consideration

### Exempt Endpoints (Rare Cases)

```python
from flask_wtf.csrf import csrf_exempt

# Only for webhooks or external APIs
@app.route('/webhook/payment', methods=['POST'])
@csrf_exempt
def payment_webhook():
    # Verify webhook signature instead
    signature = request.headers.get('X-Signature')
    if not verify_signature(signature, request.data):
        abort(403)
    # Process webhook
```

---

## File Upload Security

### Current Implementation

File uploads are handled by `utils/file_upload.py` with S3 storage.

**Allowed File Types:**
```python
ALLOWED_EXTENSIONS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif',
    'doc', 'docx', 'xls', 'xlsx'
}

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

### Security Best Practices

✅ **DO:**
- Validate file extensions (whitelist approach)
- Check file size limits (currently 10MB)
- Rename uploaded files (prevent path traversal)
- Scan files for malware (recommended for production)
- Store files outside web root (S3 recommended)
- Use Content-Type validation
- Generate unique filenames to prevent collisions

❌ **DON'T:**
- Trust client-provided filenames
- Allow arbitrary file types
- Store files with user-controlled names
- Serve files directly from upload directory
- Allow double extensions (e.g., `file.php.jpg`)

### File Upload Implementation

```python
import uuid
from werkzeug.utils import secure_filename

def upload_file(file):
    """Secure file upload implementation."""
    # Validate file presence
    if not file or file.filename == '':
        raise ValueError("No file provided")

    # Validate file extension
    if not allowed_file(file.filename):
        raise ValueError("File type not allowed")

    # Validate file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(f"File too large (max {MAX_UPLOAD_SIZE_MB}MB)")

    # Generate secure filename
    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"

    # Upload to S3 (isolated from web server)
    s3_key = f"uploads/{filename}"
    upload_to_s3(file, s3_key)

    return s3_key
```

### Content-Type Validation

```python
# Verify actual file type matches extension
import magic

def validate_file_type(file_path):
    """Validate file content matches extension."""
    mime = magic.Magic(mime=True)
    detected_type = mime.from_file(file_path)

    allowed_mimes = {
        'application/pdf',
        'image/jpeg',
        'image/png',
        # etc.
    }

    return detected_type in allowed_mimes
```

---

## Session Management

### Session Configuration

**Current settings in `config.py`:**
```python
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
SESSION_COOKIE_SECURE = FLASK_ENV == "production"  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
```

### Best Practices

✅ **DO:**
- Set `SESSION_COOKIE_SECURE = True` in production (HTTPS)
- Use `SESSION_COOKIE_HTTPONLY = True` (prevent XSS)
- Set `SESSION_COOKIE_SAMESITE = 'Lax'` or 'Strict'
- Implement session timeout
- Regenerate session ID after login
- Use secure session storage (server-side recommended)

❌ **DON'T:**
- Store sensitive data in client-side sessions
- Use predictable session IDs
- Allow indefinite session lifetime
- Disable HTTPOnly or Secure flags in production

### Improved Session Security

```python
from flask import session
from datetime import datetime

@auth.route('/login', methods=['POST'])
def login():
    user = authenticate(username, password)
    if user:
        # Regenerate session ID (prevent session fixation)
        session.clear()
        session.regenerate()

        login_user(user)
        session['login_time'] = datetime.utcnow()
        session.permanent = True  # Respect PERMANENT_SESSION_LIFETIME

        return redirect(url_for('dashboard.index'))
```

---

## Environment Variables & Secrets

### Current Issues ⚠️

**CRITICAL:** The following secrets are currently hardcoded in `.ebextensions/01_flask.config`:

- Database credentials
- AWS access keys
- S3 bucket names
- SECRET_KEY

### Recommended Approach

**Use AWS Elastic Beanstalk environment properties:**

```bash
# Set via EB CLI
eb setenv \
    SECRET_KEY="randomly-generated-secret" \
    DATABASE_URL="postgresql://user:pass@host:port/db" \
    AWS_ACCESS_KEY_ID="xxx" \
    AWS_SECRET_ACCESS_KEY="yyy" \
    AWS_S3_BUCKET="bucket-name"

# Verify
eb printenv
```

**Or use AWS Secrets Manager (best for production):**

```python
import boto3
import json

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In config.py
secrets = get_secret('awning-wo-prod-secrets')
SECRET_KEY = secrets['SECRET_KEY']
DATABASE_URL = secrets['DATABASE_URL']
```

### Best Practices

✅ **DO:**
- Store secrets in environment variables or secret managers
- Use different secrets for dev/staging/production
- Rotate secrets regularly
- Use strong, randomly generated secrets
- Add `.env` to `.gitignore`
- Use AWS Systems Manager Parameter Store or Secrets Manager

❌ **DON'T:**
- Commit secrets to version control
- Hardcode secrets in source code
- Share secrets via email or chat
- Use default or weak secrets
- Reuse secrets across environments

### Generate Strong Secrets

```python
import secrets

# Generate secure random SECRET_KEY
print(secrets.token_urlsafe(32))
# Output: 'xYz123...' (use this for SECRET_KEY)

# Generate CRON_SECRET for ML retraining
print(secrets.token_hex(16))
```

---

## Database Security

### Connection Security

**Use SSL/TLS for database connections:**

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'connect_args': {
        'sslmode': 'require',  # Force SSL
        'connect_timeout': 10
    },
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
```

### Query Security

See [SQL Injection Prevention](#sql-injection-prevention) section.

### Backup & Recovery

**Recommendations:**
- Enable automated RDS backups (retain 7-30 days)
- Test backup restoration regularly
- Use encrypted backups (AWS KMS)
- Implement point-in-time recovery
- Store backups in separate AWS region

### Best Practices

✅ **DO:**
- Use connection pooling (`pool_size`, `max_overflow`)
- Enable SSL/TLS for database connections
- Use read replicas for analytics queries
- Implement database connection retry logic
- Monitor slow queries and optimize
- Use parameterized queries exclusively

❌ **DON'T:**
- Store database credentials in code
- Allow public database access (use VPC)
- Disable SSL/TLS in production
- Use overly permissive database user privileges
- Log sensitive data (passwords, credit cards)

---

## API Security

### Rate Limiting

**Implement rate limiting for API endpoints:**

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/work_orders')
@limiter.limit("10 per minute")
@login_required
def api_work_orders():
    return jsonify(work_orders)
```

### API Authentication

**For future API development, consider:**
- API keys for external integrations
- OAuth2 for third-party access
- JWT tokens for stateless authentication
- Separate API versioning (`/api/v1/`)

### Best Practices

✅ **DO:**
- Require authentication for all API endpoints
- Implement rate limiting
- Validate and sanitize all input
- Return appropriate HTTP status codes
- Use HTTPS exclusively for API calls
- Log API access for auditing

❌ **DON'T:**
- Expose internal error details in API responses
- Allow unlimited API calls
- Return sensitive data without proper authorization
- Use GET requests for state-changing operations

---

## Logging & Monitoring

### Logging Best Practices

**What to log:**
- Authentication attempts (success and failure)
- Authorization failures
- Input validation failures
- Application errors and exceptions
- File uploads/downloads
- Database errors
- API calls

**What NOT to log:**
- Passwords (plaintext or hashed)
- Credit card numbers
- Session tokens
- API keys or secrets

### Implementation

```python
import logging
from flask import request

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Log authentication
@auth.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    if user and user.check_password(password):
        logging.info(f"Successful login: {username} from {request.remote_addr}")
        login_user(user)
    else:
        logging.warning(f"Failed login attempt: {username} from {request.remote_addr}")
```

### Monitoring

**Use AWS CloudWatch for:**
- Application logs
- Database performance metrics
- Error rates and alerts
- Custom business metrics

**Set up alerts for:**
- Failed login attempts (> 10 per minute)
- 500 errors (> 5 per hour)
- Database connection failures
- Disk space usage (> 80%)
- High CPU/memory usage

---

## Dependencies & Updates

### Dependency Management

**Keep dependencies up-to-date:**

```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade flask

# Update all dependencies
pip install --upgrade -r requirements.txt

# Check for security vulnerabilities
pip-audit
```

### Security Scanning

**Use automated tools:**
```bash
# Install safety
pip install safety

# Scan for known vulnerabilities
safety check

# Example output:
# -> flask 2.0.0 has known security vulnerabilities
#    Update to flask >= 2.0.3
```

### Best Practices

✅ **DO:**
- Regularly update dependencies (monthly)
- Review security advisories for your dependencies
- Pin dependency versions in `requirements.txt`
- Test updates in staging before production
- Use `pip-audit` or `safety` for vulnerability scanning
- Subscribe to security mailing lists for frameworks

❌ **DON'T:**
- Use outdated dependencies with known vulnerabilities
- Update all dependencies blindly without testing
- Ignore security advisories
- Use unmaintained packages

### Dependency Pinning

```
# requirements.txt
# Pin exact versions for reproducibility
Flask==2.3.3
SQLAlchemy==2.0.21
Flask-Login==0.6.2

# Allow patch updates (safer)
Flask>=2.3.3,<2.4.0
```

---

## Security Checklist

### Development

- [ ] All routes have authentication checks (`@login_required`)
- [ ] Admin routes use `@role_required('admin')`
- [ ] All forms include CSRF tokens
- [ ] User input is validated server-side
- [ ] Database queries use ORM or parameterized queries
- [ ] File uploads validate type and size
- [ ] Passwords are hashed (never stored plaintext)
- [ ] Secrets are not committed to git

### Pre-Deployment

- [ ] Environment variables configured (not hardcoded)
- [ ] `SECRET_KEY` is strong and random
- [ ] `SESSION_COOKIE_SECURE = True` (HTTPS)
- [ ] Database uses SSL/TLS connection
- [ ] S3 bucket has proper permissions
- [ ] CSRF protection enabled (`WTF_CSRF_ENABLED = True`)
- [ ] Dependencies scanned for vulnerabilities
- [ ] Logging configured (no sensitive data logged)
- [ ] Error pages don't expose internal details

### Production

- [ ] AWS credentials moved to environment variables
- [ ] Database credentials use Secrets Manager
- [ ] RDS backups enabled and tested
- [ ] CloudWatch alarms configured
- [ ] Security group rules follow least privilege
- [ ] HTTPS enforced (no HTTP allowed)
- [ ] Rate limiting enabled on auth endpoints
- [ ] Session timeout configured
- [ ] Regular security updates scheduled

---

## Common Vulnerabilities (OWASP Top 10)

### 1. Injection (SQL, OS Command)
**Status:** ✅ Protected (SQLAlchemy ORM)
**Recommendation:** Continue using ORM; avoid raw SQL

### 2. Broken Authentication
**Status:** ⚠️ Needs improvement
**Recommendation:** Add rate limiting, account lockout, MFA

### 3. Sensitive Data Exposure
**Status:** ⚠️ Needs improvement
**Recommendation:** Move secrets to AWS Secrets Manager; enable RDS encryption

### 4. XML External Entities (XXE)
**Status:** ✅ N/A (no XML parsing)

### 5. Broken Access Control
**Status:** ⚠️ Needs audit
**Recommendation:** Review all routes for proper authorization checks

### 6. Security Misconfiguration
**Status:** ⚠️ Critical
**Recommendation:** Remove hardcoded credentials from `.ebextensions/`

### 7. Cross-Site Scripting (XSS)
**Status:** ✅ Protected (Jinja2 auto-escaping)
**Recommendation:** Audit use of `| safe` filter

### 8. Insecure Deserialization
**Status:** ✅ N/A (no deserialization of untrusted data)

### 9. Using Components with Known Vulnerabilities
**Status:** ⚠️ Needs monitoring
**Recommendation:** Set up automated dependency scanning

### 10. Insufficient Logging & Monitoring
**Status:** ⚠️ Needs improvement
**Recommendation:** Enhance logging; set up CloudWatch alarms

---

## Security Contacts

**Report Security Issues:**
- Email: security@yourdomain.com
- GitHub: Private security advisory
- Do NOT open public issues for security vulnerabilities

**Security Review Schedule:**
- Quarterly dependency audits
- Annual penetration testing
- Monthly security patch reviews

---

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Considerations](https://flask.palletsprojects.com/en/2.3.x/security/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/faq/security.html)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [Python Security Guide](https://python.readthedocs.io/en/stable/library/security_warnings.html)
