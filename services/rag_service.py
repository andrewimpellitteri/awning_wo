"""
RAG (Retrieval-Augmented Generation) Service for the Awning Management chatbot.

This service provides:
- Embedding generation using Ollama
- Semantic search over customers, work orders, and items
- Chat completion with context-aware responses
"""
import os
import json
import requests
from typing import List, Dict, Optional, Tuple
import numpy as np
from extensions import db
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem

# Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2")
EMBEDDING_DIMENSION = 768  # nomic-embed-text dimension


class OllamaError(Exception):
    """Exception raised when Ollama API calls fail."""
    pass


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using Ollama.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding vector

    Raises:
        OllamaError: If the API call fails
    """
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": OLLAMA_EMBED_MODEL,
                "prompt": text
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Failed to generate embedding: {str(e)}")


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    embeddings = []
    for text in texts:
        try:
            embedding = get_embedding(text)
            embeddings.append(embedding)
        except OllamaError:
            # Return empty embedding on error
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
    Generate a chat completion using Ollama with optional RAG context.

    Args:
        messages: List of message dicts with 'role' and 'content'
        context: Retrieved context to include
        system_prompt: Optional custom system prompt

    Returns:
        Tuple of (response_text, metadata)

    Raises:
        OllamaError: If the API call fails
    """
    default_system = """You are a helpful assistant for the Awning Management System.
You help users with questions about customers, work orders, items, and general operations.
Be concise and helpful. If you reference specific records, mention their IDs.
If you don't have enough information to answer, say so clearly."""

    system = system_prompt or default_system

    # Add context to system prompt if available
    if context:
        system += f"\n\nHere is relevant information from the database:\n{context}"

    # Build messages for Ollama
    ollama_messages = [{"role": "system", "content": system}]
    ollama_messages.extend(messages)

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_CHAT_MODEL,
                "messages": ollama_messages,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()

        response_text = data.get("message", {}).get("content", "")
        metadata = {
            "model": OLLAMA_CHAT_MODEL,
            "context_provided": bool(context),
            "total_duration": data.get("total_duration"),
            "eval_count": data.get("eval_count"),
        }

        return response_text, metadata

    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Failed to get chat completion: {str(e)}")


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
    Check if Ollama is running and the required models are available.

    Returns:
        Dictionary with status information
    """
    status = {
        "ollama_running": False,
        "embed_model_available": False,
        "chat_model_available": False,
        "base_url": OLLAMA_BASE_URL,
        "embed_model": OLLAMA_EMBED_MODEL,
        "chat_model": OLLAMA_CHAT_MODEL,
    }

    try:
        # Check if Ollama is running
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        response.raise_for_status()
        status["ollama_running"] = True

        # Check available models
        models = response.json().get("models", [])
        model_names = [m.get("name", "").split(":")[0] for m in models]

        status["embed_model_available"] = OLLAMA_EMBED_MODEL.split(":")[0] in model_names
        status["chat_model_available"] = OLLAMA_CHAT_MODEL.split(":")[0] in model_names
        status["available_models"] = model_names

    except requests.exceptions.RequestException as e:
        status["error"] = str(e)

    return status
