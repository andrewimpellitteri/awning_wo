"""
Tests for RAG chatbot functionality.

Tests the chat session management, message handling, and embedding sync
without requiring actual Ollama to be running.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from extensions import db
from models.chat import ChatSession, ChatMessage
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.user import User

# Skip tests that require pgvector when using SQLite
requires_postgres = pytest.mark.skipif(
    "sqlite" in os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite").lower(),
    reason="Test requires PostgreSQL with pgvector extension (not supported in SQLite)"
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI API for embeddings."""
    with patch('services.rag_service.get_openai_client') as mock_client_getter:
        mock_client = MagicMock()

        # Mock embeddings.create() response
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536)  # text-embedding-3-small is 1536 dimensions
        ]
        mock_client.embeddings.create.return_value = mock_response

        mock_client_getter.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_deepseek_client():
    """Mock DeepSeek API client for chat."""
    with patch('services.rag_service.get_deepseek_client') as mock_client_getter:
        mock_client = MagicMock()

        # Mock models.list() for health checks
        mock_models_response = MagicMock()
        mock_models_response.data = [
            MagicMock(id="deepseek-chat"),
            MagicMock(id="deepseek-coder")
        ]
        mock_client.models.list.return_value = mock_models_response

        # Mock chat completions
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(
                    content="This is a test response from the AI assistant.",
                    tool_calls=None
                )
            )
        ]
        mock_completion.usage = MagicMock(
            prompt_tokens=50,
            completion_tokens=30,
            total_tokens=80
        )
        mock_client.chat.completions.create.return_value = mock_completion

        mock_client_getter.return_value = mock_client
        yield mock_client


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        from werkzeug.security import generate_password_hash

        user = User(
            username="testuser",
            email="test@example.com",
            role="admin",
            password_hash=generate_password_hash("testpass123")
        )
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def authenticated_client(client, test_user, app):
    """Client with authenticated user session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def sample_customer_data(app):
    """Create sample customer in database."""
    with app.app_context():
        customer = Customer(
            CustID="CUST001",
            Name="Test Customer LLC",
            Contact="John Doe",
            Address="123 Test Street",
            City="Test City",
            State="TS",
            ZipCode="12345",
            EmailAddress="test@example.com",
            Source="TEST_SOURCE"
        )
        db.session.add(customer)
        db.session.commit()
        yield customer


@pytest.fixture
def sample_work_order_data(app, sample_customer_data):
    """Create sample work order in database."""
    with app.app_context():
        wo = WorkOrder(
            WorkOrderNo="WO001",
            CustID="CUST001",
            WOName="Test Awning Work",
            SpecialInstructions="Handle with care",
            ReturnStatus="Pending"
        )
        db.session.add(wo)
        db.session.commit()
        yield wo


# =============================================================================
# Model Tests
# =============================================================================

class TestChatModels:
    """Tests for chat-related database models."""

    def test_create_chat_session(self, app, test_user):
        """Test creating a new chat session."""
        with app.app_context():
            session = ChatSession(
                user_id=test_user.id,
                title="Test Conversation"
            )
            db.session.add(session)
            db.session.commit()

            assert session.id is not None
            assert session.user_id == test_user.id
            assert session.title == "Test Conversation"
            assert session.created_at is not None

    def test_chat_session_to_dict(self, app, test_user):
        """Test chat session serialization."""
        with app.app_context():
            session = ChatSession(
                user_id=test_user.id,
                title="Test Conversation",
                work_order_no="WO001",
                customer_id="CUST001"
            )
            db.session.add(session)
            db.session.commit()

            data = session.to_dict()

            assert data["id"] == session.id
            assert data["title"] == "Test Conversation"
            assert data["work_order_no"] == "WO001"
            assert data["customer_id"] == "CUST001"

    def test_create_chat_message(self, app, test_user):
        """Test creating a chat message."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()

            message = ChatMessage(
                session_id=session.id,
                role="user",
                content="Hello, AI assistant!"
            )
            db.session.add(message)
            db.session.commit()

            assert message.id is not None
            assert message.role == "user"
            assert message.content == "Hello, AI assistant!"

    def test_chat_message_with_metadata(self, app, test_user):
        """Test chat message with metadata."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()

            metadata = {
                "model": "llama3.2",
                "sources": {"customers": ["CUST001"]}
            }

            message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content="Here is the information...",
                message_metadata=metadata
            )
            db.session.add(message)
            db.session.commit()

            assert message.message_metadata == metadata
            assert message.message_metadata["model"] == "llama3.2"

    def test_session_message_relationship(self, app, test_user):
        """Test the relationship between sessions and messages."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()

            msg1 = ChatMessage(session_id=session.id, role="user", content="Hello")
            msg2 = ChatMessage(session_id=session.id, role="assistant", content="Hi there!")
            db.session.add_all([msg1, msg2])
            db.session.commit()

            # Refresh to get the relationship
            db.session.refresh(session)

            assert len(session.messages) == 2
            assert session.messages[0].content == "Hello"

    def test_cascade_delete_session(self, app, test_user):
        """Test that deleting a session cascades to messages."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            msg = ChatMessage(session_id=session.id, role="user", content="Test")
            db.session.add(msg)
            db.session.commit()
            msg_id = msg.id

            # Delete the session
            db.session.delete(session)
            db.session.commit()

            # Verify message was also deleted
            assert ChatMessage.query.get(msg_id) is None


class TestEmbeddingModels:
    """Tests for embedding-related database models."""

    def test_create_customer_embedding(self, app):
        """Test creating a customer embedding."""
        with app.app_context():
            embedding = CustomerEmbedding(
                customer_id="CUST001",
                content="Customer: Test Customer LLC",
                embedding=[0.1] * 1536
            )
            db.session.add(embedding)
            db.session.commit()

            assert embedding.id is not None
            assert len(embedding.embedding) == 1536

    def test_create_work_order_embedding(self, app):
        """Test creating a work order embedding."""
        with app.app_context():
            embedding = WorkOrderEmbedding(
                work_order_no="WO001",
                content="Work Order: WO001 - Test Awning",
                embedding=[0.2] * 1536
            )
            db.session.add(embedding)
            db.session.commit()

            assert embedding.id is not None
            assert embedding.work_order_no == "WO001"

    def test_create_item_embedding(self, app):
        """Test creating an item embedding."""
        with app.app_context():
            embedding = ItemEmbedding(
                item_id=1,
                content="Item: Canvas Awning",
                embedding=[0.3] * 1536
            )
            db.session.add(embedding)
            db.session.commit()

            assert embedding.id is not None
            assert embedding.item_id == 1

    def test_embedding_to_dict_excludes_embedding(self, app):
        """Test that to_dict doesn't include the embedding array."""
        with app.app_context():
            embedding = CustomerEmbedding(
                customer_id="CUST001",
                content="Test content",
                embedding=[0.1] * 1536
            )
            db.session.add(embedding)
            db.session.commit()

            data = embedding.to_dict()

            assert "embedding" not in data
            assert "content" in data
            assert data["customer_id"] == "CUST001"


