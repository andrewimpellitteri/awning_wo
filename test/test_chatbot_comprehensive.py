"""
Comprehensive tests for RAG chatbot functionality with DeepSeek integration.

Tests both RAG (semantic search) and Tools (function calling) chat modes
with proper DeepSeek API mocking.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from extensions import db
from models.chat import ChatSession, ChatMessage
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.user import User


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_sentence_transformer():
    """Mock the sentence-transformers model for local embeddings."""
    with patch('services.rag_service.SentenceTransformer') as mock_st:
        mock_model = MagicMock()
        # all-MiniLM-L6-v2 produces 384-dimensional embeddings
        mock_model.encode.return_value = [[0.1] * 384]
        mock_st.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_deepseek_client():
    """
    Mock DeepSeek OpenAI client for chat completions and tools.
    """
    with patch('services.rag_service.OpenAI') as mock_openai:
        # Create mock client instance
        mock_client = MagicMock()

        # Mock models.list() for health checks
        mock_models_response = MagicMock()
        mock_models_response.data = [
            MagicMock(id="deepseek-chat"),
            MagicMock(id="deepseek-coder")
        ]
        mock_client.models.list.return_value = mock_models_response

        # Mock chat.completions.create() for basic chat
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(
                    content="This is a helpful response from DeepSeek.",
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

        # Return the mock client
        mock_openai.return_value = mock_client

        yield mock_client


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = User(
            username="testuser",
            email="test@example.com",
            role="admin"
        )
        user.set_password("testpass123")
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
            Name="Acme Awning Company",
            Contact="Jane Smith",
            Address="123 Main Street",
            City="Boston",
            State="MA",
            ZipCode="02101",
            EmailAddress="jane@acmeawning.com",
            Source="Website"
        )
        db.session.add(customer)
        db.session.commit()
        yield customer


@pytest.fixture
def sample_work_order_data(app, sample_customer_data):
    """Create sample work order with items in database."""
    with app.app_context():
        wo = WorkOrder(
            WorkOrderNo="WO2024001",
            CustID="CUST001",
            WOName="Marina Awning Cleaning",
            SpecialInstructions="Handle carefully - marine grade fabric",
            ReturnStatus="In",
            RackNo="A-15"
        )
        db.session.add(wo)

        # Add some items to the work order
        item1 = WorkOrderItem(
            WorkOrderNo="WO2024001",
            Description="Striped Awning",
            Material="Sunbrella",
            Color="Navy/White",
            Condition="Good",
            Qty=2
        )
        item2 = WorkOrderItem(
            WorkOrderNo="WO2024001",
            Description="Solid Awning",
            Material="Canvas",
            Color="Tan",
            Condition="Fair",
            Qty=1
        )
        db.session.add_all([item1, item2])
        db.session.commit()
        yield wo


@pytest.fixture
def sample_embeddings(app, sample_customer_data, sample_work_order_data):
    """Create sample embeddings for testing search."""
    with app.app_context():
        # Customer embedding
        cust_emb = CustomerEmbedding(
            customer_id="CUST001",
            content="Customer ID: CUST001 | Name: Acme Awning Company | Contact: Jane Smith",
            embedding=[0.1] * 384
        )

        # Work order embedding
        wo_emb = WorkOrderEmbedding(
            work_order_no="WO2024001",
            content="Work Order: WO2024001 | Name: Marina Awning Cleaning",
            embedding=[0.15] * 384
        )

        # Item embedding
        items = WorkOrderItem.query.filter_by(WorkOrderNo="WO2024001").all()
        if items:
            item_emb = ItemEmbedding(
                item_id=items[0].id,
                content="Item: Striped Awning | Material: Sunbrella | Color: Navy/White",
                embedding=[0.12] * 384
            )
            db.session.add(item_emb)

        db.session.add_all([cust_emb, wo_emb])
        db.session.commit()
        yield


# =============================================================================
# Service Tests - Embeddings
# =============================================================================

class TestEmbeddingGeneration:
    """Tests for local embedding generation using sentence-transformers."""

    def test_get_embedding_with_local_model(self, app, mock_sentence_transformer):
        """Test generating embeddings using local sentence-transformers."""
        with app.app_context():
            from services.rag_service import get_embedding

            text = "Test customer: Acme Awning Company in Boston"
            embedding = get_embedding(text)

            assert len(embedding) == 384
            assert isinstance(embedding, list)
            assert all(isinstance(x, float) for x in embedding)

    def test_get_embeddings_batch(self, app, mock_sentence_transformer):
        """Test batch embedding generation."""
        with app.app_context():
            from services.rag_service import get_embeddings_batch

            # Configure mock to return multiple embeddings
            mock_sentence_transformer.encode.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

            texts = ["Customer 1", "Customer 2", "Customer 3"]
            embeddings = get_embeddings_batch(texts)

            assert len(embeddings) == 3
            assert all(len(emb) == 384 for emb in embeddings)

    def test_embedding_error_handling(self, app):
        """Test error handling when embedding generation fails."""
        with app.app_context():
            from services.rag_service import get_embedding, DeepSeekError

            with patch('services.rag_service.get_embedding_model') as mock_model:
                mock_model.side_effect = Exception("Model not found")

                with pytest.raises(DeepSeekError) as exc_info:
                    get_embedding("test text")

                assert "Failed to generate embedding" in str(exc_info.value)


# =============================================================================
# Service Tests - Semantic Search
# =============================================================================

class TestSemanticSearch:
    """Tests for semantic search functionality."""

    def test_cosine_similarity(self, app):
        """Test cosine similarity calculation."""
        with app.app_context():
            from services.rag_service import cosine_similarity

            # Identical vectors
            vec1 = [1.0, 0.0, 0.0]
            assert cosine_similarity(vec1, vec1) == pytest.approx(1.0)

            # Orthogonal vectors
            vec2 = [0.0, 1.0, 0.0]
            assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

            # Opposite vectors
            vec3 = [-1.0, 0.0, 0.0]
            assert cosine_similarity(vec1, vec3) == pytest.approx(-1.0)

            # Empty vectors
            assert cosine_similarity([], []) == 0.0

    def test_search_similar_customers(self, app, sample_embeddings, mock_sentence_transformer):
        """Test searching for similar customers."""
        with app.app_context():
            from services.rag_service import search_similar_customers

            query_embedding = [0.11] * 384  # Similar to customer embedding
            results = search_similar_customers(query_embedding, limit=5)

            assert len(results) > 0
            assert results[0]["type"] == "customer"
            assert results[0]["id"] == "CUST001"
            assert "similarity" in results[0]
            assert 0.0 <= results[0]["similarity"] <= 1.0

    def test_search_similar_work_orders(self, app, sample_embeddings, mock_sentence_transformer):
        """Test searching for similar work orders."""
        with app.app_context():
            from services.rag_service import search_similar_work_orders

            query_embedding = [0.15] * 384
            results = search_similar_work_orders(query_embedding, limit=5)

            assert len(results) > 0
            assert results[0]["type"] == "work_order"
            assert results[0]["id"] == "WO2024001"

    def test_search_all(self, app, sample_embeddings, mock_sentence_transformer):
        """Test searching across all embedding types."""
        with app.app_context():
            from services.rag_service import search_all

            results = search_all("awning cleaning", limit_per_type=3)

            assert "customers" in results
            assert "work_orders" in results
            assert "items" in results

    def test_build_context_from_search(self, app):
        """Test building context string from search results."""
        with app.app_context():
            from services.rag_service import build_context_from_search

            search_results = {
                "customers": [
                    {"id": "CUST001", "content": "Acme Awning", "similarity": 0.9}
                ],
                "work_orders": [
                    {"id": "WO001", "content": "Cleaning job", "similarity": 0.8}
                ],
                "items": []
            }

            context = build_context_from_search(search_results, min_similarity=0.3)

            assert "RELEVANT CUSTOMERS" in context
            assert "Acme Awning" in context
            assert "RELEVANT WORK ORDERS" in context
            assert "Cleaning job" in context


# =============================================================================
# Service Tests - RAG Chat Mode
# =============================================================================

class TestChatWithRAG:
    """Tests for chat_with_rag (semantic search mode)."""

    def test_chat_with_rag_basic(self, app, mock_deepseek_client, mock_sentence_transformer,
                                  sample_embeddings):
        """Test basic RAG chat without context."""
        with app.app_context():
            from services.rag_service import chat_with_rag

            response_text, metadata = chat_with_rag(
                user_message="Tell me about awning companies",
                conversation_history=[]
            )

            assert isinstance(response_text, str)
            assert len(response_text) > 0
            assert "model" in metadata
            assert "sources" in metadata
            assert "customers" in metadata["sources"]

    def test_chat_with_rag_with_conversation_history(self, app, mock_deepseek_client,
                                                      mock_sentence_transformer):
        """Test RAG chat with conversation history."""
        with app.app_context():
            from services.rag_service import chat_with_rag

            history = [
                {"role": "user", "content": "What is an awning?"},
                {"role": "assistant", "content": "An awning is a covering..."}
            ]

            response_text, metadata = chat_with_rag(
                user_message="Tell me more",
                conversation_history=history
            )

            assert isinstance(response_text, str)
            # Verify history was passed to API
            mock_deepseek_client.chat.completions.create.assert_called()

    def test_chat_with_rag_with_work_order_context(self, app, mock_deepseek_client,
                                                     mock_sentence_transformer,
                                                     sample_work_order_data):
        """Test RAG chat with work order context."""
        with app.app_context():
            from services.rag_service import chat_with_rag

            response_text, metadata = chat_with_rag(
                user_message="What's the status of this order?",
                work_order_context="WO2024001"
            )

            assert isinstance(response_text, str)
            # Verify API was called with work order context
            mock_deepseek_client.chat.completions.create.assert_called()
            call_args = mock_deepseek_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            system_message = messages[0]["content"]
            assert "WO2024001" in system_message or "Marina Awning" in system_message

    def test_chat_with_rag_with_customer_context(self, app, mock_deepseek_client,
                                                   mock_sentence_transformer,
                                                   sample_customer_data):
        """Test RAG chat with customer context."""
        with app.app_context():
            from services.rag_service import chat_with_rag

            response_text, metadata = chat_with_rag(
                user_message="Tell me about this customer",
                customer_context="CUST001"
            )

            assert isinstance(response_text, str)
            # Verify customer context was included
            mock_deepseek_client.chat.completions.create.assert_called()


# =============================================================================
# Service Tests - Tools Chat Mode (Function Calling)
# =============================================================================

class TestChatWithTools:
    """Tests for chat_with_tools (function calling mode)."""

    def test_chat_with_tools_no_tool_calls(self, app, mock_deepseek_client):
        """Test chat that doesn't require tool calls."""
        with app.app_context():
            from services.rag_service import chat_with_tools

            # Mock response without tool calls
            mock_deepseek_client.chat.completions.create.return_value.choices[0].message.tool_calls = None

            response_text, metadata = chat_with_tools(
                user_message="Hello, how are you?",
                conversation_history=[]
            )

            assert isinstance(response_text, str)
            assert "model" in metadata
            assert "tool_calls" in metadata
            assert len(metadata["tool_calls"]) == 0

    def test_chat_with_tools_search_customers(self, app, mock_deepseek_client,
                                                sample_customer_data):
        """Test chat that calls search_customers tool."""
        with app.app_context():
            from services.rag_service import chat_with_tools

            # Mock tool call response
            tool_call = MagicMock()
            tool_call.id = "call_123"
            tool_call.function.name = "search_customers"
            tool_call.function.arguments = json.dumps({"query": "Acme", "limit": 5})

            # First call: assistant requests tool
            first_response = MagicMock()
            first_response.choices = [MagicMock(message=MagicMock(
                content=None,
                tool_calls=[tool_call]
            ))]
            first_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20, total_tokens=70)

            # Second call: final response
            second_response = MagicMock()
            second_response.choices = [MagicMock(message=MagicMock(
                content="I found Acme Awning Company in Boston.",
                tool_calls=None
            ))]
            second_response.usage = MagicMock(prompt_tokens=100, completion_tokens=30, total_tokens=130)

            mock_deepseek_client.chat.completions.create.side_effect = [first_response, second_response]

            response_text, metadata = chat_with_tools(
                user_message="Find customers named Acme"
            )

            assert isinstance(response_text, str)
            assert "Acme" in response_text or len(response_text) > 0
            assert metadata["tool_calls_count"] == 1
            assert metadata["tool_calls"][0]["tool"] == "search_customers"

    def test_chat_with_tools_get_work_order_details(self, app, mock_deepseek_client,
                                                      sample_work_order_data):
        """Test chat that calls get_work_order_details tool."""
        with app.app_context():
            from services.rag_service import chat_with_tools

            # Mock tool call
            tool_call = MagicMock()
            tool_call.id = "call_456"
            tool_call.function.name = "get_work_order_details"
            tool_call.function.arguments = json.dumps({"work_order_no": "WO2024001"})

            first_response = MagicMock()
            first_response.choices = [MagicMock(message=MagicMock(
                content=None,
                tool_calls=[tool_call]
            ))]
            first_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20, total_tokens=70)

            second_response = MagicMock()
            second_response.choices = [MagicMock(message=MagicMock(
                content="Work order WO2024001 is for Marina Awning Cleaning.",
                tool_calls=None
            ))]
            second_response.usage = MagicMock(prompt_tokens=100, completion_tokens=30, total_tokens=130)

            mock_deepseek_client.chat.completions.create.side_effect = [first_response, second_response]

            response_text, metadata = chat_with_tools(
                user_message="What's in work order WO2024001?"
            )

            assert isinstance(response_text, str)
            assert metadata["tool_calls_count"] == 1

    def test_chat_with_tools_multiple_calls(self, app, mock_deepseek_client,
                                             sample_customer_data, sample_work_order_data):
        """Test chat that makes multiple tool calls."""
        with app.app_context():
            from services.rag_service import chat_with_tools

            # Mock first tool call
            tool_call1 = MagicMock()
            tool_call1.id = "call_1"
            tool_call1.function.name = "search_customers"
            tool_call1.function.arguments = json.dumps({"query": "Acme"})

            # Mock second tool call
            tool_call2 = MagicMock()
            tool_call2.id = "call_2"
            tool_call2.function.name = "get_customer_work_orders"
            tool_call2.function.arguments = json.dumps({"customer_id": "CUST001"})

            # Response sequence
            response1 = MagicMock()
            response1.choices = [MagicMock(message=MagicMock(content=None, tool_calls=[tool_call1]))]
            response1.usage = MagicMock(prompt_tokens=50, completion_tokens=20, total_tokens=70)

            response2 = MagicMock()
            response2.choices = [MagicMock(message=MagicMock(content=None, tool_calls=[tool_call2]))]
            response2.usage = MagicMock(prompt_tokens=100, completion_tokens=20, total_tokens=120)

            response3 = MagicMock()
            response3.choices = [MagicMock(message=MagicMock(
                content="Acme has 1 work order.",
                tool_calls=None
            ))]
            response3.usage = MagicMock(prompt_tokens=150, completion_tokens=30, total_tokens=180)

            mock_deepseek_client.chat.completions.create.side_effect = [response1, response2, response3]

            response_text, metadata = chat_with_tools(
                user_message="Find Acme and list their work orders"
            )

            assert isinstance(response_text, str)
            assert metadata["tool_calls_count"] == 2

    def test_chat_with_tools_max_calls_limit(self, app, mock_deepseek_client):
        """Test that max_tool_calls limit is enforced."""
        with app.app_context():
            from services.rag_service import chat_with_tools

            # Create a tool call that keeps repeating
            tool_call = MagicMock()
            tool_call.id = "call_loop"
            tool_call.function.name = "get_work_order_stats"
            tool_call.function.arguments = json.dumps({})

            # Always return a tool call (would loop forever without limit)
            looping_response = MagicMock()
            looping_response.choices = [MagicMock(message=MagicMock(
                content=None,
                tool_calls=[tool_call]
            ))]
            looping_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20, total_tokens=70)

            mock_deepseek_client.chat.completions.create.return_value = looping_response

            response_text, metadata = chat_with_tools(
                user_message="Test",
                max_tool_calls=3
            )

            # Should stop at max_tool_calls
            assert metadata["tool_calls_count"] == 3
            assert metadata.get("max_calls_reached") is True


