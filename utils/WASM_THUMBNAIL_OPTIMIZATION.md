# Optimizing Thumbnail Generation with WebAssembly (WASM)

This guide details how to refactor the file upload process to generate thumbnails on the client-side using WebAssembly, significantly reducing server load and improving user experience.

**The current workflow executes all thumbnail generation (a CPU-intensive task) on the server. The new workflow offloads this to the user's browser.**

---

## Step 1: Update Backend to Receive Pre-Processed Thumbnails

First, we'll simplify the backend. It will no longer generate thumbnails; it will only receive and save the original file and the thumbnail file created by the client.

### 1.1. Simplify `utils/file_upload.py`

The `save_work_order_file` function will be simplified to just save two files. The complex `generate_thumbnail` logic is no longer needed here.

Replace the contents of `utils/file_upload.py` with the following. We are keeping the S3 logic but removing all thumbnail generation calls.

```python
import os
from werkzeug.utils import secure_filename
from models.work_order_file import WorkOrderFile
from extensions import db
import boto3
from io import BytesIO
from datetime import datetime

# --- S3 Configuration ---
UPLOAD_FOLDER = "uploads/work_orders"  # local fallback
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx", "txt", "csv"}

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

if not AWS_S3_BUCKET:
    raise ValueError("AWS_S3_BUCKET environment variable is required")

def is_running_on_aws():
    return any([
        os.getenv("AWS_EXECUTION_ENV"),
        os.getenv("AWS_LAMBDA_FUNCTION_NAME"),
        os.getenv("AWS_REGION"),
    ])

is_aws_environment = is_running_on_aws()

if is_aws_environment:
    print("Detected AWS environment - using IAM role for S3 access")
    s3_client = boto3.client("s3", region_name=AWS_REGION)
else:
    print("Detected local environment - using explicit AWS credentials")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError("Local dev requires AWS credentials")
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

def save_uploaded_files(work_order_no, original_file, thumbnail_file, to_s3=True):
    """
    Saves an original file and its pre-generated thumbnail.
    This function no longer generates thumbnails.
    """
    original_filename = secure_filename(original_file.filename)
    thumbnail_filename = secure_filename(thumbnail_file.filename)

    if to_s3:
        # Save Original File
        original_s3_key = f"work_orders/{work_order_no}/{original_filename}"
        s3_client.upload_fileobj(original_file, AWS_S3_BUCKET, original_s3_key)
        file_path = f"s3://{AWS_S3_BUCKET}/{original_s3_key}"

        # Save Thumbnail File
        thumbnail_s3_key = f"work_orders/{work_order_no}/{thumbnail_filename}"
        s3_client.upload_fileobj(thumbnail_file, AWS_S3_BUCKET, thumbnail_s3_key)
        thumbnail_path = f"s3://{AWS_S3_BUCKET}/{thumbnail_s3_key}"
    else:
        # Save locally (fallback)
        wo_folder = os.path.join(UPLOAD_FOLDER, str(work_order_no))
        os.makedirs(wo_folder, exist_ok=True)
        
        file_path = os.path.join(wo_folder, original_filename)
        original_file.save(file_path)
        
        thumbnail_path = os.path.join(wo_folder, thumbnail_filename)
        thumbnail_file.save(thumbnail_path)

    # Create WorkOrderFile object to be committed later
    wo_file = WorkOrderFile(
        WorkOrderNo=work_order_no,
        filename=original_filename,
        file_path=file_path,
        thumbnail_path=thumbnail_path,
    )
    return wo_file

# Other utility functions like generate_presigned_url can remain unchanged.
```

### 1.2. Update `routes/work_orders.py`

Modify the `create_work_order` route (and any other upload routes) to handle the two incoming files (`original` and `thumbnail`).

```python
# Inside routes/work_orders.py

# IMPORTANT: Change the import from `save_work_order_file` to `save_uploaded_files`
from utils.file_upload import save_uploaded_files

# ... inside the create_work_order function, find the file handling block ...

# --- This block replaces the old file handling logic ---
if 'original_files[]' in request.files:
    original_files = request.files.getlist('original_files[]')
    thumbnail_files = request.files.getlist('thumbnail_files[]')

    if len(original_files) != len(thumbnail_files):
        raise Exception("Mismatch between original files and thumbnails.")

    for i, original_file in enumerate(original_files):
        if original_file and original_file.filename:
            thumbnail_file = thumbnail_files[i]
            
            wo_file = save_uploaded_files(
                work_order_no=next_wo_no,
                original_file=original_file,
                thumbnail_file=thumbnail_file,
                to_s3=True 
            )
            
            if not wo_file:
                raise Exception(f"Failed to save file: {original_file.filename}")

            db.session.add(wo_file)
            print(f"Saved {wo_file.filename} and its thumbnail {thumbnail_file.filename}")
# --- End of replacement block ---
```

## Step 2: Implement Client-Side Thumbnail Generation

This involves adding JavaScript to your frontend templates. We will use `pdf.js` for PDFs and `libsquoosh` for images, as they are robust, well-supported libraries that use WebAssembly.

### 2.1. Update Your HTML Template

In your `work_orders/create.html` and `work_orders/edit.html` (or any template with a file upload), add a file input and a preview area.