# =============================================================================
# RAG Service Tests
# =============================================================================

class TestRAGService:
    """Tests for the RAG service functions."""

    def test_get_embedding(self, app, mock_openai_embeddings):
        """Test generating an embedding."""
        with app.app_context():
            from services.rag_service import get_embedding

            embedding = get_embedding("Test text")

            assert len(embedding) == 1536  # text-embedding-3-small dimension
            mock_openai_embeddings.embeddings.create.assert_called()

    def test_cosine_similarity(self, app):
        """Test cosine similarity calculation."""
        with app.app_context():
            from services.rag_service import cosine_similarity

            # Same vectors should have similarity of 1.0
            vec = [1.0, 0.0, 0.0]
            assert cosine_similarity(vec, vec) == pytest.approx(1.0)

            # Orthogonal vectors should have similarity of 0.0
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.0, 1.0, 0.0]
            assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

            # Empty vectors should return 0.0
            assert cosine_similarity([], []) == 0.0

    def test_create_customer_text(self, app, sample_customer_data):
        """Test customer text generation for embeddings."""
        with app.app_context():
            from services.rag_service import create_customer_text

            customer = Customer.query.get("CUST001")
            text = create_customer_text(customer)

            assert "CUST001" in text
            assert "Test Customer LLC" in text
            assert "Test City" in text

    def test_create_work_order_text(self, app, sample_work_order_data):
        """Test work order text generation for embeddings."""
        with app.app_context():
            from services.rag_service import create_work_order_text

            wo = WorkOrder.query.get("WO001")
            text = create_work_order_text(wo)

            assert "WO001" in text
            assert "Test Awning Work" in text
            assert "Handle with care" in text

    def test_check_deepseek_status(self, app, mock_deepseek_client, mock_openai_embeddings):
        """Test DeepSeek status check."""
        with app.app_context():
            from services.rag_service import check_deepseek_status

            status = check_deepseek_status()

            assert status["api_available"] is True
            assert status["embed_model_available"] is True
            assert status["chat_model_available"] is True

    def test_sync_customer_embedding(self, app, sample_customer_data, mock_openai_embeddings):
        """Test syncing a customer embedding."""
        with app.app_context():
            from services.rag_service import sync_customer_embedding

            success = sync_customer_embedding("CUST001")

            assert success is True

            # Verify embedding was created
            embedding = CustomerEmbedding.query.filter_by(customer_id="CUST001").first()
            assert embedding is not None
            assert "Test Customer LLC" in embedding.content

    def test_sync_work_order_embedding(self, app, sample_work_order_data, mock_openai_embeddings):
        """Test syncing a work order embedding."""
        with app.app_context():
            from services.rag_service import sync_work_order_embedding

            success = sync_work_order_embedding("WO001")

            assert success is True

            embedding = WorkOrderEmbedding.query.filter_by(work_order_no="WO001").first()
            assert embedding is not None

    @requires_postgres
    def test_chat_with_rag(self, app, mock_deepseek_client, mock_openai_embeddings):
        """Test chat completion with RAG."""
        with app.app_context():
            from services.rag_service import chat_with_rag

            response, metadata = chat_with_rag("Tell me about work orders")

            assert "test response" in response.lower() or len(response) > 0
            assert "model" in metadata
            assert "sources" in metadata