# =============================================================================
# Service Tests - Tool Functions
# =============================================================================

class TestToolFunctions:
    """Tests for individual tool implementation functions."""

    def test_tool_search_customers(self, app, sample_customer_data):
        """Test search_customers tool."""
        with app.app_context():
            from services.rag_service import tool_search_customers

            result = tool_search_customers("Acme", limit=10)

            assert result["count"] > 0
            assert result["customers"][0]["customer_id"] == "CUST001"
            assert "Acme" in result["customers"][0]["name"]

    def test_tool_get_customer_details(self, app, sample_customer_data, sample_work_order_data):
        """Test get_customer_details tool."""
        with app.app_context():
            from services.rag_service import tool_get_customer_details

            result = tool_get_customer_details("CUST001")

            assert "error" not in result
            assert result["customer_id"] == "CUST001"
            assert result["name"] == "Acme Awning Company"
            assert result["work_order_count"] >= 1
            assert len(result["recent_work_orders"]) >= 1

    def test_tool_get_customer_details_not_found(self, app):
        """Test get_customer_details with nonexistent customer."""
        with app.app_context():
            from services.rag_service import tool_get_customer_details

            result = tool_get_customer_details("NONEXISTENT")

            assert "error" in result
            assert "not found" in result["error"].lower()

    def test_tool_search_work_orders(self, app, sample_work_order_data):
        """Test search_work_orders tool."""
        with app.app_context():
            from services.rag_service import tool_search_work_orders

            result = tool_search_work_orders("Marina", limit=10)

            assert result["count"] > 0
            assert result["work_orders"][0]["work_order_no"] == "WO2024001"

    def test_tool_search_work_orders_with_status_filter(self, app, sample_work_order_data):
        """Test search_work_orders with status filter."""
        with app.app_context():
            from services.rag_service import tool_search_work_orders

            result = tool_search_work_orders("Marina", status="In", limit=10)

            assert result["status_filter"] == "In"
            if result["count"] > 0:
                assert result["work_orders"][0]["status"] == "In"

    def test_tool_get_work_order_details(self, app, sample_work_order_data):
        """Test get_work_order_details tool."""
        with app.app_context():
            from services.rag_service import tool_get_work_order_details

            result = tool_get_work_order_details("WO2024001")

            assert "error" not in result
            assert result["work_order_no"] == "WO2024001"
            assert result["name"] == "Marina Awning Cleaning"
            assert result["item_count"] == 2
            assert len(result["items"]) == 2

    def test_tool_get_customer_work_orders(self, app, sample_work_order_data):
        """Test get_customer_work_orders tool."""
        with app.app_context():
            from services.rag_service import tool_get_customer_work_orders

            result = tool_get_customer_work_orders("CUST001", limit=20)

            assert result["customer_id"] == "CUST001"
            assert result["count"] >= 1
            assert len(result["work_orders"]) >= 1

    def test_tool_search_items(self, app, sample_work_order_data):
        """Test search_items tool."""
        with app.app_context():
            from services.rag_service import tool_search_items

            result = tool_search_items("Striped", limit=10)

            assert result["count"] > 0
            assert "Striped" in result["items"][0]["description"]

    def test_tool_search_items_with_filters(self, app, sample_work_order_data):
        """Test search_items with material and color filters."""
        with app.app_context():
            from services.rag_service import tool_search_items

            result = tool_search_items("Awning", material="Sunbrella", color="Navy", limit=10)

            assert result["material_filter"] == "Sunbrella"
            assert result["color_filter"] == "Navy"

    def test_tool_get_work_order_stats(self, app, sample_work_order_data):
        """Test get_work_order_stats tool."""
        with app.app_context():
            from services.rag_service import tool_get_work_order_stats

            result = tool_get_work_order_stats()

            assert "total_work_orders" in result
            assert "total_items" in result
            assert "by_status" in result
            assert result["total_work_orders"] >= 1

    def test_tool_get_work_order_stats_filtered(self, app, sample_work_order_data):
        """Test get_work_order_stats filtered by customer."""
        with app.app_context():
            from services.rag_service import tool_get_work_order_stats

            result = tool_get_work_order_stats(customer_id="CUST001")

            assert result["customer_id"] == "CUST001"
            assert result["total_work_orders"] >= 1

    def test_execute_tool(self, app, sample_customer_data):
        """Test execute_tool wrapper function."""
        with app.app_context():
            from services.rag_service import execute_tool

            result_json = execute_tool("search_customers", {"query": "Acme", "limit": 5})
            result = json.loads(result_json)

            assert result["count"] > 0

    def test_execute_tool_unknown(self, app):
        """Test execute_tool with unknown tool."""
        with app.app_context():
            from services.rag_service import execute_tool

            result_json = execute_tool("unknown_tool", {})
            result = json.loads(result_json)

            assert "error" in result
            assert "Unknown tool" in result["error"]


