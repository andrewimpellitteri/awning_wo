"""
RAG (Retrieval-Augmented Generation) Service for the Awning Management chatbot.

This service provides:
- Embedding generation using OpenAI text-embedding-3-small API
- Semantic search over customers, work orders, and items
- Chat completion with context-aware responses using DeepSeek V3
- Function calling / tool use for read-only database queries
"""

import os
import json
import time
from typing import List, Dict, Optional, Tuple, Callable
import numpy as np
from openai import OpenAI
from extensions import db
from models.embeddings import (
    CustomerEmbedding,
    WorkOrderEmbedding,
    ItemEmbedding,
    DocumentationEmbedding,
)
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem

# Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/")
DEEPSEEK_CHAT_MODEL = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

# OpenAI API for embeddings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = 1536  # text-embedding-3-small default dimension

# Initialize clients
_deepseek_client = None
_openai_client = None


def get_deepseek_client() -> OpenAI:
    global _deepseek_client
    if _deepseek_client is None:
        if not DEEPSEEK_API_KEY:
            raise DeepSeekError("DEEPSEEK_API_KEY environment variable is not set")
        try:
            _deepseek_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,  # make sure this is exactly https://api.deepseek.com/v1
            )
        except Exception as e:
            raise DeepSeekError(f"Failed to initialize DeepSeek client: {e}") from e
    return _deepseek_client


def get_openai_client() -> OpenAI:
    """Get or create the OpenAI client for embeddings."""
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise DeepSeekError("OPENAI_API_KEY environment variable is not set")
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# Cache for API status to avoid repeated health checks
_api_status_cache = {"last_check": 0, "is_available": False}


class DeepSeekError(Exception):
    """Exception raised when DeepSeek API calls fail."""

    pass


# Keep OllamaError as alias for backwards compatibility
OllamaError = DeepSeekError


def is_ollama_available() -> bool:
    """
    Check if DeepSeek API is available with caching (1 minute cache).
    Named for backwards compatibility with existing code.

    Returns:
        True if DeepSeek API is responding, False otherwise
    """
    return is_deepseek_available()


