"""
Document OCR Service using AWS Textract.

Extracts text from work order document images (handwritten and typed)
and creates embeddings for RAG search.
"""
import os
import io
from typing import Optional, Dict, List, Tuple
import boto3
from botocore.exceptions import ClientError

from extensions import db
from models.embeddings import DocumentEmbedding
from models.work_order_file import WorkOrderFile


# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")

# Supported file extensions for OCR
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}
PDF_EXTENSIONS = {'.pdf'}
DOCUMENT_EXTENSIONS = {'.docx', '.doc'}  # Requires different handling
ALL_OCR_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS


def get_s3_client():
    """Get boto3 S3 client."""
    return boto3.client('s3', region_name=AWS_REGION)


def get_textract_client():
    """Get boto3 Textract client."""
    return boto3.client('textract', region_name=AWS_REGION)


def parse_s3_path(s3_path: str) -> Tuple[str, str]:
    """
    Parse an S3 path into bucket and key.

    Args:
        s3_path: S3 path like 's3://bucket/key' or just 'key'

    Returns:
        Tuple of (bucket, key)
    """
    if s3_path.startswith('s3://'):
        # Remove s3:// prefix and split
        path = s3_path[5:]
        parts = path.split('/', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0], ''
    # Assume it's just a key, use default bucket
    return AWS_S3_BUCKET, s3_path


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension including the dot."""
    return os.path.splitext(filename)[1].lower()


def is_ocr_supported(filename: str) -> bool:
    """Check if the file type is supported for OCR."""
    ext = get_file_extension(filename)
    return ext in ALL_OCR_EXTENSIONS


def extract_text_from_s3_image(s3_path: str) -> Dict:
    """
    Extract text from an image stored in S3 using AWS Textract.

    Args:
        s3_path: Full S3 path (s3://bucket/key)

    Returns:
        Dictionary with 'text', 'confidence', and 'blocks' (raw Textract response)
    """
    bucket, key = parse_s3_path(s3_path)

    if not bucket:
        return {"error": "No S3 bucket configured", "text": "", "confidence": 0}

    textract = get_textract_client()

    try:
        response = textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )

        # Extract text and confidence from blocks
        lines = []
        confidences = []

        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                lines.append(block.get('Text', ''))
                confidences.append(block.get('Confidence', 0))

        text = '\n'.join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "text": text,
            "confidence": avg_confidence,
            "line_count": len(lines),
            "blocks": response.get('Blocks', [])
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return {
            "error": f"Textract error ({error_code}): {error_msg}",
            "text": "",
            "confidence": 0
        }
    except Exception as e:
        return {
            "error": f"OCR failed: {str(e)}",
            "text": "",
            "confidence": 0
        }


def extract_text_from_s3_pdf(s3_path: str) -> Dict:
    """
    Extract text from a PDF stored in S3 using AWS Textract.
    For multi-page PDFs, uses async API.

    Args:
        s3_path: Full S3 path (s3://bucket/key)

    Returns:
        Dictionary with 'text', 'confidence', and metadata
    """
    bucket, key = parse_s3_path(s3_path)

    if not bucket:
        return {"error": "No S3 bucket configured", "text": "", "confidence": 0}

    textract = get_textract_client()

    try:
        # For PDFs, we need to use async detection
        # Start the job
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )

        job_id = response['JobId']

        # Wait for completion (with timeout)
        import time
        max_attempts = 60  # 5 minutes max
        attempt = 0

        while attempt < max_attempts:
            result = textract.get_document_text_detection(JobId=job_id)
            status = result['JobStatus']

            if status == 'SUCCEEDED':
                break
            elif status == 'FAILED':
                return {
                    "error": f"Textract job failed: {result.get('StatusMessage', 'Unknown error')}",
                    "text": "",
                    "confidence": 0
                }

            time.sleep(5)  # Wait 5 seconds between checks
            attempt += 1

        if attempt >= max_attempts:
            return {
                "error": "Textract job timed out",
                "text": "",
                "confidence": 0
            }

        # Collect all results (handle pagination)
        lines = []
        confidences = []
        next_token = None

        while True:
            if next_token:
                result = textract.get_document_text_detection(
                    JobId=job_id,
                    NextToken=next_token
                )

            for block in result.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    lines.append(block.get('Text', ''))
                    confidences.append(block.get('Confidence', 0))

            next_token = result.get('NextToken')
            if not next_token:
                break

        text = '\n'.join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "text": text,
            "confidence": avg_confidence,
            "line_count": len(lines),
            "page_count": result.get('DocumentMetadata', {}).get('Pages', 1)
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return {
            "error": f"Textract error ({error_code}): {error_msg}",
            "text": "",
            "confidence": 0
        }
    except Exception as e:
        return {
            "error": f"OCR failed: {str(e)}",
            "text": "",
            "confidence": 0
        }


def extract_text_from_file(file_path: str, filename: str) -> Dict:
    """
    Extract text from a file based on its type.

    Args:
        file_path: S3 path to the file
        filename: Original filename (for extension detection)

    Returns:
        Dictionary with 'text', 'confidence', 'method', and optional 'error'
    """
    ext = get_file_extension(filename)

    if ext in IMAGE_EXTENSIONS:
        result = extract_text_from_s3_image(file_path)
        result['method'] = 'textract_image'
        return result

    elif ext in PDF_EXTENSIONS:
        result = extract_text_from_s3_pdf(file_path)
        result['method'] = 'textract_pdf'
        return result

    elif ext in DOCUMENT_EXTENSIONS:
        # Word documents need different handling
        # For now, return unsupported
        return {
            "text": "",
            "confidence": 0,
            "method": "unsupported",
            "error": f"Word documents ({ext}) not yet supported for OCR"
        }

    else:
        return {
            "text": "",
            "confidence": 0,
            "method": "unsupported",
            "error": f"File type {ext} not supported for OCR"
        }


def sync_document_embedding(file_id: int) -> bool:
    """
    Extract text from a work order file and create/update its embedding.

    Args:
        file_id: ID of the WorkOrderFile

    Returns:
        True if successful, False otherwise
    """
    from services.rag_service import get_embedding

    # Get the file record
    wo_file = WorkOrderFile.query.get(file_id)
    if not wo_file:
        print(f"File not found: {file_id}")
        return False

    # Check if file type is supported
    if not is_ocr_supported(wo_file.filename):
        print(f"File type not supported for OCR: {wo_file.filename}")
        return False

    # Check if file is on S3
    if not wo_file.file_path.startswith('s3://'):
        print(f"File not on S3: {wo_file.file_path}")
        return False

    # Extract text using OCR
    print(f"Extracting text from: {wo_file.filename}")
    result = extract_text_from_file(wo_file.file_path, wo_file.filename)

    if result.get('error'):
        print(f"OCR error: {result['error']}")
        return False

    text = result.get('text', '').strip()
    if not text:
        print(f"No text extracted from: {wo_file.filename}")
        return False

    # Prepare content for embedding (truncate if needed)
    # Include metadata for better search context
    content = f"Document: {wo_file.filename}\nWork Order: {wo_file.WorkOrderNo}\n\n{text}"

    # Truncate if too long (embedding models have limits)
    max_chars = 8000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."

    # Generate embedding
    try:
        embedding = get_embedding(content)
    except Exception as e:
        print(f"Embedding error: {e}")
        return False

    # Check for existing embedding
    existing = DocumentEmbedding.query.filter_by(file_id=file_id).first()

    if existing:
        # Update existing
        existing.content = content
        existing.ocr_text = text
        existing.embedding = embedding
        existing.ocr_confidence = result.get('confidence', 0)
        existing.ocr_method = result.get('method', 'unknown')
    else:
        # Create new
        doc_embedding = DocumentEmbedding(
            file_id=file_id,
            work_order_no=wo_file.WorkOrderNo,
            filename=wo_file.filename,
            s3_path=wo_file.file_path,
            ocr_text=text,
            content=content,
            embedding=embedding,
            ocr_confidence=result.get('confidence', 0),
            ocr_method=result.get('method', 'unknown')
        )
        db.session.add(doc_embedding)

    db.session.commit()
    print(f"Successfully processed: {wo_file.filename} ({len(text)} chars, {result.get('confidence', 0):.1f}% confidence)")
    return True


def sync_all_document_embeddings(batch_size: int = 10) -> Dict:
    """
    Sync embeddings for all work order files that don't have embeddings yet.

    Args:
        batch_size: Number of files to process at a time

    Returns:
        Dictionary with sync statistics
    """
    from sqlalchemy import not_

    stats = {
        "total_files": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "already_embedded": 0,
        "errors": []
    }

    # Get all S3 files that support OCR
    all_files = WorkOrderFile.query.filter(
        WorkOrderFile.file_path.like('s3://%')
    ).all()

    stats["total_files"] = len(all_files)

    # Get existing embeddings
    existing_ids = {
        e.file_id for e in DocumentEmbedding.query.with_entities(DocumentEmbedding.file_id).all()
    }

    for wo_file in all_files:
        # Skip if already embedded
        if wo_file.id in existing_ids:
            stats["already_embedded"] += 1
            continue

        # Skip unsupported file types
        if not is_ocr_supported(wo_file.filename):
            stats["skipped"] += 1
            continue

        # Try to sync
        try:
            success = sync_document_embedding(wo_file.id)
            if success:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{wo_file.filename}: {str(e)}")

    return stats


def search_documents(query: str, limit: int = 5) -> List[Dict]:
    """
    Search document embeddings using semantic similarity.

    Args:
        query: Search query text
        limit: Maximum number of results

    Returns:
        List of matching documents with similarity scores
    """
    from services.rag_service import get_embedding
    from sqlalchemy import text

    # Get query embedding
    query_embedding = get_embedding(query)

    # Use cosine similarity search
    # PostgreSQL array comparison with pgvector extension
    sql = text("""
        SELECT
            id,
            file_id,
            work_order_no,
            filename,
            ocr_text,
            content,
            ocr_confidence,
            1 - (embedding <=> :query_embedding::vector) as similarity
        FROM document_embeddings
        ORDER BY embedding <=> :query_embedding::vector
        LIMIT :limit
    """)

    try:
        result = db.session.execute(sql, {
            "query_embedding": str(query_embedding),
            "limit": limit
        })

        documents = []
        for row in result:
            documents.append({
                "id": row.id,
                "file_id": row.file_id,
                "work_order_no": row.work_order_no,
                "filename": row.filename,
                "ocr_text": row.ocr_text[:500] + "..." if len(row.ocr_text or "") > 500 else row.ocr_text,
                "ocr_confidence": row.ocr_confidence,
                "similarity": float(row.similarity) if row.similarity else 0
            })

        return documents

    except Exception as e:
        print(f"Document search error: {e}")
        return []


def get_document_stats() -> Dict:
    """Get statistics about document embeddings."""
    from sqlalchemy import func

    total = DocumentEmbedding.query.count()

    # Count by OCR method
    by_method = db.session.query(
        DocumentEmbedding.ocr_method,
        func.count(DocumentEmbedding.id)
    ).group_by(DocumentEmbedding.ocr_method).all()

    # Average confidence
    avg_conf = db.session.query(
        func.avg(DocumentEmbedding.ocr_confidence)
    ).scalar() or 0

    # Files without embeddings
    total_files = WorkOrderFile.query.filter(
        WorkOrderFile.file_path.like('s3://%')
    ).count()

    return {
        "total_embedded": total,
        "total_s3_files": total_files,
        "pending": total_files - total,
        "average_confidence": round(float(avg_conf), 2),
        "by_method": dict(by_method)
    }
