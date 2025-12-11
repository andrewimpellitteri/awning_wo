"""
RAG (Retrieval-Augmented Generation) Service for the Awning Management chatbot.

This service provides:
- Embedding generation using local sentence-transformers (no API needed)
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
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem

# Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_CHAT_MODEL = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

# Local embedding model configuration (sentence-transformers)
# all-MiniLM-L6-v2: Fast, 384 dimensions, ~80MB
# all-mpnet-base-v2: Better quality, 768 dimensions, ~420MB
LOCAL_EMBED_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 dimension

# Initialize clients
_deepseek_client = None
_embedding_model = None


def get_deepseek_client() -> OpenAI:
    """Get or create the DeepSeek client."""
    global _deepseek_client
    if _deepseek_client is None:
        if not DEEPSEEK_API_KEY:
            raise DeepSeekError("DEEPSEEK_API_KEY environment variable is not set")
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _deepseek_client


def get_embedding_model():
    """Get or create the local embedding model (lazy loading)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(LOCAL_EMBED_MODEL)
    return _embedding_model


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
    Generate embedding for text using local sentence-transformers model.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding vector

    Raises:
        DeepSeekError: If embedding generation fails
    """
    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        raise DeepSeekError(f"Failed to generate embedding: {str(e)}")


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (batch processing).

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    try:
        model = get_embedding_model()
        # sentence-transformers can batch encode efficiently
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]
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


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not a or not b:
        return 0.0
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot_product = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def search_similar_customers(query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """
    Search for customers similar to the query embedding.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of customer results with similarity scores
    """
    embeddings = CustomerEmbedding.query.all()
    results = []

    for emb in embeddings:
        similarity = cosine_similarity(query_embedding, emb.embedding)
        results.append({
            "type": "customer",
            "id": emb.customer_id,
            "content": emb.content,
            "similarity": similarity
        })

    # Sort by similarity (highest first)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def search_similar_work_orders(query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """
    Search for work orders similar to the query embedding.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of work order results with similarity scores
    """
    embeddings = WorkOrderEmbedding.query.all()
    results = []

    for emb in embeddings:
        similarity = cosine_similarity(query_embedding, emb.embedding)
        results.append({
            "type": "work_order",
            "id": emb.work_order_no,
            "content": emb.content,
            "similarity": similarity
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


def search_similar_items(query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """
    Search for items similar to the query embedding.

    Args:
        query_embedding: The query vector
        limit: Maximum number of results

    Returns:
        List of item results with similarity scores
    """
    embeddings = ItemEmbedding.query.all()
    results = []

    for emb in embeddings:
        similarity = cosine_similarity(query_embedding, emb.embedding)
        results.append({
            "type": "item",
            "id": emb.item_id,
            "content": emb.content,
            "similarity": similarity
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


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
        return {"error": str(e), "customers": [], "work_orders": [], "items": []}

    return {
        "customers": search_similar_customers(query_embedding, limit_per_type),
        "work_orders": search_similar_work_orders(query_embedding, limit_per_type),
        "items": search_similar_items(query_embedding, limit_per_type),
    }


def build_context_from_search(search_results: Dict[str, List[Dict]], min_similarity: float = 0.3) -> str:
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
    customers = [r for r in search_results.get("customers", []) if r["similarity"] >= min_similarity]
    if customers:
        context_parts.append("RELEVANT CUSTOMERS:")
        for c in customers:
            context_parts.append(f"- {c['content']}")

    # Add work order context
    work_orders = [r for r in search_results.get("work_orders", []) if r["similarity"] >= min_similarity]
    if work_orders:
        context_parts.append("\nRELEVANT WORK ORDERS:")
        for wo in work_orders:
            context_parts.append(f"- {wo['content']}")

    # Add item context
    items = [r for r in search_results.get("items", []) if r["similarity"] >= min_similarity]
    if items:
        context_parts.append("\nRELEVANT ITEMS:")
        for item in items:
            context_parts.append(f"- {item['content']}")

    return "\n".join(context_parts) if context_parts else ""


def chat_completion(
    messages: List[Dict[str, str]],
    context: str = "",
    system_prompt: str = None
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
    default_system = """You are a helpful assistant for the Awning Management System.
