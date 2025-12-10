"""
Chatbot routes for the RAG-enhanced AI assistant.

Provides API endpoints for:
- Chat sessions management
- Message handling
- Embedding sync operations
- Ollama status checking
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db, limiter
from models.chat import ChatSession, ChatMessage
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding
from services.rag_service import (
    chat_with_rag,
    search_all,
    sync_all_embeddings,
    sync_customer_embedding,
    sync_work_order_embedding,
    sync_item_embedding,
    check_ollama_status,
    OllamaError
)
from decorators import role_required

# Create blueprint
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chat")


# ============================================================================
# Chat Session Endpoints
# ============================================================================

@chatbot_bp.route("/sessions", methods=["GET"])
@login_required
def list_sessions():
    """List chat sessions for the current user."""
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)

    sessions = (
        ChatSession.query
        .filter_by(user_id=current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    total = ChatSession.query.filter_by(user_id=current_user.id).count()

    return jsonify({
        "sessions": [s.to_dict() for s in sessions],
        "total": total,
        "limit": limit,
        "offset": offset
    })


@chatbot_bp.route("/sessions", methods=["POST"])
@login_required
def create_session():
    """Create a new chat session."""
    data = request.get_json() or {}

    session = ChatSession(
        user_id=current_user.id,
        title=data.get("title"),
        work_order_no=data.get("work_order_no"),
        customer_id=data.get("customer_id")
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        "success": True,
        "session": session.to_dict()
    }), 201


@chatbot_bp.route("/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    """Get a chat session with its messages."""
    session = ChatSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "session": session.to_dict(include_messages=True)
    })


@chatbot_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@login_required
def delete_session(session_id):
    """Delete a chat session."""
    session = ChatSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    db.session.delete(session)
    db.session.commit()

    return jsonify({"success": True})


# ============================================================================
# Chat Message Endpoints
# ============================================================================

@chatbot_bp.route("/sessions/<int:session_id>/messages", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def send_message(session_id):
    """
    Send a message and get an AI response.

    Request body:
        message: str - The user's message
        work_order_context: str (optional) - Work order to focus on
        customer_context: str (optional) - Customer to focus on

    Response:
        user_message: The saved user message
        assistant_message: The AI response
    """
    session = ChatSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required"}), 400

    user_content = data["message"].strip()
    if not user_content:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Get conversation history
    history_messages = ChatMessage.query.filter_by(
        session_id=session_id
    ).order_by(ChatMessage.created_at).limit(20).all()

    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages
    ]

    # Save user message
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_content
    )
    db.session.add(user_message)

    try:
        # Get AI response with RAG
        response_text, metadata = chat_with_rag(
            user_message=user_content,
            conversation_history=conversation_history,
            work_order_context=data.get("work_order_context") or session.work_order_no,
            customer_context=data.get("customer_context") or session.customer_id
        )

        # Save assistant message
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=response_text,
            metadata=metadata
        )
        db.session.add(assistant_message)

        # Update session title if this is the first message
        if not session.title and len(conversation_history) == 0:
            # Use first 50 chars of user message as title
            session.title = user_content[:50] + ("..." if len(user_content) > 50 else "")

        db.session.commit()

        return jsonify({
            "success": True,
            "user_message": user_message.to_dict(),
            "assistant_message": assistant_message.to_dict()
        })

    except OllamaError as e:
        db.session.rollback()
        return jsonify({
            "error": f"AI service unavailable: {str(e)}",
            "hint": "Make sure Ollama is running with the required models"
        }), 503


@chatbot_bp.route("/quick", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def quick_chat():
    """
    Quick chat endpoint without session management.
    Useful for one-off questions.

    Request body:
        message: str - The user's message
        work_order_context: str (optional)
        customer_context: str (optional)

    Response:
        response: The AI response text
        metadata: Response metadata including sources
    """
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required"}), 400

    user_content = data["message"].strip()
    if not user_content:
        return jsonify({"error": "Message cannot be empty"}), 400

    try:
        response_text, metadata = chat_with_rag(
            user_message=user_content,
            work_order_context=data.get("work_order_context"),
            customer_context=data.get("customer_context")
        )

        return jsonify({
            "success": True,
            "response": response_text,
            "metadata": metadata
        })

    except OllamaError as e:
        return jsonify({
            "error": f"AI service unavailable: {str(e)}",
            "hint": "Make sure Ollama is running with the required models"
        }), 503


# ============================================================================
# Search Endpoint
# ============================================================================

@chatbot_bp.route("/search", methods=["POST"])
@login_required
def semantic_search():
    """
    Perform semantic search across embeddings.

    Request body:
        query: str - The search query
        limit_per_type: int (optional) - Max results per type (default 5)

    Response:
        results: Search results grouped by type
    """
    data = request.get_json()
    if not data or not data.get("query"):
        return jsonify({"error": "Query is required"}), 400

    limit = data.get("limit_per_type", 5)
    results = search_all(data["query"], limit_per_type=limit)

    if "error" in results:
        return jsonify({
            "error": results["error"],
            "hint": "Make sure Ollama is running"
        }), 503

    return jsonify({
        "success": True,
        "results": results
    })


# ============================================================================
# Admin Endpoints (Embedding Management)
# ============================================================================

@chatbot_bp.route("/status", methods=["GET"])
@login_required
def get_status():
    """Get chatbot and Ollama status."""
    ollama_status = check_ollama_status()

    # Get embedding counts
    embedding_counts = {
        "customers": CustomerEmbedding.query.count(),
        "work_orders": WorkOrderEmbedding.query.count(),
        "items": ItemEmbedding.query.count(),
    }

    return jsonify({
        "ollama": ollama_status,
        "embeddings": embedding_counts
    })


@chatbot_bp.route("/embeddings/sync", methods=["POST"])
@login_required
@role_required("admin")
def sync_embeddings():
    """
    Sync all embeddings (admin only).
    This is a long-running operation.

    Request body:
        type: str (optional) - "customers", "work_orders", "items", or "all"
    """
    data = request.get_json() or {}
    sync_type = data.get("type", "all")

    # Check Ollama status first
    status = check_ollama_status()
    if not status["ollama_running"]:
        return jsonify({
            "error": "Ollama is not running",
            "hint": f"Start Ollama at {status['base_url']}"
        }), 503

    if not status["embed_model_available"]:
        return jsonify({
            "error": f"Embedding model '{status['embed_model']}' not available",
            "hint": f"Run: ollama pull {status['embed_model']}"
        }), 503

    try:
        if sync_type == "all":
            stats = sync_all_embeddings()
        else:
            # Sync specific type
            stats = {"synced": 0, "failed": 0}
            if sync_type == "customers":
                from models.customer import Customer
                for customer in Customer.query.all():
                    if sync_customer_embedding(customer.CustID):
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
            elif sync_type == "work_orders":
                from models.work_order import WorkOrder
                for wo in WorkOrder.query.all():
                    if sync_work_order_embedding(wo.WorkOrderNo):
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
            elif sync_type == "items":
                from models.work_order import WorkOrderItem
                for item in WorkOrderItem.query.all():
                    if sync_item_embedding(item.id):
                        stats["synced"] += 1
                    else:
                        stats["failed"] += 1
            else:
                return jsonify({"error": f"Unknown sync type: {sync_type}"}), 400

        return jsonify({
            "success": True,
            "stats": stats
        })

    except Exception as e:
        return jsonify({
            "error": f"Sync failed: {str(e)}"
        }), 500


@chatbot_bp.route("/embeddings/sync/single", methods=["POST"])
@login_required
def sync_single_embedding():
    """
    Sync embedding for a single record.
    Useful for keeping embeddings up-to-date after edits.

    Request body:
        type: str - "customer", "work_order", or "item"
        id: str - The record ID
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    record_type = data.get("type")
    record_id = data.get("id")

    if not record_type or not record_id:
        return jsonify({"error": "Both 'type' and 'id' are required"}), 400

    try:
        if record_type == "customer":
            success = sync_customer_embedding(record_id)
        elif record_type == "work_order":
            success = sync_work_order_embedding(record_id)
        elif record_type == "item":
            success = sync_item_embedding(int(record_id))
        else:
            return jsonify({"error": f"Unknown type: {record_type}"}), 400

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to sync embedding"}), 500

    except OllamaError as e:
        return jsonify({
            "error": f"Ollama error: {str(e)}",
            "hint": "Make sure Ollama is running"
        }), 503