def is_deepseek_available() -> bool:
    """
    Check if DeepSeek API is available with caching (1 minute cache).

    Returns:
        True if DeepSeek API is responding, False otherwise
    """
    current_time = time.time()

    # Use cached result if less than 60 seconds old
    if current_time - _api_status_cache["last_check"] < 60:
        return _api_status_cache["is_available"]

    # Check DeepSeek API status by making a simple models list call
    try:
        if not DEEPSEEK_API_KEY:
            is_available = False
        else:
            client = get_deepseek_client()
            # Try to list models as a health check
            client.models.list()
            is_available = True
    except Exception:
        is_available = False

    # Update cache
    _api_status_cache["last_check"] = current_time
    _api_status_cache["is_available"] = is_available

    return is_available


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI API.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding vector

    Raises:
        DeepSeekError: If embedding generation fails
    """
    try:
        client = get_openai_client()
        response = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=text)
        return response.data[0].embedding
    except Exception as e:
        raise DeepSeekError(f"Failed to generate embedding: {str(e)}")


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (batch processing via OpenAI API).

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    try:
        client = get_openai_client()
        # OpenAI API supports batch embedding (up to 2048 inputs)
        response = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
        return [data.embedding for data in response.data]
    except Exception as e:
        # Fallback to individual encoding on error
        embeddings = []
        for text in texts:
            try:
                embedding = get_embedding(text)
                embeddings.append(embedding)
            except DeepSeekError:
                embeddings.append([])
        return embeddings


def search_similar_customers(
    query_embedding: List[float], limit: int = 5
) -> List[Dict]:
    """
    Search for customers similar to the query embedding using pgvector.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of customer results with similarity scores
    """
    # The <=> operator in pgvector is cosine distance. 1 - distance = similarity.
    results = (
        db.session.query(
            CustomerEmbedding,
            CustomerEmbedding.embedding.cosine_distance(query_embedding).label(
                "distance"
            ),
        )
        .order_by(CustomerEmbedding.embedding.cosine_distance(query_embedding))
        .limit(limit)
        .all()
    )

    return [
        {
            "type": "customer",
            "id": emb.customer_id,
            "content": emb.content,
            "similarity": 1 - distance,
        }
        for emb, distance in results
    ]


def search_similar_work_orders(
    query_embedding: List[float], limit: int = 5
) -> List[Dict]:
    """
    Search for work orders similar to the query embedding using pgvector.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of work order results with similarity scores
    """
    results = (
        db.session.query(
            WorkOrderEmbedding,
            WorkOrderEmbedding.embedding.cosine_distance(query_embedding).label(
                "distance"
            ),
        )
        .order_by(WorkOrderEmbedding.embedding.cosine_distance(query_embedding))
        .limit(limit)
        .all()
    )

    return [
        {
            "type": "work_order",
            "id": emb.work_order_no,
            "content": emb.content,
            "similarity": 1 - distance,
        }
        for emb, distance in results
    ]


def search_similar_items(query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """
    Search for items similar to the query embedding using pgvector.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of item results with similarity scores
    """
    results = (
        db.session.query(
            ItemEmbedding,
            ItemEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .order_by(ItemEmbedding.embedding.cosine_distance(query_embedding))
        .limit(limit)
        .all()
    )

    return [
        {
            "type": "item",
            "id": emb.item_id,
            "content": emb.content,
            "similarity": 1 - distance,
        }
        for emb, distance in results
    ]


def search_similar_documentation(
    query_embedding: List[float], limit: int = 5
) -> List[Dict]:
    """Search for documentation similar to the query embedding using pgvector.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of documentation results with similarity scores
    """
    results = (
        db.session.query(
            DocumentationEmbedding,
            DocumentationEmbedding.embedding.cosine_distance(query_embedding).label(
                "distance"
            ),
        )
        .order_by(DocumentationEmbedding.embedding.cosine_distance(query_embedding))
        .limit(limit)
        .all()
    )

    return [
        {
            "type": "documentation",
            "id": emb.file_path,
            "title": emb.title,
            "category": emb.category,
            "content": emb.content,
            "similarity": 1 - distance,
        }
        for emb, distance in results
    ]


def search_all(query: str, limit_per_type: int = 3) -> Dict[str, List[Dict]]:
    """
    Search across all embedding types for relevant context.

    Args:
        query: The search query
        limit_per_type: Maximum results per type

    Returns:
        Dictionary with results for each type
    """
    try:
        query_embedding = get_embedding(query)
    except OllamaError as e:
        return {
            "error": str(e),
            "customers": [],
            "work_orders": [],
            "items": [],
            "documentation": [],
        }

    return {
        "customers": search_similar_customers(query_embedding, limit_per_type),
        "work_orders": search_similar_work_orders(query_embedding, limit_per_type),
        "items": search_similar_items(query_embedding, limit_per_type),
        "documentation": search_similar_documentation(query_embedding, limit_per_type),
    }


def build_context_from_search(
    search_results: Dict[str, List[Dict]], min_similarity: float = 0.3
) -> str:
    """
    Build a context string from search results for the LLM.

    Args:
        search_results: Results from search_all()
        min_similarity: Minimum similarity score to include

    Returns:
        Formatted context string
    """
    context_parts = []

    # Add customer context
    customers = [
        r
        for r in search_results.get("customers", [])
        if r["similarity"] >= min_similarity
    ]
    if customers:
        context_parts.append("RELEVANT CUSTOMERS:")
        for c in customers:
            context_parts.append(f"- {c['content']}")

    # Add work order context
    work_orders = [
        r
        for r in search_results.get("work_orders", [])
        if r["similarity"] >= min_similarity
    ]
    if work_orders:
        context_parts.append("\nRELEVANT WORK ORDERS:")
        for wo in work_orders:
            context_parts.append(f"- {wo['content']}")

    # Add item context
    items = [
        r for r in search_results.get("items", []) if r["similarity"] >= min_similarity
    ]
    if items:
        context_parts.append("\nRELEVANT ITEMS:")
        for item in items:
            context_parts.append(f"- {item['content']}")

    # Add documentation context
    documentation = [
        r
        for r in search_results.get("documentation", [])
        if r["similarity"] >= min_similarity
    ]
    if documentation:
        context_parts.append("\nRELEVANT DOCUMENTATION:")
        for doc in documentation:
            context_parts.append(
                f"- [{doc['title']}] ({doc['category']}) - {doc['content'][:200]}..."
            )

    return "\n".join(context_parts) if context_parts else ""


def chat_completion(
    messages: List[Dict[str, str]], context: str = "", system_prompt: str = None
) -> Tuple[str, Dict]:
    """
    Generate a chat completion using DeepSeek V3 with optional RAG context.

    Args:
        messages: List of message dicts with 'role' and 'content'
        context: Retrieved context to include
        system_prompt: Optional custom system prompt

    Returns:
        Tuple of (response_text, metadata)

    Raises:
        DeepSeekError: If the API call fails
    """
    default_system = """You are 'AwningBot', a helpful AI assistant for the Awning Management System.
Your goal is to answer user questions based *only* on the information provided in the 'RELEVANT INFORMATION' section.