```html
<!-- Add a unique ID to your file input -->
<input type="file" id="file-uploader" name="files[]" multiple>

<!-- Add a container to display thumbnail previews -->
<div id="thumbnail-preview-area" style="display:flex; flex-wrap:wrap; gap:10px; margin-top:15px;"></div>

<!-- Include pdf.js and libsquosh from a CDN -->
<!-- Place these in your base.html or at the bottom of the page -->
<script src="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.min.js"></script>
<script>
    // Required for pdf.js
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js`;
</script>
<script type="module" src="https://unpkg.com/@jsquash/jpeg@1.3.0/meta.js"></script>
<script type="module" src="https://unpkg.com/@jsquash/resize@1.2.1/meta.js"></script>
```

### 2.2. Add the Client-Side Processing JavaScript

Add this script to your page. It will listen for file selections, process them, and prepare them for upload.

```javascript
document.addEventListener('DOMContentLoaded', () => {
    const fileUploader = document.getElementById('file-uploader');
    const previewArea = document.getElementById('thumbnail-preview-area');
    
    // This will store our processed files, ready for upload
    const processedFiles = {
        originals: [],
        thumbnails: []
    };

    fileUploader.addEventListener('change', async (event) => {
        const files = event.target.files;
        if (!files.length) return;

        // Clear previous previews and stored files
        previewArea.innerHTML = '';
        processedFiles.originals = [];
        processedFiles.thumbnails = [];

        for (const file of files) {
            let thumbnailBlob;
            const originalFileName = file.name;

            // Show a placeholder
            const placeholder = document.createElement('div');
            placeholder.textContent = `Processing ${originalFileName}...`;
            previewArea.appendChild(placeholder);

            try {
                if (file.type.startsWith('image/')) {
                    thumbnailBlob = await processImage(file);
                } else if (file.type === 'application/pdf') {
                    thumbnailBlob = await processPdf(file);
                } else {
                    // For other files, you might create a default icon or skip a thumbnail
                    console.log(`Skipping thumbnail for ${originalFileName}`);
                    placeholder.textContent = `No preview for ${originalFileName}`;
                    continue; // Or create a default thumbnail
                }

                const thumbnailFile = new File([thumbnailBlob], `thumb_${originalFileName.split('.')[0]}.jpeg`, { type: 'image/jpeg' });

                // Store the files
                processedFiles.originals.push(file);
                processedFiles.thumbnails.push(thumbnailFile);

                // Create and display the thumbnail preview
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.style.width = '150px';
                    img.style.height = '150px';
                    img.style.objectFit = 'cover';
                    img.title = `Thumbnail for ${originalFileName}`;
                    placeholder.replaceWith(img); // Replace placeholder with the actual thumbnail
                };
                reader.readAsDataURL(thumbnailBlob);

            } catch (error) {
                console.error(`Failed to process ${originalFileName}:`, error);
                placeholder.textContent = `Error processing ${originalFileName}`;
            }
        }
    });

    // --- Image Processing Function (uses libsquosh) ---
    async function processImage(file) {
        const imageBuffer = await file.arrayBuffer();
        
        // Resize the image
        const resizeOptions = {
            width: 200,
            height: 200,
            method: 'lanczos3',
        };
        const resizedImage = await resize(imageBuffer, resizeOptions);

        // Encode the resized image to JPEG
        const jpegBlob = await encode(resizedImage, { quality: 85 });
        return jpegBlob;
    }

    // --- PDF Processing Function (uses pdf.js) ---
    async function processPdf(file) {
        const fileBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: fileBuffer }).promise;
        const page = await pdf.getPage(1); // Get the first page

        const viewport = page.getViewport({ scale: 1 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        
        // Set canvas dimensions to match PDF page aspect ratio
        const scale = 200 / viewport.height;
        const scaledViewport = page.getViewport({ scale });
        canvas.height = scaledViewport.height;
        canvas.width = scaledViewport.width;

        // Render PDF page to canvas
        await page.render({ canvasContext: context, viewport: scaledViewport }).promise;

        // Convert canvas to JPEG blob
        return new Promise(resolve => {
            canvas.toBlob(resolve, 'image/jpeg', 0.85);
        });
    }

    // --- Modify Form Submission ---
    // You need to intercept the form submission to append the processed files.
    const form = fileUploader.closest('form');
    form.addEventListener('submit', function(event) {
        event.preventDefault(); // Stop the default submission

        const formData = new FormData(form);

        // Remove the original placeholder file list
        formData.delete('files[]');

        // Append the processed files
        processedFiles.originals.forEach(file => {
            formData.append('original_files[]', file);
        });
        processedFiles.thumbnails.forEach(file => {
            formData.append('thumbnail_files[]', file);
        });

        // Submit the form with the new FormData
        fetch(form.action, {
            method: 'POST',
            body: formData,
            // headers: { 'X-CSRF-TOKEN': 'your_csrf_token' } // If you use CSRF tokens
        })
        .then(response => {
            if (response.ok) {
                // Redirect on success, e.g., to the work order detail page
                window.location.href = response.url; 
            } else {
                // Handle errors
                console.error('Upload failed');
                alert('Upload failed!');
            }
        })
        .catch(error => {
            console.error('Error submitting form:', error);
            alert('An error occurred.');
        });
    });
});
```

## Step 3: Clean Up Old Code

Once the new implementation is verified and working, you can safely remove the old server-side generation code.

1.  **Delete `utils/thumbnail_generator.py`:** This file is no longer needed.
2.  **Clean up `utils/file_upload.py`:** Ensure the old `save_work_order_file` and any related helper functions for generation are removed, as shown in Step 1.1.
3.  **Remove old libraries:** If `Pillow`, `PyMuPDF`, `python-docx`, etc., were only used for thumbnailing, you can remove them from your `requirements.txt` to slim down your application dependencies.

---

This refactoring moves the performance-critical task of thumbnail generation to the client, resulting in a faster, more scalable, and more responsive application.