# =============================================================================
# Route Tests
# =============================================================================

class TestChatbotRoutes:
    """Tests for chatbot API routes."""

    def test_get_status_unauthenticated(self, client):
        """Test that unauthenticated users can't access status."""
        response = client.get("/api/chat/status")
        # Should redirect to login
        assert response.status_code in [302, 401]

    def test_get_status_authenticated(self, authenticated_client, mock_deepseek_client,
                                       mock_openai_embeddings, app):
        """Test status endpoint for authenticated users."""
        with app.app_context():
            response = authenticated_client.get("/api/chat/status")
            assert response.status_code == 200

            data = response.get_json()
            assert "ollama" in data  # Backwards compatible key
            assert "embeddings" in data

    def test_create_session(self, authenticated_client, app, test_user):
        """Test creating a chat session."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/sessions",
                json={"title": "Test Session"}
            )

            assert response.status_code == 201
            data = response.get_json()
            assert data["success"] is True
            assert data["session"]["title"] == "Test Session"

    def test_list_sessions(self, authenticated_client, app, test_user):
        """Test listing chat sessions."""
        with app.app_context():
            # Create some sessions first
            for i in range(3):
                session = ChatSession(user_id=test_user.id, title=f"Session {i}")
                db.session.add(session)
            db.session.commit()

            response = authenticated_client.get("/api/chat/sessions")

            assert response.status_code == 200
            data = response.get_json()
            assert len(data["sessions"]) == 3

    def test_get_session(self, authenticated_client, app, test_user):
        """Test getting a specific session."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id, title="Test")
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            response = authenticated_client.get(f"/api/chat/sessions/{session_id}")

            assert response.status_code == 200
            data = response.get_json()
            assert data["session"]["title"] == "Test"

    def test_get_nonexistent_session(self, authenticated_client, app):
        """Test getting a session that doesn't exist."""
        with app.app_context():
            response = authenticated_client.get("/api/chat/sessions/99999")
            assert response.status_code == 404

    def test_delete_session(self, authenticated_client, app, test_user):
        """Test deleting a chat session."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id, title="To Delete")
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            response = authenticated_client.delete(f"/api/chat/sessions/{session_id}")

            assert response.status_code == 200
            assert ChatSession.query.get(session_id) is None

    def test_send_message(self, authenticated_client, app, test_user, mock_deepseek_client,
                          mock_openai_embeddings):
        """Test sending a message to a session."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"message": "Hello, AI!"}
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["user_message"]["content"] == "Hello, AI!"
            assert "assistant_message" in data

    def test_send_empty_message(self, authenticated_client, app, test_user):
        """Test sending an empty message returns error."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"message": "  "}
            )

            assert response.status_code == 400

    def test_quick_chat(self, authenticated_client, app, mock_deepseek_client,
                        mock_openai_embeddings):
        """Test quick chat endpoint."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/quick",
                json={"message": "What's the status?"}
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "response" in data

    @requires_postgres
    def test_semantic_search(self, authenticated_client, app, mock_openai_embeddings):
        """Test semantic search endpoint."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/search",
                json={"query": "find awnings"}
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "results" in data

    def test_semantic_search_empty_query(self, authenticated_client, app):
        """Test semantic search with empty query."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/search",
                json={}
            )

            assert response.status_code == 400


# =============================================================================
# Integration Tests
# =============================================================================

class TestChatbotIntegration:
    """Integration tests for the chatbot functionality."""

    def test_full_conversation_flow(self, authenticated_client, app, test_user,
                                     mock_deepseek_client, mock_openai_embeddings):
        """Test a complete conversation flow."""
        with app.app_context():
            # 1. Create a session
            create_response = authenticated_client.post(
                "/api/chat/sessions",
                json={"title": "Integration Test"}
            )
            assert create_response.status_code == 201
            session_id = create_response.get_json()["session"]["id"]

            # 2. Send first message
            msg1_response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"message": "Hello!"}
            )
            assert msg1_response.status_code == 200

            # 3. Send follow-up message
            msg2_response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={"message": "Tell me about work orders"}
            )
            assert msg2_response.status_code == 200

            # 4. Verify session has all messages
            get_response = authenticated_client.get(f"/api/chat/sessions/{session_id}")
            session_data = get_response.get_json()["session"]
            assert session_data["message_count"] == 4  # 2 user + 2 assistant

            # 5. Clean up - delete session
            del_response = authenticated_client.delete(f"/api/chat/sessions/{session_id}")
            assert del_response.status_code == 200

    def test_session_with_context(self, authenticated_client, app, test_user,
                                   sample_work_order_data, mock_deepseek_client,
                                   mock_openai_embeddings):
        """Test session with work order context."""
        with app.app_context():
            # Create session with work order context
            response = authenticated_client.post(
                "/api/chat/sessions",
                json={
                    "title": "Context Test",
                    "work_order_no": "WO001"
                }
            )

            assert response.status_code == 201
            data = response.get_json()
            assert data["session"]["work_order_no"] == "WO001"