**Core Instructions:**
1.  **Strictly Grounded:** Your answers MUST be based exclusively on the text provided in the 'RELEVANT INFORMATION' context. Do not use any external knowledge or make assumptions.
2.  **Cite Your Sources:** When you pull information from a specific record, mention its ID (e.g., "Customer ID: CUST123", "Work Order: WO5678").
3.  **Handle Missing Information:** If the answer to the user's question is not present in the 'RELEVANT INFORMATION', you MUST state that you do not have enough information to answer. Do not try to guess.
4.  **Be Concise and Factual:** Provide clear, factual answers. Use lists or tables to format structured data.
5.  **Professional Tone:** Maintain a professional and helpful tone.
"""

    system = system_prompt or default_system

    # Add context to system prompt if available
    if context:
        system += f"\n\nHere is relevant information from the database:\n{context}"

    # Build messages for DeepSeek (OpenAI-compatible format)
    api_messages = [{"role": "system", "content": system}]
    api_messages.extend(messages)

    try:
        client = get_deepseek_client()
        response = client.responses.create(
            model=DEEPSEEK_CHAT_MODEL,
            input=api_messages,
            temperature=0.2,
            max_output_tokens=2048,
        )

        response_text = ""
        for item in response.output:
            if item["type"] == "message":
                for content in item["content"]:
                    if content["type"] == "output_text":
                        response_text += content["text"]

        metadata = {
            "model": DEEPSEEK_CHAT_MODEL,
            "context_provided": bool(context),
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens
            if response.usage
            else None,
            "total_tokens": response.usage.total_tokens if response.usage else None,
        }

        return response_text, metadata

    except Exception as e:
        raise DeepSeekError(f"Failed to get chat completion: {str(e)}")


def chat_with_rag(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    work_order_context: str = None,
    customer_context: str = None,
) -> Tuple[str, Dict]:
    """
    High-level function to chat with RAG-enhanced context.

    Args:
        user_message: The user's message
        conversation_history: Previous messages in the conversation
        work_order_context: Optional specific work order to focus on
        customer_context: Optional specific customer to focus on

    Returns:
        Tuple of (response_text, metadata_with_sources)
    """
    # Search for relevant context
    search_results = search_all(user_message, limit_per_type=3)

    # Build context string
    context = build_context_from_search(search_results)

    # Add specific context if provided
    additional_context = []
    if work_order_context:
        wo = WorkOrder.query.get(work_order_context)
        if wo:
            additional_context.append(
                f"CURRENT WORK ORDER: {wo.WorkOrderNo} - {wo.WOName}"
            )
            additional_context.append(f"  Customer: {wo.CustID}")
            additional_context.append(
                f"  Special Instructions: {wo.SpecialInstructions or 'None'}"
            )
            additional_context.append(f"  Return Status: {wo.ReturnStatus or 'N/A'}")

    if customer_context:
        cust = Customer.query.get(customer_context)
        if cust:
            additional_context.append(f"CURRENT CUSTOMER: {cust.CustID} - {cust.Name}")
            additional_context.append(f"  Contact: {cust.Contact or 'N/A'}")
            additional_context.append(f"  Phone: {cust.get_primary_phone() or 'N/A'}")

    if additional_context:
        context = "\n".join(additional_context) + "\n\n" + context

    # Build messages
    messages = conversation_history or []
    messages.append({"role": "user", "content": user_message})

    # Get completion
    response_text, metadata = chat_completion(messages, context)

    # Add sources to metadata
    metadata["sources"] = {
        "customers": [r["id"] for r in search_results.get("customers", [])[:3]],
        "work_orders": [r["id"] for r in search_results.get("work_orders", [])[:3]],
        "items": [r["id"] for r in search_results.get("items", [])[:3]],
    }

    return response_text, metadata


# ============================================================================
# Embedding Management Functions
# ============================================================================


def create_customer_text(customer: Customer) -> str:
    """Create searchable text representation of a customer."""
    parts = [
        f"Customer ID: {customer.CustID}",
        f"Name: {customer.Name or 'Unknown'}",
    ]

    if customer.Contact:
        parts.append(f"Contact: {customer.Contact}")
    if customer.get_full_address():
        parts.append(f"Address: {customer.get_full_address()}")
    if customer.clean_email():
        parts.append(f"Email: {customer.clean_email()}")
    if customer.Source:
        parts.append(f"Source: {customer.Source}")

    return " | ".join(parts)


def create_work_order_text(work_order: WorkOrder) -> str:
    """Create searchable text representation of a work order."""
    parts = [
        f"Work Order: {work_order.WorkOrderNo}",
        f"Name: {work_order.WOName or 'Unnamed'}",
        f"Customer: {work_order.CustID}",
    ]

    if work_order.SpecialInstructions:
        parts.append(f"Instructions: {work_order.SpecialInstructions}")
    if work_order.ReturnStatus:
        parts.append(f"Return Status: {work_order.ReturnStatus}")
    if work_order.StorageTime:
        parts.append(f"Storage: {work_order.StorageTime}")
    if work_order.RackNo:
        parts.append(f"Location: {work_order.RackNo}")
    if work_order.ShipTo:
        parts.append(f"Ship To: {work_order.ShipTo}")

    return " | ".join(parts)


def create_item_text(item: WorkOrderItem) -> str:
    """Create searchable text representation of an item."""
    parts = [
        f"Item: {item.Description}",
        f"Work Order: {item.WorkOrderNo}",
    ]

    if item.Material:
        parts.append(f"Material: {item.Material}")
    if item.Color:
        parts.append(f"Color: {item.Color}")
    if item.Condition:
        parts.append(f"Condition: {item.Condition}")
    if item.SizeWgt:
        parts.append(f"Size/Weight: {item.SizeWgt}")
    if item.Qty:
        parts.append(f"Quantity: {item.Qty}")

    return " | ".join(parts)


def create_documentation_text(
    file_path: str, title: str = None, category: str = None, content: str = None
) -> str:
    """Create searchable text representation of a documentation file.

    Args:
        file_path: Relative path from project root
        title: Document title (extracted from H1 or filename)
        category: Category folder (architecture, developer-guide, etc.)
        content: Full markdown content

    Returns:
        Pipe-separated searchable text
    """
    parts = [
        f"Documentation: {title or 'Untitled'}",
        f"Category: {category or 'General'}",
        f"Path: {file_path}",
    ]

    # Add first 500 chars of content as preview
    if content:
        preview = content.replace("\n", " ")[:500]
        parts.append(f"Content: {preview}")

    return " | ".join(parts)


def extract_markdown_metadata(file_path: str) -> Dict[str, str]:
    """Extract title and category from markdown file.

    Args:
        file_path: Absolute or relative path to .md file

    Returns:
        Dict with 'title', 'category', 'content', 'relative_path'
    """
    import os
    import re

    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract title from first H1 heading
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = (
        title_match.group(1)
        if title_match
        else os.path.basename(file_path).replace(".md", "")
    )

    # Extract category from path
    relative_path = file_path.replace(os.getcwd() + "/", "")
    parts = relative_path.split("/")
    category = parts[1] if len(parts) > 2 and parts[0] == "docs" else "general"

    return {
        "title": title,
        "category": category,
        "content": content,
        "relative_path": relative_path,
    }


def sync_customer_embedding(customer_id: str) -> bool:
    """
    Create or update embedding for a single customer.

    Args:
        customer_id: The customer ID to sync

    Returns:
        True if successful, False otherwise
    """
    customer = Customer.query.get(customer_id)
    if not customer:
        return False

    text = create_customer_text(customer)

    try:
        embedding = get_embedding(text)
    except OllamaError:
        return False

    # Check if embedding exists
    existing = CustomerEmbedding.query.filter_by(customer_id=customer_id).first()

    if existing:
        existing.content = text
        existing.embedding = embedding
    else:
        new_emb = CustomerEmbedding(
            customer_id=customer_id, content=text, embedding=embedding
        )
        db.session.add(new_emb)

    db.session.commit()
    return True


def sync_work_order_embedding(work_order_no: str) -> bool:
    """
    Create or update embedding for a single work order.

    Args:
        work_order_no: The work order number to sync

    Returns:
        True if successful, False otherwise
    """
    work_order = WorkOrder.query.get(work_order_no)
    if not work_order:
        return False

    text = create_work_order_text(work_order)

    try:
        embedding = get_embedding(text)
    except OllamaError:
        return False

    # Check if embedding exists
    existing = WorkOrderEmbedding.query.filter_by(work_order_no=work_order_no).first()

    if existing:
        existing.content = text
        existing.embedding = embedding
    else:
        new_emb = WorkOrderEmbedding(
            work_order_no=work_order_no, content=text, embedding=embedding
        )
        db.session.add(new_emb)

    db.session.commit()
    return True


def sync_item_embedding(item_id: int) -> bool:
    """
    Create or update embedding for a single item.

    Args:
        item_id: The item ID to sync

    Returns:
        True if successful, False otherwise
    """
    item = WorkOrderItem.query.get(item_id)
    if not item:
        return False

    text = create_item_text(item)

    try:
        embedding = get_embedding(text)
    except OllamaError:
        return False

    # Check if embedding exists
    existing = ItemEmbedding.query.filter_by(item_id=item_id).first()

    if existing:
        existing.content = text
        existing.embedding = embedding
    else:
        new_emb = ItemEmbedding(item_id=item_id, content=text, embedding=embedding)
        db.session.add(new_emb)

    db.session.commit()
    return True


def sync_documentation_embedding(file_path: str) -> bool:
    """Create or update embedding for a documentation file.

    Args:
        file_path: Path to markdown file (absolute or relative)

    Returns:
        True if successful, False otherwise
    """
    import os

    # Make path absolute if needed
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    if not os.path.exists(file_path):
        return False

    try:
        # Extract metadata
        metadata = extract_markdown_metadata(file_path)

        # Create searchable text
        text = create_documentation_text(
            metadata["relative_path"],
            metadata["title"],
            metadata["category"],
            metadata["content"],
        )

        # Generate embedding
        embedding = get_embedding(text)

        # Check if embedding exists
        existing = DocumentationEmbedding.query.filter_by(
            file_path=metadata["relative_path"]
        ).first()

        if existing:
            existing.title = metadata["title"]
            existing.category = metadata["category"]
            existing.content = text
            existing.embedding = embedding
        else:
            new_emb = DocumentationEmbedding(
                file_path=metadata["relative_path"],
                title=metadata["title"],
                category=metadata["category"],
                content=text,
                embedding=embedding,
            )
            db.session.add(new_emb)

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error syncing documentation {file_path}: {e}")
        return False


def sync_all_embeddings(batch_size: int = 100) -> Dict[str, int]:
    """
    Sync embeddings for all customers, work orders, and items.

    This is a batch operation that should be run periodically or on-demand.

    Args:
        batch_size: Number of records to process in each batch

    Returns:
        Dictionary with counts of synced records
    """
    stats = {
        "customers_synced": 0,
        "customers_failed": 0,
        "work_orders_synced": 0,
        "work_orders_failed": 0,
        "items_synced": 0,
        "items_failed": 0,
    }

    # Sync customers
    customers = Customer.query.all()
    for customer in customers:
        if sync_customer_embedding(customer.CustID):
            stats["customers_synced"] += 1
        else:
            stats["customers_failed"] += 1

    # Sync work orders
    work_orders = WorkOrder.query.all()
    for wo in work_orders:
        if sync_work_order_embedding(wo.WorkOrderNo):
            stats["work_orders_synced"] += 1
        else:
            stats["work_orders_failed"] += 1

    # Sync items
    items = WorkOrderItem.query.all()
    for item in items:
        if sync_item_embedding(item.id):
            stats["items_synced"] += 1
        else:
            stats["items_failed"] += 1

    return stats


def sync_all_documentation_embeddings(docs_path: str = "docs") -> Dict[str, int]:
    """Sync embeddings for all markdown documentation files.

    Args:
        docs_path: Path to documentation directory (default: docs)

    Returns:
        Dictionary with sync statistics
    """
    import os
    import glob

    stats = {"synced": 0, "failed": 0, "skipped": 0}

    # Find all .md files in docs directory
    pattern = os.path.join(docs_path, "**/*.md")
    md_files = glob.glob(pattern, recursive=True)

    for file_path in md_files:
        # Skip certain files if needed
        if "node_modules" in file_path or ".venv" in file_path:
            stats["skipped"] += 1
            continue

        if sync_documentation_embedding(file_path):
            stats["synced"] += 1
        else:
            stats["failed"] += 1

    return stats


def check_ollama_status() -> Dict:
    """
    Check if DeepSeek API is available and configured.
    Named for backwards compatibility with existing code.

    Returns:
        Dictionary with status information
    """
    return check_deepseek_status()


def check_deepseek_status() -> Dict:
    """
    Check if DeepSeek API and OpenAI embedding API are available.

    Returns:
        Dictionary with status information
    """
    status = {
        "api_available": False,
        "api_configured": bool(DEEPSEEK_API_KEY),
        "embed_model": OPENAI_EMBED_MODEL,
        "embed_model_local": False,
        "embed_api_configured": bool(OPENAI_API_KEY),
        "chat_model": DEEPSEEK_CHAT_MODEL,
        "base_url": DEEPSEEK_BASE_URL,
        # Keep old keys for backwards compatibility
        "ollama_running": False,
        "embed_model_available": False,
        "chat_model_available": False,
    }

    # Check OpenAI embedding API
    if not OPENAI_API_KEY:
        status["embed_error"] = "OPENAI_API_KEY environment variable is not set"
    else:
        try:
            client = get_openai_client()
            # Try to generate a test embedding as health check
            test_response = client.embeddings.create(
                model=OPENAI_EMBED_MODEL, input="test"
            )
            status["embed_model_available"] = True
            status["embed_dimension"] = len(test_response.data[0].embedding)
        except Exception as e:
            status["embed_error"] = str(e)

    if not DEEPSEEK_API_KEY:
        status["error"] = "DEEPSEEK_API_KEY environment variable is not set"
        return status

    try:
        client = get_deepseek_client()
        # Try to list models as a health check
        models_response = client.models.list()
        status["api_available"] = True
        status["ollama_running"] = True  # Backwards compatibility

        # Get available models
        available_models = (
            [m.id for m in models_response.data] if models_response.data else []
        )
        status["available_models"] = available_models

        # Check if our chat model is available
        status["chat_model_available"] = (
            DEEPSEEK_CHAT_MODEL in available_models or "deepseek" in DEEPSEEK_CHAT_MODEL
        )

    except Exception as e:
        status["error"] = str(e)

    return status


# ============================================================================
# Tool Definitions for Function Calling
# ============================================================================

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "Search for customers by name, ID, contact person, or any text. Returns matching customers with their details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - can be customer name, ID, contact name, email, or any keyword",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_details",
            "description": "Get full details for a specific customer by their ID, including contact info and work order history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., 'CUST001' or 'ABC123')",
                    }
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_work_orders",
            "description": "Search for work orders by number, customer, status, or any text. Returns matching work orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - can be work order number, customer ID, status, or keyword",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by return status (optional)",
                        "enum": ["In", "Out", "Pending", "Complete"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_order_details",
            "description": "Get full details for a specific work order including all items, customer info, and special instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "work_order_no": {
                        "type": "string",
                        "description": "The work order number (e.g., 'WO001' or '12345')",
                    }
                },
                "required": ["work_order_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_work_orders",
            "description": "Get all work orders for a specific customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of work orders to return (default 20)",
                        "default": 20,
                    },
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "Search for items by description, material, color, or condition.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - can be item description, material, color, etc.",
                    },
                    "material": {
                        "type": "string",
                        "description": "Filter by material type (optional)",
                    },
                    "color": {
                        "type": "string",
                        "description": "Filter by color (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_order_stats",
            "description": "Get statistics about work orders - counts by status, recent activity, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Optional: filter stats by customer ID",
                    }
                },
                "required": [],
            },
        },
    },
]


# ============================================================================
# Tool Implementation Functions
# ============================================================================


def tool_search_customers(query: str, limit: int = 5) -> Dict:
    """Search customers by query text."""
    query_lower = query.lower()

    # Search in database
    customers = (
        Customer.query.filter(
            db.or_(
                Customer.CustID.ilike(f"%{query}%"),
                Customer.Name.ilike(f"%{query}%"),
                Customer.Contact.ilike(f"%{query}%"),
                Customer.EmailAddress.ilike(f"%{query}%"),
            )
        )
        .limit(limit)
        .all()
    )

    results = []
    for c in customers:
        results.append(
            {
                "customer_id": c.CustID,
                "name": c.Name,
                "contact": c.Contact,
                "phone": c.get_primary_phone(),
                "email": c.clean_email(),
                "address": c.get_full_address(),
            }
        )

    return {"query": query, "count": len(results), "customers": results}


def tool_get_customer_details(customer_id: str) -> Dict:
    """Get full details for a customer."""
    customer = Customer.query.get(customer_id)

    if not customer:
        return {"error": f"Customer '{customer_id}' not found"}

    # Get work order count
    work_orders = WorkOrder.query.filter_by(CustID=customer_id).all()

    return {
        "customer_id": customer.CustID,
        "name": customer.Name,
        "contact": customer.Contact,
        "phone": customer.get_primary_phone(),
        "email": customer.clean_email(),
        "address": customer.get_full_address(),
        "source": customer.Source,
        "work_order_count": len(work_orders),
        "recent_work_orders": [
            {
                "work_order_no": wo.WorkOrderNo,
                "name": wo.WOName,
                "status": wo.ReturnStatus,
            }
            for wo in work_orders[:5]
        ],
    }


def tool_search_work_orders(query: str, status: str = None, limit: int = 10) -> Dict:
    """Search work orders by query text."""
    filters = [
        db.or_(
            WorkOrder.WorkOrderNo.ilike(f"%{query}%"),
            WorkOrder.WOName.ilike(f"%{query}%"),
            WorkOrder.CustID.ilike(f"%{query}%"),
            WorkOrder.SpecialInstructions.ilike(f"%{query}%"),
        )
    ]

    if status:
        filters.append(WorkOrder.ReturnStatus == status)

    work_orders = WorkOrder.query.filter(*filters).limit(limit).all()

    results = []
    for wo in work_orders:
        results.append(
            {
                "work_order_no": wo.WorkOrderNo,
                "name": wo.WOName,
                "customer_id": wo.CustID,
                "status": wo.ReturnStatus,
                "rack_location": wo.RackNo,
                "special_instructions": wo.SpecialInstructions[:100]
                if wo.SpecialInstructions
                else None,
            }
        )

    return {
        "query": query,
        "status_filter": status,
        "count": len(results),
        "work_orders": results,
    }


def tool_get_work_order_details(work_order_no: str) -> Dict:
    """Get full details for a work order."""
    wo = WorkOrder.query.get(work_order_no)

    if not wo:
        return {"error": f"Work order '{work_order_no}' not found"}

    # Get items
    items = WorkOrderItem.query.filter_by(WorkOrderNo=work_order_no).all()

    # Get customer
    customer = Customer.query.get(wo.CustID) if wo.CustID else None

    # Determine if order is open or closed
    is_open = wo.DateCompleted is None

    # Calculate age from creation date
    from datetime import datetime

    age_days = None
    if wo.created_at:
        age_days = (datetime.utcnow() - wo.created_at).days

    return {
        "work_order_no": wo.WorkOrderNo,
        "name": wo.WOName,
        "customer": {
            "id": wo.CustID,
            "name": customer.Name if customer else None,
        },
        "status": wo.ReturnStatus,
        "is_open": is_open,
        "created_at": wo.created_at.strftime("%Y-%m-%d") if wo.created_at else None,
        "completed_at": wo.DateCompleted.strftime("%Y-%m-%d")
        if wo.DateCompleted
        else None,
        "age_days": age_days,
        "date_in": wo.DateIn.strftime("%Y-%m-%d") if wo.DateIn else None,
        "clean_date": wo.Clean.strftime("%Y-%m-%d") if wo.Clean else None,
        "treat_date": wo.Treat.strftime("%Y-%m-%d") if wo.Treat else None,
        "rack_location": wo.RackNo,
        "storage_time": wo.StorageTime,
        "special_instructions": wo.SpecialInstructions,
        "ship_to": wo.ShipTo,
        "item_count": len(items),
        "items": [
            {
                "id": item.id,
                "description": item.Description,
                "material": item.Material,
                "color": item.Color,
                "condition": item.Condition,
                "quantity": item.Qty,
            }
            for item in items
        ],
    }


def tool_get_customer_work_orders(customer_id: str, limit: int = 20) -> Dict:
    """Get all work orders for a customer with enhanced temporal and status context."""
    customer = Customer.query.get(customer_id)

    if not customer:
        return {"error": f"Customer '{customer_id}' not found"}

    work_orders = (
        WorkOrder.query.filter_by(CustID=customer_id)
        .order_by(WorkOrder.created_at.desc())
        .limit(limit)
        .all()
    )

    # Calculate age and status for each order
    from datetime import datetime

    enriched_orders = []
    for wo in work_orders:
        is_open = wo.DateCompleted is None
        age_days = None
        if wo.created_at:
            age_days = (datetime.utcnow() - wo.created_at).days

        enriched_orders.append(
            {
                "work_order_no": wo.WorkOrderNo,
                "name": wo.WOName,
                "status": wo.ReturnStatus,
                "is_open": is_open,
                "created_at": wo.created_at.strftime("%Y-%m-%d")
                if wo.created_at
                else None,
                "completed_at": wo.DateCompleted.strftime("%Y-%m-%d")
                if wo.DateCompleted
                else None,
                "age_days": age_days,
                "rack_location": wo.RackNo,
                "ship_to": wo.ShipTo,
                "storage_time": wo.StorageTime,
            }
        )

    # Separate into open and closed orders
    open_orders = [o for o in enriched_orders if o["is_open"]]
    closed_orders = [o for o in enriched_orders if not o["is_open"]]

    return {
        "customer_id": customer_id,
        "customer_name": customer.Name,
        "total_count": len(work_orders),
        "open_count": len(open_orders),
        "closed_count": len(closed_orders),
        "work_orders": enriched_orders,
        "open_work_orders": open_orders,
        "closed_work_orders": closed_orders,
    }


def tool_search_items(
    query: str, material: str = None, color: str = None, limit: int = 10
) -> Dict:
    """Search items by query text."""
    filters = [
        db.or_(
            WorkOrderItem.Description.ilike(f"%{query}%"),
            WorkOrderItem.Material.ilike(f"%{query}%"),
            WorkOrderItem.Color.ilike(f"%{query}%"),
        )
    ]

    if material:
        filters.append(WorkOrderItem.Material.ilike(f"%{material}%"))
    if color:
        filters.append(WorkOrderItem.Color.ilike(f"%{color}%"))

    items = WorkOrderItem.query.filter(*filters).limit(limit).all()

    results = []
    for item in items:
        results.append(
            {
                "id": item.id,
                "work_order_no": item.WorkOrderNo,
                "description": item.Description,
                "material": item.Material,
                "color": item.Color,
                "condition": item.Condition,
                "quantity": item.Qty,
            }
        )

    return {
        "query": query,
        "material_filter": material,
        "color_filter": color,
        "count": len(results),
        "items": results,
    }


def tool_get_work_order_stats(customer_id: str = None) -> Dict:
    """Get work order statistics."""
    query = WorkOrder.query

    if customer_id:
        query = query.filter_by(CustID=customer_id)

    work_orders = query.all()

    # Count by status
    status_counts = {}
    for wo in work_orders:
        status = wo.ReturnStatus or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    # Count items
    total_items = 0
    if customer_id:
        for wo in work_orders:
            total_items += WorkOrderItem.query.filter_by(
                WorkOrderNo=wo.WorkOrderNo
            ).count()
    else:
        total_items = WorkOrderItem.query.count()

    return {
        "customer_id": customer_id,
        "total_work_orders": len(work_orders),
        "total_items": total_items,
        "by_status": status_counts,
    }


# Map tool names to functions
TOOL_FUNCTIONS: Dict[str, Callable] = {
    "search_customers": tool_search_customers,
    "get_customer_details": tool_get_customer_details,
    "search_work_orders": tool_search_work_orders,
    "get_work_order_details": tool_get_work_order_details,
    "get_customer_work_orders": tool_get_customer_work_orders,
    "search_items": tool_search_items,
    "get_work_order_stats": tool_get_work_order_stats,
}


def execute_tool(tool_name: str, arguments: Dict) -> str:
    """Execute a tool and return the result as JSON string."""
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = TOOL_FUNCTIONS[tool_name](**arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {str(e)}"})


# ============================================================================
# Chat with Tools (Function Calling)
# ============================================================================


def chat_with_tools(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    max_tool_calls: int = 5,
) -> Tuple[str, Dict]:
    """
    Chat with the LLM using function calling for database queries.

    Args:
        user_message: The user's message
        conversation_history: Previous messages in the conversation
        max_tool_calls: Maximum number of tool calls to allow

    Returns:
        Tuple of (response_text, metadata)
    """
    system_prompt = """You are 'AwningBot', an expert AI assistant for an awning cleaning and repair business. Your primary goal is to help staff by providing accurate and timely information from the company's database.