You help users with questions about customers, work orders, items, and general operations.
Be concise and helpful. If you reference specific records, mention their IDs.
If you don't have enough information to answer, say so clearly."""

    system = system_prompt or default_system

    # Add context to system prompt if available
    if context:
        system += f"\n\nHere is relevant information from the database:\n{context}"

    # Build messages for DeepSeek (OpenAI-compatible format)
    api_messages = [{"role": "system", "content": system}]
    api_messages.extend(messages)

    try:
        client = get_deepseek_client()
        response = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=api_messages,
            temperature=0.7,
            max_tokens=2048,
        )

        response_text = response.choices[0].message.content or ""
        metadata = {
            "model": DEEPSEEK_CHAT_MODEL,
            "context_provided": bool(context),
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
            "total_tokens": response.usage.total_tokens if response.usage else None,
        }

        return response_text, metadata

    except Exception as e:
        raise DeepSeekError(f"Failed to get chat completion: {str(e)}")


def chat_with_rag(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    work_order_context: str = None,
    customer_context: str = None
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
            additional_context.append(f"CURRENT WORK ORDER: {wo.WorkOrderNo} - {wo.WOName}")
            additional_context.append(f"  Customer: {wo.CustID}")
            additional_context.append(f"  Special Instructions: {wo.SpecialInstructions or 'None'}")
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
            customer_id=customer_id,
            content=text,
            embedding=embedding
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
            work_order_no=work_order_no,
            content=text,
            embedding=embedding
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
        new_emb = ItemEmbedding(
            item_id=item_id,
            content=text,
            embedding=embedding
        )
        db.session.add(new_emb)

    db.session.commit()
    return True


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
    Check if DeepSeek API and local embedding model are available.

    Returns:
        Dictionary with status information
    """
    status = {
        "api_available": False,
        "api_configured": bool(DEEPSEEK_API_KEY),
        "embed_model": LOCAL_EMBED_MODEL,
        "embed_model_local": True,
        "chat_model": DEEPSEEK_CHAT_MODEL,
        "base_url": DEEPSEEK_BASE_URL,
        # Keep old keys for backwards compatibility
        "ollama_running": False,
        "embed_model_available": False,
        "chat_model_available": False,
    }

    # Check local embedding model
    try:
        model = get_embedding_model()
        status["embed_model_available"] = True
        status["embed_dimension"] = EMBEDDING_DIMENSION
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
        available_models = [m.id for m in models_response.data] if models_response.data else []
        status["available_models"] = available_models

        # Check if our chat model is available
        status["chat_model_available"] = DEEPSEEK_CHAT_MODEL in available_models or "deepseek" in DEEPSEEK_CHAT_MODEL

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
                        "description": "Search query - can be customer name, ID, contact name, email, or any keyword"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
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
                        "description": "The customer ID (e.g., 'CUST001' or 'ABC123')"
                    }
                },
                "required": ["customer_id"]
            }
        }
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
                        "description": "Search query - can be work order number, customer ID, status, or keyword"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by return status (optional)",
                        "enum": ["In", "Out", "Pending", "Complete"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
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
                        "description": "The work order number (e.g., 'WO001' or '12345')"
                    }
                },
                "required": ["work_order_no"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_work_orders",
            "description": "Get all work orders for a specific customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of work orders to return (default 20)",
                        "default": 20
                    }
                },
                "required": ["customer_id"]
            }
        }
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
                        "description": "Search query - can be item description, material, color, etc."
                    },
                    "material": {
                        "type": "string",
                        "description": "Filter by material type (optional)"
                    },
                    "color": {
                        "type": "string",
                        "description": "Filter by color (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
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
                        "description": "Optional: filter stats by customer ID"
                    }
                },
                "required": []
            }
        }
    }
]


# ============================================================================
# Tool Implementation Functions
# ============================================================================

def tool_search_customers(query: str, limit: int = 5) -> Dict:
    """Search customers by query text."""
    query_lower = query.lower()

    # Search in database
    customers = Customer.query.filter(
        db.or_(
            Customer.CustID.ilike(f"%{query}%"),
            Customer.Name.ilike(f"%{query}%"),
            Customer.Contact.ilike(f"%{query}%"),
            Customer.Email.ilike(f"%{query}%"),
        )
    ).limit(limit).all()

    results = []
    for c in customers:
        results.append({
            "customer_id": c.CustID,
            "name": c.Name,
            "contact": c.Contact,
            "phone": c.get_primary_phone(),
            "email": c.clean_email(),
            "address": c.get_full_address(),
        })

    return {
        "query": query,
        "count": len(results),
        "customers": results
    }


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
            {"work_order_no": wo.WorkOrderNo, "name": wo.WOName, "status": wo.ReturnStatus}
            for wo in work_orders[:5]
        ]
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
        results.append({
            "work_order_no": wo.WorkOrderNo,
            "name": wo.WOName,
            "customer_id": wo.CustID,
            "status": wo.ReturnStatus,
            "rack_location": wo.RackNo,
            "special_instructions": wo.SpecialInstructions[:100] if wo.SpecialInstructions else None,
        })

    return {
        "query": query,
        "status_filter": status,
        "count": len(results),
        "work_orders": results
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

    return {
        "work_order_no": wo.WorkOrderNo,
        "name": wo.WOName,
        "customer": {
            "id": wo.CustID,
            "name": customer.Name if customer else None,
        },
        "status": wo.ReturnStatus,
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
        ]
    }


def tool_get_customer_work_orders(customer_id: str, limit: int = 20) -> Dict:
    """Get all work orders for a customer."""
    customer = Customer.query.get(customer_id)

    if not customer:
        return {"error": f"Customer '{customer_id}' not found"}

    work_orders = WorkOrder.query.filter_by(CustID=customer_id).limit(limit).all()

    return {
        "customer_id": customer_id,
        "customer_name": customer.Name,
        "count": len(work_orders),
        "work_orders": [
            {
                "work_order_no": wo.WorkOrderNo,
                "name": wo.WOName,
                "status": wo.ReturnStatus,
                "rack_location": wo.RackNo,
            }
            for wo in work_orders
        ]
    }


def tool_search_items(query: str, material: str = None, color: str = None, limit: int = 10) -> Dict:
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
        results.append({
            "id": item.id,
            "work_order_no": item.WorkOrderNo,
            "description": item.Description,
            "material": item.Material,
            "color": item.Color,
            "condition": item.Condition,
            "quantity": item.Qty,
        })

    return {
        "query": query,
        "material_filter": material,
        "color_filter": color,
        "count": len(results),
        "items": results
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
            total_items += WorkOrderItem.query.filter_by(WorkOrderNo=wo.WorkOrderNo).count()
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
    max_tool_calls: int = 5
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
    system_prompt = """You are a helpful assistant for the Awning Management System.
You help users with questions about customers, work orders, items, and general operations.

You have access to tools that can search and retrieve data from the database.
Use these tools to answer user questions accurately. When you need specific data,
call the appropriate tool rather than guessing.

Be concise and helpful. When referencing records, include their IDs.
If a search returns no results, let the user know and suggest alternatives."""

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
            temperature=0.7,
            max_tokens=2048,
        )

        assistant_message = response.choices[0].message

        # Check if we need to call tools
        if assistant_message.tool_calls:
            # Add assistant message to conversation
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = execute_tool(tool_name, arguments)
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result_preview": result[:200] + "..." if len(result) > 200 else result
                })

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            # No more tool calls, return the response
            response_text = assistant_message.content or ""
            metadata = {
                "model": DEEPSEEK_CHAT_MODEL,
                "tool_calls": tool_calls_made,
                "tool_calls_count": len(tool_calls_made),
                "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                "completion_tokens": response.usage.completion_tokens if response.usage else None,
                "total_tokens": response.usage.total_tokens if response.usage else None,
            }
            return response_text, metadata

    # Max tool calls reached, return last response
    response_text = assistant_message.content or "I've gathered some information but reached the limit of queries I can make. Please try a more specific question."
    metadata = {
        "model": DEEPSEEK_CHAT_MODEL,
        "tool_calls": tool_calls_made,
        "tool_calls_count": len(tool_calls_made),
        "max_calls_reached": True,
    }
    return response_text, metadata
