# File Upload System

## Overview

The Awning Management System includes a comprehensive file upload system with:
- **S3 Integration:** Cloud storage for production
- **Local Storage:** Fallback for development
- **Deferred Uploads:** Prevents orphaned S3 files when database commits fail
- **Thumbnail Generation:** Automatic image thumbnail creation
- **Environment Detection:** Automatic AWS vs local environment detection

## Architecture

### File Upload Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     File Upload Process                          │
└─────────────────────────────────────────────────────────────────┘

User uploads file
       │
       ▼
┌──────────────────────┐
│ 1. File Validation   │ ← Check allowed extensions
│    (allowed_file)    │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ 2. Read File Content │ ← Read into memory
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│ 3. Generate          │ ← Create thumbnail (if image)
│    Thumbnail         │
└──────────────────────┘
       │
       ▼
  ┌───────────┐
  │ Deferred? │
  └───────────┘
       │
       ├─────── Yes ────────────────────┐
       │                                 │
       │                                 ▼
       │                     ┌─────────────────────────┐
       │                     │ 4a. Store in Memory     │
       │                     │     _deferred_content   │
       │                     │     _deferred_s3_key    │
       │                     └─────────────────────────┘
       │                                 │
       │                                 ▼
       │                     ┌─────────────────────────┐
       │                     │ 5a. Create DB Record    │
       │                     │     (file_path = s3://) │
       │                     └─────────────────────────┘
       │                                 │
       │                                 ▼
       │                     ┌─────────────────────────┐
       │                     │ 6a. Commit Transaction  │
       │                     └─────────────────────────┘
       │                                 │
       │                        ┌────────┴────────┐
       │                        │                 │
       │                  Success              Failure
       │                        │                 │
       │                        ▼                 ▼
       │           ┌─────────────────────┐  ┌──────────────┐
       │           │ 7a. Upload to S3    │  │ 7b. Rollback │
       │           │     (deferred)      │  │   + Cleanup  │
       │           └─────────────────────┘  └──────────────┘
       │                        │                 │
       │                        │            No orphaned
       │                        │            S3 files! ✓
       │                        ▼
       │           ┌─────────────────────┐
       │           │ 8. Clean Memory     │
       │           └─────────────────────┘
       │
       └─────── No ─────────────────────┐
                                         │
                                         ▼
                             ┌──────────────────────┐
                             │ 4b. Upload to S3     │
                             │     (immediate)      │
                             └──────────────────────┘
                                         │
                                         ▼
                             ┌──────────────────────┐
                             │ 5b. Create DB Record │
                             └──────────────────────┘
                                         │
                                         ▼
                             ┌──────────────────────┐
                             │ 6b. Commit           │
                             └──────────────────────┘
                                         │
                                ┌────────┴────────┐
                                │                 │
                          Success              Failure
                                │                 │
                                ▼                 ▼
                           ┌─────────┐   ┌──────────────┐
                           │  Done   │   │ Rollback BUT │
                           └─────────┘   │ Orphaned S3  │
                                         │ files exist! │
                                         └──────────────┘
                                                │
                                         Risk: S3 cleanup
                                         needed manually
```

## Deferred Upload Pattern

### Why Deferred Uploads?

**Problem:** Immediate uploads can leave orphaned S3 files when database commits fail.

**Example Scenario (Without Deferred Uploads):**
```python
# Upload to S3 immediately
save_work_order_file("WO000001", file, defer_s3_upload=False)
# ↑ File is now in S3

# Create database record
db.session.add(work_order)
db.session.commit()  # ← This fails!

# Result: File exists in S3 but no database record
# Orphaned file that wastes storage and is hard to clean up
```

**Solution:** Defer S3 upload until after successful database commit.

### Deferred Upload Workflow

```python
from utils.file_upload import (
    save_work_order_file,
    commit_deferred_uploads,
    cleanup_deferred_files
)

# Step 1: Process files (stores in memory, not S3)
file_objects = []
for uploaded_file in request.files.getlist('documents'):
    file_obj = save_work_order_file(
        work_order_no="WO000001",
        file=uploaded_file,
        to_s3=True,
        generate_thumbnails=True,
        defer_s3_upload=True  # ← Key parameter
    )
    file_objects.append(file_obj)
    db.session.add(file_obj)

# Step 2: Add work order and commit
try:
    db.session.add(work_order)
    db.session.commit()  # ← Database transaction

    # Step 3: ONLY after successful commit, upload to S3
    success, uploaded, failed = commit_deferred_uploads(file_objects)

    if not success:
        flash(f"{len(failed)} files failed to upload", "warning")
        for file_obj, error in failed:
            flash(f"Error uploading {file_obj.filename}: {error}", "error")

except Exception as e:
    # Step 4: On failure, rollback and cleanup memory
    db.session.rollback()
    cleanup_deferred_files(file_objects)  # ← No orphaned S3 files!
    flash(f"Error: {e}", "error")
```

### Memory Management

Deferred uploads store file content in memory using temporary object attributes:

```python
# These attributes are attached to file model objects:
file_obj._deferred_file_content      # bytes: The file content
file_obj._deferred_s3_key             # str: The S3 key to upload to
file_obj._deferred_thumbnail_content  # PIL.Image or bytes: Thumbnail
file_obj._deferred_thumbnail_key      # str: Thumbnail S3 key
```

**Memory Cleanup:**
- `commit_deferred_uploads()` - Removes attributes after successful upload
- `cleanup_deferred_files()` - Removes attributes after rollback (prevents memory leaks)

---

## Configuration

### Environment Variables

```bash
# Required
AWS_S3_BUCKET=your-bucket-name

# Optional (defaults)
AWS_REGION=us-east-1

# Local Development Only (AWS provides these automatically in production via IAM)
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

### Allowed File Extensions

Configured in [utils/file_upload.py](../../utils/file_upload.py):

```python
ALLOWED_EXTENSIONS = {
    'pdf',      # Documents
    'docx',
    'txt',
    'csv',
    'xlsx',
    'jpg',      # Images
    'jpeg',
    'png'
}
```

**To add new extensions:**
```python
# In utils/file_upload.py
ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'txt', 'csv', 'xlsx',
    'jpg', 'jpeg', 'png',
    'gif', 'bmp', 'tiff',  # Add new extensions
}
```

### File Size Limits

Configured in [config.py](../../config.py):

```python
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
```

**To change limit:**
```python
# In config.py
class Config:
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
```

---

## Environment Detection

The system automatically detects whether it's running on AWS or locally:

```python
def is_running_on_aws():
    """Detect if running in AWS environment."""
    aws_indicators = [
        os.getenv("AWS_EXECUTION_ENV"),           # AWS services
        os.getenv("AWS_LAMBDA_FUNCTION_NAME"),    # Lambda
        os.getenv("AWS_REGION"),                  # Usually set in AWS
        os.path.exists("/var/app/current"),       # EB directory
        os.path.exists("/opt/elasticbeanstalk"),  # EB specific path
    ]
    return any(aws_indicators)
```

**Behavior:**
- **On AWS:** Uses IAM role for S3 access (no credentials needed)
- **Local:** Uses explicit AWS credentials from environment variables

---

## Core Functions

### File Upload Functions

#### `save_work_order_file(work_order_no, file, to_s3=True, generate_thumbnails=True, defer_s3_upload=False)`

Save a file for a work order.

**Parameters:**
- `work_order_no` (str): Work order number
- `file`: Flask file upload object
- `to_s3` (bool): Whether to save to S3 (default: True)
- `generate_thumbnails` (bool): Generate thumbnail for images (default: True)
- `defer_s3_upload` (bool): Defer upload until after DB commit (default: False, **should be True in production**)

**Returns:** `WorkOrderFile` instance (not yet committed to database)

**Example:**
```python
from utils.file_upload import save_work_order_file

file_obj = save_work_order_file(
    work_order_no="WO000001",
    file=request.files['document'],
    to_s3=True,
    generate_thumbnails=True,
    defer_s3_upload=True  # Recommended!
)

db.session.add(file_obj)
```

#### `save_repair_order_file(repair_order_no, file, to_s3=True, generate_thumbnails=True, defer_s3_upload=False)`

Save a file for a repair order (same interface as `save_work_order_file`).

---

### Deferred Upload Management

#### `commit_deferred_uploads(file_objects)`

Upload files to S3 that were deferred until after database commit.

**Parameters:**
- `file_objects` (list): List of file model objects with deferred upload data

**Returns:** Tuple of `(success, uploaded_files, failed_files)`
- `success` (bool): True if all uploads succeeded
- `uploaded_files` (list): List of successfully uploaded file objects
- `failed_files` (list): List of (file_obj, error_message) tuples

**Example:**
```python
success, uploaded, failed = commit_deferred_uploads(file_objects)

if success:
    flash(f"All {len(uploaded)} files uploaded successfully", "success")
else:
    flash(f"{len(uploaded)} files uploaded, {len(failed)} failed", "warning")
    for file_obj, error in failed:
        print(f"Failed: {file_obj.filename} - {error}")
```

#### `cleanup_deferred_files(file_objects)`

Clean up memory for files that were staged for deferred upload but the transaction was rolled back.

**Parameters:**
- `file_objects` (list): List of file model objects with deferred upload data

**Purpose:** Prevents memory leaks by removing temporary `_deferred_*` attributes.

**Example:**
```python
try:
    db.session.commit()
    commit_deferred_uploads(file_objects)
except Exception as e:
    db.session.rollback()
    cleanup_deferred_files(file_objects)  # Prevent memory leaks
```

---

### File Validation

#### `allowed_file(filename)`

Check if uploaded file has allowed extension.

**Example:**
```python
from utils.file_upload import allowed_file

if request.files['document']:
    file = request.files['document']
    if allowed_file(file.filename):
        # Process file
        pass
    else:
        flash("File type not allowed", "error")
```

---

### File Information

#### `get_file_size(file_path)`

Get human-readable file size.

**Parameters:**
- `file_path` (str): S3 path (`s3://...`) or local path

**Returns:** Human-readable size string (e.g., "1.5 MB") or None if file not found

**Example:**
```python
from utils.file_upload import get_file_size

size = get_file_size("s3://my-bucket/work_orders/WO000001/document.pdf")
print(size)  # "2.3 MB"
```

---

### Presigned URLs

#### `generate_presigned_url(file_path, expires_in=3600)`

Generate a temporary URL for secure S3 file access.

**Parameters:**
- `file_path` (str): Full S3 path (`s3://bucket/key`)
- `expires_in` (int): URL expiration in seconds (default: 3600 = 1 hour)

**Returns:** Presigned URL string

**Why Presigned URLs?**
- S3 files are private by default
- Presigned URLs provide temporary access without making files public
- URLs automatically expire for security

**Example:**
```python
from utils.file_upload import generate_presigned_url

# Generate 2-hour access URL
url = generate_presigned_url(
    "s3://my-bucket/work_orders/WO000001/document.pdf",
    expires_in=7200
)

# Use in template
return render_template('view_file.html', file_url=url)
```

#### `get_file_with_thumbnail_urls(wo_file, expires_in=3600)`

Get file URLs including thumbnail for a WorkOrderFile object.

**Returns:** Dict with keys:
- `file`: The WorkOrderFile object
- `file_url`: Presigned URL or file path
- `thumbnail_url`: Presigned thumbnail URL or None
- `has_thumbnail`: Boolean

**Example:**
```python
from utils.file_upload import get_file_with_thumbnail_urls

file_data = get_file_with_thumbnail_urls(work_order_file, expires_in=3600)

return render_template('files.html', **file_data)
```

**Template usage:**
```html
{% if has_thumbnail %}
    <img src="{{ thumbnail_url }}" alt="Thumbnail">
{% endif %}
<a href="{{ file_url }}" download>Download File</a>
```

---

### File Deletion

#### `delete_file_from_s3(file_path)`

Delete a file from S3 given its full s3:// path.

**Parameters:**
- `file_path` (str): Full S3 path (e.g., `s3://bucket-name/path/to/file.jpg`)

**Returns:** Boolean (True on success, False on failure)

**Example:**
```python
from utils.file_upload import delete_file_from_s3

# Delete file
success = delete_file_from_s3("s3://my-bucket/work_orders/WO000001/file.pdf")

if success:
    # Also delete database record
    db.session.delete(file_record)
    db.session.commit()

# Also works for thumbnails
delete_file_from_s3("s3://my-bucket/work_orders/WO000001/thumbnails/file_thumb.jpg")
```

---

## Thumbnail Generation

Thumbnails are automatically generated for image files (jpg, jpeg, png).

### Thumbnail Configuration

**Size:** 300x300 pixels (maintains aspect ratio)

**Format:** JPEG

**S3 Path Pattern:**
```
work_orders/{order_no}/thumbnails/{filename}_thumb.jpg
repair_orders/{order_no}/thumbnails/{filename}_thumb.jpg
```

### Thumbnail Functions

Located in [utils/thumbnail_generator.py](../../utils/thumbnail_generator.py):

#### `generate_thumbnail(file_content, filename)`
Generate thumbnail from image file content.

#### `save_thumbnail_to_s3(thumbnail_img, s3_client, bucket, s3_key)`
Save thumbnail to S3.

#### `save_thumbnail_locally(thumbnail_img, file_path)`
Save thumbnail to local filesystem.

---

## S3 Folder Structure

```
s3://your-bucket/
├── work_orders/
│   ├── WO000001/
│   │   ├── invoice.pdf
│   │   ├── photo1.jpg
│   │   └── thumbnails/
│   │       └── photo1_thumb.jpg
│   ├── WO000002/
│   │   └── document.docx
│   └── ...
├── repair_orders/
│   ├── RO000001/
│   │   ├── before.jpg
│   │   ├── after.jpg
│   │   └── thumbnails/
│   │       ├── before_thumb.jpg
│   │       └── after_thumb.jpg
│   └── ...
└── ml_models/
    ├── latest_model.pkl
    └── latest_model_metadata.json
```

---

## Complete Upload Example

### Route Handler with Deferred Upload

```python
from flask import Blueprint, request, flash, redirect, url_for
from utils.file_upload import (
    save_work_order_file,
    commit_deferred_uploads,
    cleanup_deferred_files,
    allowed_file
)
from models.work_order import WorkOrder
from extensions import db

work_orders_bp = Blueprint('work_orders', __name__)

@work_orders_bp.route('/work_orders/<work_order_no>/upload', methods=['POST'])
def upload_files(work_order_no):
    """Upload files to a work order."""

    # Verify work order exists
    work_order = WorkOrder.query.get_or_404(work_order_no)

    # Validate files
    files = request.files.getlist('documents')
    if not files or files[0].filename == '':
        flash("No files selected", "error")
        return redirect(url_for('work_orders.view', work_order_no=work_order_no))

    # Check file types
    invalid_files = [f.filename for f in files if not allowed_file(f.filename)]
    if invalid_files:
        flash(f"Invalid file types: {', '.join(invalid_files)}", "error")
        return redirect(url_for('work_orders.view', work_order_no=work_order_no))

    # Step 1: Process files (deferred upload)
    file_objects = []
    for uploaded_file in files:
        try:
            file_obj = save_work_order_file(
                work_order_no=work_order_no,
                file=uploaded_file,
                to_s3=True,
                generate_thumbnails=True,
                defer_s3_upload=True  # Key: Defer until after commit
            )
            file_objects.append(file_obj)
            db.session.add(file_obj)
        except Exception as e:
            flash(f"Error processing {uploaded_file.filename}: {e}", "error")

    # Step 2: Commit database changes
    try:
        db.session.commit()

        # Step 3: Upload to S3 (only after successful commit)
        success, uploaded, failed = commit_deferred_uploads(file_objects)

        # Step 4: Report results
        if success:
            flash(f"{len(uploaded)} files uploaded successfully", "success")
        else:
            flash(f"{len(uploaded)} files uploaded, {len(failed)} failed", "warning")
            for file_obj, error in failed:
                flash(f"Failed to upload {file_obj.filename}: {error}", "error")

        return redirect(url_for('work_orders.view', work_order_no=work_order_no))

    except Exception as e:
        # Step 5: On error, rollback and cleanup
        db.session.rollback()
        cleanup_deferred_files(file_objects)

        flash(f"Error uploading files: {e}", "error")
        return redirect(url_for('work_orders.view', work_order_no=work_order_no))
```

### HTML Form

```html
<form method="POST" action="{{ url_for('work_orders.upload_files', work_order_no=work_order.WorkOrderNo) }}"
      enctype="multipart/form-data">

    <div class="form-group">
        <label for="documents">Upload Files</label>
        <input type="file"
               class="form-control-file"
               id="documents"
               name="documents"
               multiple
               accept=".pdf,.docx,.txt,.csv,.xlsx,.jpg,.jpeg,.png">
        <small class="form-text text-muted">
            Allowed types: PDF, DOCX, TXT, CSV, XLSX, JPG, PNG (max 16MB per file)
        </small>
    </div>

    <button type="submit" class="btn btn-primary">Upload</button>
</form>
```

---

## Display Files with Thumbnails

```python
@work_orders_bp.route('/work_orders/<work_order_no>/files')
def view_files(work_order_no):
    """Display files for a work order."""
    work_order = WorkOrder.query.get_or_404(work_order_no)

    # Get files with presigned URLs
    files_data = []
    for file in work_order.files:
        file_data = get_file_with_thumbnail_urls(file, expires_in=3600)
        files_data.append(file_data)

    return render_template('files.html', work_order=work_order, files=files_data)
```

```html
<!-- files.html -->
<div class="row">
    {% for file_data in files %}
    <div class="col-md-3">
        <div class="card">
            {% if file_data.has_thumbnail %}
                <img src="{{ file_data.thumbnail_url }}" class="card-img-top" alt="{{ file_data.file.filename }}">
            {% else %}
                <div class="card-img-top bg-secondary text-white text-center" style="height: 200px; line-height: 200px;">
                    <i class="fas fa-file fa-3x"></i>
                </div>
            {% endif %}
            <div class="card-body">
                <h5 class="card-title">{{ file_data.file.filename }}</h5>
                <p class="card-text">
                    <small class="text-muted">{{ file_data.file.uploaded_at.strftime('%Y-%m-%d') }}</small>
                </p>
                <a href="{{ file_data.file_url }}" class="btn btn-primary btn-sm" download>
                    <i class="fas fa-download"></i> Download
                </a>
                <form method="POST" action="{{ url_for('work_orders.delete_file', file_id=file_data.file.id) }}"
                      style="display:inline;">
                    <button type="submit" class="btn btn-danger btn-sm"
                            onclick="return confirm('Delete this file?')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </form>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
```

---

## Local Development

### Using Local Storage

For development without AWS credentials:

```python
file_obj = save_work_order_file(
    work_order_no="WO000001",
    file=uploaded_file,
    to_s3=False,  # Use local storage
    generate_thumbnails=True,
    defer_s3_upload=False  # Not applicable for local
)
```

**Local Storage Path:**
```
uploads/work_orders/{order_no}/{filename}
uploads/work_orders/{order_no}/thumbnails/{filename}_thumb.jpg
```

### AWS Credentials for Local Development

Create `.env` file in project root:

```bash
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

**Load in Flask:**
```python
# config.py
from dotenv import load_dotenv
load_dotenv()
```

---

## Best Practices

### 1. Always Use Deferred Uploads in Production

```python
# ✅ Good - Prevents orphaned S3 files
file_obj = save_work_order_file(
    work_order_no=wo_no,
    file=uploaded_file,
    defer_s3_upload=True
)
```

```python
# ❌ Bad - Can leave orphaned S3 files
file_obj = save_work_order_file(
    work_order_no=wo_no,
    file=uploaded_file,
    defer_s3_upload=False
)
```

### 2. Always Clean Up on Rollback

```python
try:
    db.session.commit()
    commit_deferred_uploads(file_objects)
except Exception:
    db.session.rollback()
    cleanup_deferred_files(file_objects)  # ✅ Prevents memory leaks
```

### 3. Validate File Types Before Processing

```python
# ✅ Good - Validate early
if not allowed_file(file.filename):
    flash("Invalid file type", "error")
    return redirect(...)

# Process file
file_obj = save_work_order_file(...)
```

### 4. Handle Partial Upload Failures

```python
success, uploaded, failed = commit_deferred_uploads(file_objects)

if not success:
    # ✅ Good - Inform user about specific failures
    for file_obj, error in failed:
        flash(f"Failed: {file_obj.filename} - {error}", "error")
```

### 5. Use Presigned URLs with Reasonable Expiration

```python
# ✅ Good - 1 hour expiration for user downloads
url = generate_presigned_url(file_path, expires_in=3600)

# ❌ Bad - 24 hour expiration (security risk)
url = generate_presigned_url(file_path, expires_in=86400)
```

---

## Troubleshooting

### Issue: "AWS credentials not found"

**Cause:** Missing AWS credentials in local development.

**Solution:**
```bash
# Set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_S3_BUCKET=your-bucket
```

### Issue: "NoSuchBucket" error

**Cause:** S3 bucket doesn't exist or name is incorrect.

**Solution:**
1. Verify bucket name in environment variables
2. Create bucket in AWS S3 console
3. Ensure bucket is in correct region

### Issue: Orphaned S3 files after errors

**Cause:** Not using deferred uploads or missing cleanup.

**Solution:**
```python
# Use deferred uploads
defer_s3_upload=True

# Always cleanup on rollback
except Exception:
    cleanup_deferred_files(file_objects)
```

### Issue: Memory leaks during file uploads

**Cause:** Not cleaning up deferred file content.

**Solution:**
```python
# Always call cleanup_deferred_files on rollback
cleanup_deferred_files(file_objects)
```

### Issue: Thumbnails not generating

**Cause:** Non-image file or PIL library issue.

**Solution:**
1. Verify file is an image (jpg, jpeg, png)
2. Check PIL/Pillow is installed: `pip install Pillow`
3. Check error logs for thumbnail generation failures

---

## See Also

- [Utility Functions Reference](./utility-functions.md) - File upload utility functions
- [Error Handling](./error-handling.md) - Handling upload errors
- [Testing](./testing.md) - Testing file uploads
- [CLAUDE.md](../../CLAUDE.md) - Main project documentation