**Your Persona:**
- You are professional, efficient, and precise.
- You are here to provide data-driven answers, not to chat conversationally.
- Your responses should be clear, concise, and directly address the user's question.

**Core Instructions:**
1.  **Tool First:** Your first instinct should ALWAYS be to use a tool. The database contains the most accurate information. Do not try to answer from memory or general knowledge.
2.  **Analyze the User's Need:** Understand what the user is asking for. Is it a search for a specific record (`get_work_order_details`), a broad search (`search_customers`), or an aggregation (`get_work_order_stats`)? Choose the best tool for the job.
3.  **Execute and Synthesize:** After you receive the data from a tool, present it to the user in a clean, easy-to-read format. Use markdown tables, lists, and bold text to structure your answer.
4.  **Cite Your Sources:** When you provide details about a specific record (like a work order or customer), always mention its ID (e.g., "Work Order #56471").
5.  **Handle No Results:** If a tool returns no results, state that clearly. For example, "I could not find any work orders matching 'XYZ'." Do not apologize. Suggest a different search or broader criteria.
6.  **Handle Errors:** If a tool call fails, inform the user that you encountered an error trying to retrieve the data and suggest they try again.
7.  **Be Data-Driven:** Do not make assumptions beyond the data returned by the tools. If the user asks a question that the tools cannot answer, state that you do not have the ability to answer that question.
8.  **Clarify Ambiguity:** If the user's request is ambiguous (e.g., "look up Smith's order"), and a tool returns multiple customers named Smith, ask the user for clarification (e.g., "I found multiple customers named Smith. Can you provide a customer ID or a more specific name?").