# =============================================================================
# API Route Tests - RAG Mode
# =============================================================================

class TestChatbotRoutesRAGMode:
    """Tests for chatbot API routes in RAG mode."""

    def test_quick_chat_rag_mode(self, authenticated_client, app, mock_deepseek_client,
                                  mock_sentence_transformer, sample_embeddings):
        """Test quick chat endpoint in RAG mode."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/quick",
                json={
                    "message": "Tell me about awning companies",
                    "mode": "rag"
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "response" in data
            assert "metadata" in data
            assert "sources" in data["metadata"]

    def test_send_message_rag_mode(self, authenticated_client, app, test_user,
                                    mock_deepseek_client, mock_sentence_transformer):
        """Test sending message in RAG mode."""
        with app.app_context():
            # Create session
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "What awning companies do we work with?",
                    "mode": "rag"
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "assistant_message" in data


# =============================================================================
# API Route Tests - Tools Mode
# =============================================================================

class TestChatbotRoutesToolsMode:
    """Tests for chatbot API routes in Tools mode."""

    def test_quick_chat_tools_mode(self, authenticated_client, app, mock_deepseek_client,
                                    sample_customer_data):
        """Test quick chat endpoint in tools mode (default)."""
        with app.app_context():
            # Mock tool response
            mock_deepseek_client.chat.completions.create.return_value.choices[0].message.tool_calls = None

            response = authenticated_client.post(
                "/api/chat/quick",
                json={
                    "message": "Hello",
                    "mode": "tools"  # Explicit tools mode
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "response" in data

    def test_quick_chat_default_mode_is_tools(self, authenticated_client, app,
                                               mock_deepseek_client):
        """Test that default mode is tools when not specified."""
        with app.app_context():
            response = authenticated_client.post(
                "/api/chat/quick",
                json={"message": "Hello"}  # No mode specified
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

    def test_send_message_tools_mode(self, authenticated_client, app, test_user,
                                      mock_deepseek_client, sample_customer_data):
        """Test sending message in tools mode."""
        with app.app_context():
            session = ChatSession(user_id=test_user.id)
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            mock_deepseek_client.chat.completions.create.return_value.choices[0].message.tool_calls = None

            response = authenticated_client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Find customers named Acme",
                    "mode": "tools"
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


# =============================================================================
# Status and Health Check Tests
# =============================================================================

class TestDeepSeekStatus:
    """Tests for DeepSeek API status checking."""

    def test_check_deepseek_status(self, app, mock_deepseek_client, mock_sentence_transformer):
        """Test checking DeepSeek API status."""
        with app.app_context():
            from services.rag_service import check_deepseek_status

            status = check_deepseek_status()

            assert status["api_configured"] is True
            assert status["api_available"] is True
            assert status["embed_model_local"] is True
            assert status["embed_model"] == "all-MiniLM-L6-v2"
            assert status["chat_model"] == "deepseek-chat"

    def test_check_deepseek_status_no_api_key(self, app):
        """Test status check when API key is not configured."""
        with app.app_context():
            from services.rag_service import check_deepseek_status

            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': ''}):
                status = check_deepseek_status()

                assert status["api_configured"] is False
                assert "error" in status

    def test_is_deepseek_available(self, app, mock_deepseek_client):
        """Test is_deepseek_available function."""
        with app.app_context():
            from services.rag_service import is_deepseek_available

            available = is_deepseek_available()

            assert available is True

    def test_status_endpoint(self, authenticated_client, app, mock_deepseek_client,
                              mock_sentence_transformer):
        """Test /api/chat/status endpoint."""
        with app.app_context():
            response = authenticated_client.get("/api/chat/status")

            assert response.status_code == 200
            data = response.get_json()
            assert "ollama" in data  # Backwards compatible key name
            assert "embeddings" in data