**Temporal Context & Status Interpretation:**
9.  **Distinguish Order Age:** When presenting multiple work orders, ALWAYS note significant age differences. For example:
    - If one order is from 2023 (age_days > 365) and another is from this week (age_days < 14), explicitly state this: "WO#12345 is from 2023 (historical), while WO#67890 is from last week (active)."
10. **Identify Open vs Closed Orders:** Use the `is_open` and `completed_at` fields to distinguish active from historical orders:
    - If `is_open: true` and `completed_at: null`, describe it as "currently open" or "in progress"
    - If `is_open: false` and `completed_at` has a date, describe it as "completed on [date]" or "archived"
11. **Connect Related Work:** If you see multiple orders for the same customer with identical or similar items, note this relationship. For example: "This customer previously had service in 2023 for the same awnings, which may be related to the current mold issue."
12. **Interpret Process Status:** Use process dates (clean_date, treat_date) to explain where an order is in the workflow:
    - If `clean_date` exists but `completed_at` is null: "This order has been cleaned but is not yet complete."
    - If neither exist: "This order is awaiting processing."

**Response Formatting & Citations:**
13. **Structure Your Answers:** Use clear markdown formatting:
    - Use **bold** for important record IDs and key facts
    - Use bullet points or numbered lists for multiple items
    - Use markdown tables for comparing multiple records
14. **Always Cite Sources:** When you reference specific data, cite the source inline:
    - "According to **Work Order #56471**, the items were treated on 2025-01-15..."
    - "**Customer 25565** (Uhrig) has 2 work orders in the system..."
15. **Professional Tone:** Your responses should be informative but concise. Avoid unnecessary pleasantries. Get straight to the facts.

**Critical: Your responses should transform raw data into actionable insights by interpreting dates, statuses, and relationships.**

Your goal is to be a reliable interface to the database that provides context-aware, intelligent answers - not just raw data dumps. The UI will automatically display your tool calls and database queries in a separate citation section, so focus on providing a clear narrative in your main response.
"""

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    client = get_deepseek_client()
    tool_calls_made = []

    for _ in range(max_tool_calls):
        # Call the API with tools
        response = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=messages,
            tools=AVAILABLE_TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=2048,
        )

        assistant_message = response.choices[0].message

        # Check if we need to call tools
        if assistant_message.tool_calls:
            # Add assistant message to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )

            # Execute each tool call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = execute_tool(tool_name, arguments)
                tool_calls_made.append(
                    {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result_preview": result[:200] + "..."
                        if len(result) > 200
                        else result,
                    }
                )

                # Add tool result to messages
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )
        else:
            # No more tool calls, return the response
            response_text = assistant_message.content or ""
            metadata = {
                "model": DEEPSEEK_CHAT_MODEL,
                "tool_calls": tool_calls_made,
                "tool_calls_count": len(tool_calls_made),
                "prompt_tokens": response.usage.prompt_tokens
                if response.usage
                else None,
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else None,
                "total_tokens": response.usage.total_tokens if response.usage else None,
            }
            return response_text, metadata

    # Max tool calls reached, return last response
    response_text = (
        assistant_message.content
        or "I've gathered some information but reached the limit of queries I can make. Please try a more specific question."
    )
    metadata = {
        "model": DEEPSEEK_CHAT_MODEL,
        "tool_calls": tool_calls_made,
        "tool_calls_count": len(tool_calls_made),
        "max_calls_reached": True,
    }
    return response_text, metadata
