# RAG Chatbot Design for Awning Management System

## Executive Summary

This document outlines the design and implementation plan for a business-focused RAG (Retrieval-Augmented Generation) chatbot for the Awning Work Order Management System. The chatbot will provide intelligent assistance to users by answering questions about customers, work orders, repair orders, inventory, and business analytics using natural language queries.

**Key Design Decisions:**
- **Hybrid Architecture:** Flask app on Elastic Beanstalk + AWS Lambda for LLM inference
- **Vector Database:** AWS OpenSearch Serverless or PostgreSQL with pgvector extension
- **LLM Provider:** AWS Bedrock (Claude 3.5 Sonnet recommended) or OpenAI API
- **Embedding Model:** Amazon Titan Embeddings or OpenAI text-embedding-3-small
- **Data Sources:** PostgreSQL database, S3 documents, business analytics

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Design](#component-design)
3. [Data Pipeline](#data-pipeline)
4. [RAG Implementation](#rag-implementation)
5. [AWS Lambda Integration](#aws-lambda-integration)
6. [Security & Access Control](#security--access-control)
7. [Implementation Phases](#implementation-phases)
8. [Cost Estimation](#cost-estimation)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Alternative Architectures](#alternative-architectures)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interface (Browser)                      │
│                  Flask Templates + JavaScript                    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              Flask App (Elastic Beanstalk)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Chat Route (/api/chat)                                   │  │
│  │  - Authentication & Authorization                         │  │
│  │  - Query Processing & Context Building                    │  │
│  │  - Session Management                                      │  │
│  └────────────┬───────────────────────────────┬───────────────┘  │
└───────────────┼───────────────────────────────┼──────────────────┘
                │                               │
                │                               │
                ▼                               ▼
┌───────────────────────────────┐   ┌─────────────────────────────┐
│   Vector Search Service       │   │   AWS Lambda Function       │
│   (OpenSearch/pgvector)       │   │   - LLM Inference           │
│                               │   │   - Prompt Engineering      │
│   - Semantic Search           │   │   - Response Generation     │
│   - Hybrid Search (BM25+Vec)  │   │                             │
│   - Filtered Search           │   │   Models:                   │
└───────────────┬───────────────┘   │   - AWS Bedrock (Claude)    │
                │                   │   - or OpenAI API           │
                │                   └─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Sources                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │   PostgreSQL     │  │   S3 Bucket      │  │  Analytics    │ │
│  │   (RDS)          │  │   - PDFs         │  │  Cache        │ │
│  │   - Customers    │  │   - Work Orders  │  │               │ │
│  │   - Work Orders  │  │   - Documents    │  │               │ │
│  │   - Inventory    │  │                  │  │               │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Benefits

1. **Separation of Concerns:** Flask handles web logic, Lambda handles compute-intensive LLM calls
2. **Cost Efficiency:** Lambda only runs when needed, avoiding constant LLM inference costs
3. **Scalability:** Lambda auto-scales for concurrent users
4. **Elastic Beanstalk Compatibility:** Minimal changes to existing infrastructure
5. **Timeout Handling:** Lambda functions support longer timeouts (up to 15 minutes) for complex queries

---

## Component Design

### 1. Chat Interface (Frontend)

**Location:** `templates/chat/` and `static/js/chat.js`

**Features:**
- Conversational UI with message history
- Typing indicators during LLM response
- Code/table formatting for structured data
- Source citations (links to work orders, customers, etc.)
- Quick action buttons (e.g., "Show me today's queue")
- Voice input support (optional)

**Technology:**
- HTML/CSS with existing base template styling
- JavaScript (vanilla or lightweight library)
- WebSocket or Server-Sent Events for streaming responses
- Markdown rendering for formatted responses

**Example UI:**
```html
<div class="chat-container">
  <div class="chat-messages" id="chatMessages">
    <!-- Message history -->
  </div>
  <div class="chat-input">
    <textarea id="userInput" placeholder="Ask about work orders, customers, inventory..."></textarea>
    <button id="sendBtn">Send</button>
  </div>
  <div class="quick-actions">
    <button data-query="What work orders are in the queue today?">Today's Queue</button>
    <button data-query="Show me overdue work orders">Overdue Orders</button>
    <button data-query="What's our inventory status?">Inventory Status</button>
  </div>
</div>
```

---

### 2. Flask Chat Route

**Location:** `routes/chat.py`

**Responsibilities:**
- Receive user queries
- Authenticate and authorize users
- Retrieve relevant context from vector database
- Build prompts with retrieved context
- Invoke AWS Lambda for LLM inference
- Stream responses back to frontend
- Log conversations for analytics

**Code Structure:**
```python
# routes/chat.py
from flask import Blueprint, request, jsonify, stream_with_context
from flask_login import login_required, current_user
import boto3
import json

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@chat_bp.route('/query', methods=['POST'])
@login_required
def query():
    """
    Handle user chat queries with RAG pipeline
    """
    data = request.get_json()
    user_query = data.get('query')
    session_id = data.get('session_id')

    # 1. Retrieve relevant context from vector DB
    context_docs = retrieve_context(user_query, user_id=current_user.id)

    # 2. Build prompt with context
    prompt = build_prompt(user_query, context_docs, session_id)

    # 3. Invoke Lambda for LLM inference
    response = invoke_lambda_llm(prompt)

    # 4. Return response with sources
    return jsonify({
        'response': response['text'],
        'sources': response['sources'],
        'session_id': session_id
    })

def retrieve_context(query, user_id, top_k=5):
    """
    Retrieve relevant documents from vector database
    """
    # Vector search implementation
    pass

def build_prompt(query, context_docs, session_id):
    """
    Build LLM prompt with retrieved context
    """
    pass

def invoke_lambda_llm(prompt):
    """
    Call AWS Lambda function for LLM inference
    """
    lambda_client = boto3.client('lambda', region_name='us-east-1')

    payload = {
        'prompt': prompt,
        'max_tokens': 1000,
        'temperature': 0.7
    }

    response = lambda_client.invoke(
        FunctionName='awning-rag-llm',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    return json.loads(response['Payload'].read())
```

---

### 3. Vector Database

**Option A: PostgreSQL with pgvector (Recommended for MVP)**

**Pros:**
- Leverages existing RDS PostgreSQL instance
- No additional AWS service costs
- Familiar SQL interface
- Easy integration with existing models

**Cons:**
- Less optimized for large-scale vector search
- Manual index management

**Setup:**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 or Titan embeddings
    metadata JSONB,
    doc_type VARCHAR(50),  -- 'work_order', 'customer', 'inventory', etc.
    doc_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for fast similarity search
CREATE INDEX ON document_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create GIN index for metadata filtering
CREATE INDEX idx_metadata ON document_embeddings USING GIN (metadata);
```

**Option B: AWS OpenSearch Serverless**

**Pros:**
- Purpose-built for vector search at scale
- Serverless (auto-scaling)
- Hybrid search (BM25 + vector)
- Advanced filtering and faceting

**Cons:**
- Additional AWS service cost (~$700/month minimum)
- More complex setup
- Learning curve for OpenSearch APIs

**When to Choose:**
- Use **pgvector** for MVP and low-medium scale (< 1M documents)
- Use **OpenSearch** for production scale (> 1M documents) or advanced search features

---

### 4. Embedding Pipeline

**Location:** `utils/embeddings.py` and `scripts/build_embeddings.py`

**Responsibilities:**
- Generate embeddings for all business data
- Incremental updates when data changes
- Batch processing for initial indexing
- Deduplication and chunking strategies

**Data Sources to Embed:**

1. **Work Orders:**
   - Order details (WOName, SpecialInstructions, RepairsNeeded)
   - Customer context (name, address, contact)
   - Items (descriptions, materials, conditions)
   - Status and dates

2. **Customers:**
   - Customer profile (name, contact, address)
   - Order history summaries
   - Source/vendor information

3. **Repair Orders:**
   - Repair details and items
   - Labor and parts information
   - Customer context

4. **Inventory:**
   - Item descriptions
   - Materials and conditions
   - Quantity and pricing

5. **Analytics Summaries:**
   - Daily/weekly/monthly reports
   - Revenue summaries
   - Queue metrics

6. **PDF Documents (S3):**
   - Extract text from work order PDFs
   - Extract text from uploaded documents

**Chunking Strategy:**
```python
# utils/embeddings.py
from typing import List, Dict
import openai  # or boto3 for AWS Bedrock

class EmbeddingManager:
    def __init__(self, model='text-embedding-3-small'):
        self.model = model

    def chunk_work_order(self, work_order: WorkOrder) -> List[Dict]:
        """
        Split work order into semantic chunks
        """
        chunks = []

        # Chunk 1: Order header with customer context
        header_text = f"""
        Work Order {work_order.WorkOrderNo}
        Customer: {work_order.customer.Name}
        Contact: {work_order.customer.Contact}
        Address: {work_order.customer.get_full_address()}
        Status: {work_order.ReturnStatus}
        Date In: {work_order.DateIn}
        Date Required: {work_order.DateRequired}
        Special Instructions: {work_order.SpecialInstructions}
        """

        chunks.append({
            'content': header_text.strip(),
            'metadata': {
                'doc_type': 'work_order_header',
                'doc_id': work_order.WorkOrderNo,
                'customer_id': work_order.CustID,
                'date_in': str(work_order.DateIn) if work_order.DateIn else None
            }
        })

        # Chunk 2: Items
        if work_order.items:
            items_text = f"Work Order {work_order.WorkOrderNo} Items:\n"
            for item in work_order.items:
                items_text += f"- {item.Description} ({item.Material}), "
                items_text += f"Qty: {item.Qty}, Condition: {item.Condition}\n"

            chunks.append({
                'content': items_text.strip(),
                'metadata': {
                    'doc_type': 'work_order_items',
                    'doc_id': work_order.WorkOrderNo,
                    'customer_id': work_order.CustID
                }
            })

        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using OpenAI or AWS Bedrock
        """
        # OpenAI example
        response = openai.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

        # AWS Bedrock example (alternative)
        # bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        # response = bedrock.invoke_model(
        #     modelId='amazon.titan-embed-text-v1',
        #     body=json.dumps({'inputText': text})
        # )

    def index_work_order(self, work_order: WorkOrder):
        """
        Generate and store embeddings for a work order
        """
        chunks = self.chunk_work_order(work_order)
        texts = [chunk['content'] for chunk in chunks]
        embeddings = self.generate_embeddings(texts)

        for chunk, embedding in zip(chunks, embeddings):
            # Store in pgvector
            doc_emb = DocumentEmbedding(
                content=chunk['content'],
                embedding=embedding,
                metadata=chunk['metadata'],
                doc_type=chunk['metadata']['doc_type'],
                doc_id=chunk['metadata']['doc_id']
            )
            db.session.add(doc_emb)

        db.session.commit()
```

**Batch Indexing Script:**
```python
# scripts/build_embeddings.py
from app import app, db
from models import WorkOrder, Customer, Inventory, RepairWorkOrder
from utils.embeddings import EmbeddingManager

def build_all_embeddings():
    """
    Initial indexing of all business data
    """
    with app.app_context():
        emb_manager = EmbeddingManager()

        # Index all work orders
        print("Indexing work orders...")
        work_orders = WorkOrder.query.all()
        for i, wo in enumerate(work_orders):
            emb_manager.index_work_order(wo)
            if i % 100 == 0:
                print(f"Indexed {i}/{len(work_orders)} work orders")

        # Index all customers
        print("Indexing customers...")
        customers = Customer.query.all()
        for customer in customers:
            emb_manager.index_customer(customer)

        # Index inventory
        print("Indexing inventory...")
        inventory_items = Inventory.query.all()
        for item in inventory_items:
            emb_manager.index_inventory_item(item)

        print("Indexing complete!")

if __name__ == '__main__':
    build_all_embeddings()
```

**Incremental Updates (Database Triggers or Application Hooks):**
```python
# In routes/work_orders.py - after creating/updating work order
@work_orders_bp.route('/create', methods=['POST'])
@login_required
def create_work_order():
    # ... existing code ...

    db.session.commit()

    # Trigger embedding update
    from utils.embeddings import EmbeddingManager
    emb_manager = EmbeddingManager()
    emb_manager.index_work_order(new_work_order)

    # ... rest of code ...
```

---

### 5. AWS Lambda Function for LLM Inference

**Why Lambda?**
- **Cost Efficiency:** Pay only for LLM inference time (not 24/7 like EC2)
- **Scalability:** Auto-scales for concurrent users
- **Timeout:** Supports up to 15-minute execution for complex queries
- **Separation:** Keeps compute-intensive LLM work off EB instances

**Lambda Function Structure:**
```
awning-rag-llm/
├── lambda_function.py      # Main handler
├── requirements.txt        # Dependencies (boto3, openai, etc.)
├── prompt_templates.py     # Prompt engineering
└── config.py               # Model configuration
```

**lambda_function.py:**
```python
import json
import os
import boto3
from openai import OpenAI

# Initialize clients
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

def lambda_handler(event, context):
    """
    Main Lambda handler for LLM inference

    Event structure:
    {
        "prompt": "Full prompt with context",
        "model": "claude-3-5-sonnet" or "gpt-4",
        "max_tokens": 1000,
        "temperature": 0.7,
        "stream": false
    }
    """
    try:
        prompt = event['prompt']
        model = event.get('model', 'claude-3-5-sonnet')
        max_tokens = event.get('max_tokens', 1000)
        temperature = event.get('temperature', 0.7)

        # Route to appropriate LLM provider
        if model.startswith('claude'):
            response = invoke_bedrock_claude(prompt, model, max_tokens, temperature)
        elif model.startswith('gpt'):
            response = invoke_openai(prompt, model, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported model: {model}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'text': response,
                'model': model,
                'tokens_used': len(response.split())  # Approximate
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def invoke_bedrock_claude(prompt, model, max_tokens, temperature):
    """
    Invoke AWS Bedrock with Claude model
    """
    model_id = f"anthropic.{model}-20240229-v1:0"

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body)
    )

    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']

def invoke_openai(prompt, model, max_tokens, temperature):
    """
    Invoke OpenAI API
    """
    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )

    return response.choices[0].message.content
```

**Deployment:**
```bash
# Package Lambda function
cd lambda/awning-rag-llm
pip install -r requirements.txt -t .
zip -r lambda.zip .

# Deploy via AWS CLI
aws lambda create-function \
  --function-name awning-rag-llm \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --zip-file fileb://lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables={OPENAI_API_KEY=sk-...}

# Or deploy via AWS SAM/Terraform
```

**IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

### 6. Retrieval Logic

**Location:** `utils/retrieval.py`

**Hybrid Retrieval Strategy:**
```python
# utils/retrieval.py
from typing import List, Dict
from sqlalchemy import text
from models import WorkOrder, Customer

class Retriever:
    def __init__(self, top_k=5, similarity_threshold=0.7):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def retrieve(self, query: str, user_id: int, filters: Dict = None) -> List[Dict]:
        """
        Hybrid retrieval combining:
        1. Vector similarity search
        2. Keyword/metadata filtering
        3. Recency boosting
        """
        # Generate query embedding
        from utils.embeddings import EmbeddingManager
        emb_manager = EmbeddingManager()
        query_embedding = emb_manager.generate_embeddings([query])[0]

        # Build SQL query with pgvector
        sql = text("""
            SELECT
                content,
                metadata,
                doc_type,
                doc_id,
                1 - (embedding <=> :query_embedding::vector) as similarity
            FROM document_embeddings
            WHERE 1 - (embedding <=> :query_embedding::vector) > :threshold
        """)

        # Add metadata filters if provided
        if filters:
            if filters.get('doc_type'):
                sql += text(" AND doc_type = :doc_type")
            if filters.get('customer_id'):
                sql += text(" AND metadata->>'customer_id' = :customer_id")
            if filters.get('date_range'):
                sql += text(" AND (metadata->>'date_in')::date BETWEEN :start_date AND :end_date")

        sql += text("""
            ORDER BY similarity DESC
            LIMIT :top_k
        """)

        params = {
            'query_embedding': query_embedding,
            'threshold': self.similarity_threshold,
            'top_k': self.top_k,
            **filters
        }

        results = db.session.execute(sql, params).fetchall()

        # Enhance results with source links
        enhanced_results = []
        for row in results:
            enhanced_results.append({
                'content': row.content,
                'metadata': row.metadata,
                'similarity': row.similarity,
                'source_link': self._build_source_link(row.doc_type, row.doc_id)
            })

        return enhanced_results

    def _build_source_link(self, doc_type: str, doc_id: str) -> str:
        """
        Build clickable links to source documents
        """
        if doc_type == 'work_order_header':
            return f"/work_orders/{doc_id}"
        elif doc_type == 'customer':
            return f"/customers/{doc_id}"
        elif doc_type == 'repair_order':
            return f"/repair_work_orders/{doc_id}"
        elif doc_type == 'inventory':
            return f"/inventory"
        return None

    def retrieve_with_sql_fallback(self, query: str, user_id: int) -> List[Dict]:
        """
        Fallback to direct SQL queries for structured questions

        Examples:
        - "Show me all work orders for customer ABC123"
        - "What's in the cleaning queue today?"
        - "List overdue work orders"
        """
        # Use regex or LLM to detect structured queries
        if self._is_structured_query(query):
            return self._execute_structured_query(query)
        else:
            return self.retrieve(query, user_id)

    def _is_structured_query(self, query: str) -> bool:
        """
        Detect if query is a structured database query
        """
        structured_patterns = [
            r"show (me )?all",
            r"list (all )?",
            r"what('s| is) in the (queue|inventory)",
            r"how many",
            r"count",
        ]
        # Simple pattern matching (could use LLM for better detection)
        import re
        for pattern in structured_patterns:
            if re.search(pattern, query.lower()):
                return True
        return False

    def _execute_structured_query(self, query: str) -> List[Dict]:
        """
        Execute direct database queries for structured questions
        (Placeholder - implement based on query type)
        """
        # Use LLM to generate SQL from natural language
        # Or use predefined query templates
        pass
```

**Query Classification (Optional Enhancement):**
```python
def classify_query(query: str) -> str:
    """
    Classify query type to route to appropriate retrieval strategy

    Returns:
    - 'semantic': General question requiring vector search
    - 'structured': Database query requiring SQL
    - 'analytical': Requires running analytics
    - 'conversational': Chitchat or clarification
    """
    # Use lightweight classifier or simple LLM call
    classification_prompt = f"""
    Classify this user query into one of these categories:
    - semantic: General question about business data
    - structured: Specific database query (list, show, count)
    - analytical: Requires calculations or reports
    - conversational: Chitchat or clarification

    Query: {query}

    Category:
    """

    # Call lightweight LLM (e.g., GPT-3.5-turbo or Claude Haiku)
    # Return classification
```

---

## RAG Implementation

### Prompt Engineering

**Location:** `utils/prompts.py`

**System Prompt:**
```python
SYSTEM_PROMPT = """
You are an AI assistant for an awning cleaning and repair business management system.
You help staff answer questions about work orders, customers, inventory, and business operations.

Your capabilities:
- Answer questions about work orders, repair orders, and customer information
- Provide inventory status and item details
- Explain business metrics and analytics
- Guide users through system workflows
- Search historical data

Guidelines:
- Be concise and professional
- Use specific data from the provided context
- If information is not in the context, say so clearly
- Include relevant work order numbers, customer IDs, and dates
- Format responses with tables or lists when appropriate
- Provide source links when referencing specific records

Data Context:
The following information is relevant to the user's query:

{context}

Current Date: {current_date}
User: {user_name} (Role: {user_role})
"""
```

**Prompt Builder:**
```python
# utils/prompts.py
from datetime import datetime
from typing import List, Dict

def build_rag_prompt(
    user_query: str,
    context_docs: List[Dict],
    user_name: str,
    user_role: str,
    conversation_history: List[Dict] = None
) -> str:
    """
    Build complete RAG prompt with context and conversation history
    """
    # Format context documents
    context_str = "\n\n".join([
        f"Document {i+1} (Similarity: {doc['similarity']:.2f}):\n{doc['content']}"
        for i, doc in enumerate(context_docs)
    ])

    # Build system prompt
    system_prompt = SYSTEM_PROMPT.format(
        context=context_str,
        current_date=datetime.now().strftime("%Y-%m-%d"),
        user_name=user_name,
        user_role=user_role
    )

    # Add conversation history
    conversation_str = ""
    if conversation_history:
        conversation_str = "\n\nConversation History:\n"
        for msg in conversation_history[-5:]:  # Last 5 messages
            conversation_str += f"{msg['role']}: {msg['content']}\n"

    # Build final prompt
    full_prompt = f"""
{system_prompt}

{conversation_str}

User Question: {user_query}

Answer:
"""

    return full_prompt
```

**Example Prompts for Common Use Cases:**

```python
# Business Analytics Query
"""
User asks: "What was our revenue last month?"

Context: [Monthly analytics data, completed work orders, payment info]

Response should include:
- Total revenue with breakdown by category (cleaning vs. repairs)
- Comparison to previous month
- Top customers by revenue
- Charts/visualizations if available
"""

# Work Order Search
"""
User asks: "Find all work orders for John Smith's boat"

Context: [Customer info, work order history, current queue status]

Response should include:
- List of all work orders with numbers
- Status of each order
- Links to detailed views
- Any pending or in-progress orders highlighted
"""

# Inventory Query
"""
User asks: "Do we have any Sunbrella Canvas in stock?"

Context: [Inventory items matching "Sunbrella", material "Canvas"]

Response should include:
- Available quantity
- Condition and color breakdown
- Pricing information
- Recent usage trends
"""
```

---

## Security & Access Control

### Authentication & Authorization

**Row-Level Security:**
```python
# utils/retrieval.py - Enhanced with access control

class SecureRetriever(Retriever):
    def retrieve(self, query: str, user_id: int, filters: Dict = None) -> List[Dict]:
        """
        Retrieve with user-based access control
        """
        # Get user permissions
        user = User.query.get(user_id)

        # Add permission filters
        if not user.is_admin:
            # Non-admin users can only see their assigned work orders
            # This is a simplified example - implement based on your auth model
            if filters is None:
                filters = {}

            # Example: restrict to user's assigned customers or territory
            # filters['assigned_user_id'] = user_id

        return super().retrieve(query, user_id, filters)
```

**Data Sanitization:**
```python
def sanitize_response(response: str) -> str:
    """
    Remove sensitive information from LLM responses
    """
    import re

    # Redact credit card numbers
    response = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[REDACTED]', response)

    # Redact SSNs
    response = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED]', response)

    # Add more sanitization rules as needed

    return response
```

**Audit Logging:**
```python
# models/chat_log.py
class ChatLog(db.Model):
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    query = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    retrieved_docs = db.Column(db.JSON)  # Store what context was used
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tokens_used = db.Column(db.Integer)

    user = db.relationship('User', backref='chat_logs')

# In routes/chat.py
def log_chat_interaction(user_id, session_id, query, response, docs, tokens):
    log = ChatLog(
        user_id=user_id,
        session_id=session_id,
        query=query,
        response=response,
        retrieved_docs=[{'content': d['content'][:200], 'doc_id': d.get('metadata', {}).get('doc_id')} for d in docs],
        tokens_used=tokens
    )
    db.session.add(log)
    db.session.commit()
```

---

## Implementation Phases

### Phase 1: MVP (2-3 weeks)

**Goal:** Basic Q&A chatbot with work order search

**Tasks:**
1. **Setup pgvector extension** (1 day)
   - Enable pgvector on RDS PostgreSQL
   - Create embeddings table and indexes
   - Test vector search performance

2. **Build embedding pipeline** (3 days)
   - Create `EmbeddingManager` class
   - Implement work order chunking
   - Build batch indexing script
   - Index all existing work orders

3. **Create AWS Lambda function** (2 days)
   - Setup Lambda with Bedrock or OpenAI
   - Implement LLM inference handler
   - Test with sample prompts
   - Configure IAM permissions

4. **Develop Flask chat route** (3 days)
   - Create `/api/chat/query` endpoint
   - Implement retrieval logic
   - Build prompt templates
   - Lambda invocation from Flask

5. **Build basic chat UI** (2 days)
   - Simple chat interface in templates
   - Message history display
   - Loading states
   - Basic styling with existing CSS

6. **Testing & refinement** (2 days)
   - Test with real business queries
   - Refine prompts for accuracy
   - Performance optimization
   - Bug fixes

**Deliverables:**
- Working chatbot that answers questions about work orders
- Basic retrieval from work order data
- Simple chat interface
- Lambda function for LLM calls

---

### Phase 2: Enhanced Features (2-3 weeks)

**Goal:** Multi-source data, better UI, incremental indexing

**Tasks:**
1. **Expand data sources** (4 days)
   - Index customers, repair orders, inventory
   - Implement incremental embedding updates
   - Add PDF document extraction
   - S3 document indexing

2. **Improve chat UI** (3 days)
   - Better styling and UX
   - Source citations with links
   - Quick action buttons
   - Conversation history
   - Markdown rendering

3. **Add conversation memory** (2 days)
   - Session management
   - Conversation history storage
   - Context-aware responses

4. **Implement filters** (2 days)
   - Date range filtering
   - Customer-specific queries
   - Status filtering
   - Territory/user filtering

5. **Performance optimization** (2 days)
   - Query caching
   - Response streaming
   - Lambda cold start optimization
   - Database query optimization

**Deliverables:**
- Full business data searchable
- Improved UI/UX
- Conversational memory
- Advanced filtering

---

### Phase 3: Advanced Features (3-4 weeks)

**Goal:** Analytics, SQL generation, multi-modal support

**Tasks:**
1. **SQL query generation** (5 days)
   - Text-to-SQL for structured queries
   - Query validation and safety
   - Result formatting
   - Complex aggregations

2. **Analytics integration** (3 days)
   - Connect to analytics cache
   - Business metrics queries
   - Chart generation from chat
   - Report export

3. **Multi-modal support** (4 days)
   - Image upload for damage assessment
   - PDF upload and analysis
   - Voice input (optional)
   - Screenshot analysis

4. **Admin features** (3 days)
   - Usage analytics dashboard
   - Prompt management UI
   - Embedding reindexing tools
   - Cost tracking

5. **Advanced RAG techniques** (3 days)
   - Hybrid search (BM25 + vector)
   - Query rewriting
   - Multi-hop reasoning
   - Fact verification

**Deliverables:**
- Text-to-SQL capability
- Analytics from chat
- Multi-modal inputs
- Admin tools

---

## Cost Estimation

### AWS Lambda Costs

**Assumptions:**
- 1000 queries/day
- Average 2 seconds per query (LLM inference)
- 512 MB memory
- 30 days/month

**Lambda Costs:**
```
Requests: 1000/day × 30 days = 30,000 requests/month
Duration: 30,000 × 2 seconds = 60,000 seconds = 16.67 hours

Lambda Pricing (us-east-1):
- $0.20 per 1M requests = $0.006/month
- $0.0000166667 per GB-second = $0.139/month (512 MB × 16.67 hours)

Total Lambda: ~$0.15/month (negligible)
```

### LLM API Costs

**AWS Bedrock (Claude 3.5 Sonnet):**
```
Input: $3 per 1M tokens
Output: $15 per 1M tokens

Assumptions per query:
- Input: 1500 tokens (context + prompt)
- Output: 500 tokens

Monthly cost:
- Input: 30,000 queries × 1500 tokens × $3/1M = $135/month
- Output: 30,000 queries × 500 tokens × $15/1M = $225/month

Total: $360/month
```

**OpenAI (GPT-4o):**
```
Input: $2.50 per 1M tokens
Output: $10 per 1M tokens

Monthly cost:
- Input: 30,000 × 1500 × $2.50/1M = $112.50/month
- Output: 30,000 × 500 × $10/1M = $150/month

Total: $262.50/month
```

**OpenAI (GPT-3.5-turbo) - Budget Option:**
```
Input: $0.50 per 1M tokens
Output: $1.50 per 1M tokens

Monthly cost:
- Input: 30,000 × 1500 × $0.50/1M = $22.50/month
- Output: 30,000 × 500 × $1.50/1M = $22.50/month

Total: $45/month
```

### Embedding Costs

**OpenAI (text-embedding-3-small):**
```
$0.02 per 1M tokens

Initial indexing (one-time):
- 10,000 documents × 500 tokens avg = 5M tokens
- Cost: $0.10 (one-time)

Incremental updates:
- 100 documents/day × 500 tokens = 50,000 tokens/day
- Monthly: 1.5M tokens × $0.02/1M = $0.03/month
```

**AWS Bedrock (Titan Embeddings):**
```
$0.10 per 1M tokens

Initial: 5M tokens × $0.10/1M = $0.50 (one-time)
Monthly updates: 1.5M tokens × $0.10/1M = $0.15/month
```

### Vector Database Costs

**PostgreSQL with pgvector (Recommended for MVP):**
```
- Uses existing RDS instance
- Minimal additional storage (<1 GB for 10K documents)
- No additional cost
```

**AWS OpenSearch Serverless (If scaling up):**
```
- OCU (OpenSearch Compute Units): ~$700/month minimum
- Storage: $0.024 per GB-month

Only recommended if:
- >1M documents
- Advanced search features needed
- High query throughput (>10K/day)
```

### Total Monthly Cost Summary

**MVP (Phase 1):**
- Lambda: $0.15
- LLM (GPT-3.5-turbo): $45
- Embeddings: $0.03
- Vector DB (pgvector): $0
- **Total: ~$45/month**

**Production (Phase 3 with Claude 3.5):**
- Lambda: $0.15
- LLM (Claude 3.5 Sonnet): $360
- Embeddings: $0.15
- Vector DB (pgvector): $0
- **Total: ~$360/month**

**Cost Optimization Tips:**
1. Use GPT-3.5-turbo for simple queries, GPT-4 for complex ones
2. Implement caching for common questions
3. Use smaller context windows when possible
4. Batch embedding generation
5. Monitor and set usage limits

---

## Monitoring & Maintenance

### Key Metrics to Track

**Performance Metrics:**
```python
# utils/monitoring.py
import time
from functools import wraps

def track_query_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        result = func(*args, **kwargs)

        duration = time.time() - start_time

        # Log to CloudWatch or database
        log_metric('chat_query_duration', duration)
        log_metric('chat_query_count', 1)

        return result
    return wrapper

# Track:
# - Query latency (p50, p95, p99)
# - LLM token usage
# - Cache hit rate
# - Retrieval accuracy
# - User satisfaction (thumbs up/down)
```

**Quality Metrics:**
```python
# Implement feedback mechanism
@chat_bp.route('/feedback', methods=['POST'])
@login_required
def chat_feedback():
    data = request.get_json()

    feedback = ChatFeedback(
        chat_log_id=data['chat_log_id'],
        rating=data['rating'],  # 1-5 or thumbs up/down
        comment=data.get('comment'),
        user_id=current_user.id
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({'success': True})
```

**Dashboards:**
- CloudWatch dashboard for Lambda metrics
- Custom dashboard for chat analytics:
  - Queries per day
  - Average response time
  - Token usage trends
  - User feedback scores
  - Top queries
  - Failed queries

### Maintenance Tasks

**Weekly:**
- Review failed queries and improve prompts
- Check for hallucinations in responses
- Monitor token costs

**Monthly:**
- Retrain/update embeddings for new data
- Review and optimize most expensive queries
- Update prompt templates based on feedback
- Analyze user feedback for improvements

**Quarterly:**
- Evaluate new LLM models for better performance/cost
- Review security and access logs
- Performance benchmarking
- Cost optimization review

---

## Alternative Architectures

### Option 1: All-in-One Flask (Simpler but Less Scalable)

**Architecture:**
```
Flask App (EB)
├── Chat routes
├── LLM inference (direct API calls)
├── Vector search (pgvector)
└── Database queries
```

**Pros:**
- Simpler deployment
- No Lambda complexity
- Lower latency (no Lambda cold starts)

**Cons:**
- LLM calls block Flask workers
- Limited scalability for concurrent users
- Higher memory usage on EB instances

**When to use:**
- Low traffic (<100 queries/day)
- Small team (< 5 users)
- Tight budget
- Quick prototype

---

### Option 2: Full Serverless (Most Scalable)

**Architecture:**
```
API Gateway → Lambda (Chat Handler)
              ├→ Lambda (LLM Inference)
              └→ Aurora Serverless (PostgreSQL + pgvector)
              └→ OpenSearch Serverless (Vector DB)
```

**Pros:**
- Maximum scalability
- Pay-per-use
- No server management

**Cons:**
- Most expensive at scale
- Complex deployment
- Vendor lock-in
- Higher latency (multiple Lambda hops)

**When to use:**
- High scale (>10K queries/day)
- Unpredictable traffic
- Multi-tenant SaaS
- External API exposure

---

### Option 3: Hybrid with ElastiCache

**Architecture:**
```
Flask App (EB)
├→ ElastiCache (Redis) - Response cache
├→ Lambda (LLM Inference)
└→ RDS PostgreSQL (pgvector)
```

**Pros:**
- Best balance of performance and cost
- Fast response for cached queries
- Scalable LLM inference

**Cons:**
- Added ElastiCache cost (~$15-50/month)
- More components to manage

**When to use:**
- Medium traffic (500-5K queries/day)
- Repeated common queries
- Production deployment (recommended)

---

## Getting Started: Quick Start Guide

### Prerequisite Checklist

- [ ] AWS CLI configured with Elastic Beanstalk access
- [ ] PostgreSQL RDS instance running (already exists)
- [ ] S3 bucket for Lambda deployments
- [ ] OpenAI API key or AWS Bedrock access
- [ ] pgvector extension enabled on RDS

### Step 1: Enable pgvector

```bash
# Connect to RDS PostgreSQL
psql -h your-rds-endpoint.rds.amazonaws.com -U postgres -d clean_repair

# Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create embeddings table
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    doc_type VARCHAR(50),
    doc_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON document_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Step 2: Install Dependencies

```bash
# Add to requirements.txt
openai>=1.0.0  # Or boto3 for Bedrock
pgvector>=0.2.0
sentence-transformers  # Optional for local embeddings
```

### Step 3: Create Embedding Model

```python
# models/document_embedding.py
from extensions import db
from pgvector.sqlalchemy import Vector

class DocumentEmbedding(db.Model):
    __tablename__ = 'document_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(Vector(1536))  # OpenAI ada-002 dimension
    metadata = db.Column(db.JSON)
    doc_type = db.Column(db.String(50))
    doc_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.now())
```

### Step 4: Run Initial Indexing

```bash
# Create initial embeddings
python scripts/build_embeddings.py
```

### Step 5: Deploy Lambda Function

```bash
cd lambda/awning-rag-llm
pip install -r requirements.txt -t .
zip -r lambda.zip .

aws lambda create-function \
  --function-name awning-rag-llm \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-role \
  --zip-file fileb://lambda.zip \
  --timeout 300 \
  --environment Variables={OPENAI_API_KEY=sk-xxx}
```

### Step 6: Add Chat Routes to Flask

```python
# In app.py
from routes.chat import chat_bp
app.register_blueprint(chat_bp)
```

### Step 7: Deploy to Elastic Beanstalk

```bash
eb deploy
```

### Step 8: Test the Chatbot

```bash
curl -X POST https://your-eb-app.com/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all work orders in the queue today",
    "session_id": "test-session-1"
  }'
```

---

## Troubleshooting

### Common Issues

**Issue: pgvector extension not found**
```
ERROR: could not open extension control file "/usr/share/postgresql/XX/extension/vector.control"
```

**Solution:**
```bash
# For RDS, enable via parameter group
# Or if using local PostgreSQL:
sudo apt-get install postgresql-14-pgvector
```

---

**Issue: Lambda timeout**
```
Task timed out after 3.00 seconds
```

**Solution:**
```bash
# Increase Lambda timeout
aws lambda update-function-configuration \
  --function-name awning-rag-llm \
  --timeout 300
```

---

**Issue: High embedding costs**

**Solution:**
- Use smaller embedding models (e.g., text-embedding-3-small)
- Batch embedding generation
- Cache embeddings for unchanged documents
- Only re-embed when content changes

---

**Issue: Poor retrieval quality**

**Solution:**
- Increase `top_k` for more context
- Lower similarity threshold
- Improve chunking strategy
- Add metadata filtering
- Use hybrid search (BM25 + vector)

---

## Future Enhancements

### Advanced Features Roadmap

**1. Multi-Agent System**
- Specialized agents for different tasks (customer service, analytics, inventory)
- Agent orchestration for complex queries
- Tool calling (create work orders, update inventory, etc.)

**2. Voice Interface**
- Speech-to-text integration
- Voice commands for common tasks
- Hands-free operation for field workers

**3. Mobile App**
- Native iOS/Android chat interface
- Offline mode with sync
- Push notifications for responses

**4. Workflow Automation**
- Create work orders from chat
- Update order status via chat
- Trigger email/SMS notifications
- Schedule follow-ups

**5. Predictive Analytics**
- Forecast completion times via chat
- Identify bottlenecks
- Recommend resource allocation
- Revenue projections

**6. Integration with External Systems**
- Email integration (query via email)
- Slack/Teams bot
- SMS interface (Twilio)
- Calendar integration

---

## References & Resources

**Documentation:**
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [AWS Bedrock](https://docs.aws.amazon.com/bedrock/)
- [OpenAI API](https://platform.openai.com/docs)
- [AWS Lambda](https://docs.aws.amazon.com/lambda/)
- [RAG Best Practices](https://www.anthropic.com/news/retrieval-augmented-generation)

**Tools:**
- [LangChain](https://python.langchain.com/) - RAG framework
- [LlamaIndex](https://www.llamaindex.ai/) - Data framework for LLM apps
- [Weaviate](https://weaviate.io/) - Alternative vector database

**Monitoring:**
- AWS CloudWatch for Lambda metrics
- Langfuse for LLM observability
- Weights & Biases for ML monitoring

---

## Conclusion

This design provides a comprehensive roadmap for implementing a production-ready RAG chatbot for your awning management system. The hybrid architecture (Flask + Lambda) balances simplicity, cost, and scalability while leveraging your existing Elastic Beanstalk infrastructure.

**Recommended Approach:**
1. Start with Phase 1 MVP using pgvector and GPT-3.5-turbo (~$45/month)
2. Gather user feedback and iterate on prompts
3. Expand to Phase 2 with full data sources
4. Upgrade to Claude 3.5 Sonnet or GPT-4 for production quality

**Key Success Factors:**
- High-quality embeddings and chunking strategy
- Well-engineered prompts with business context
- User feedback loop for continuous improvement
- Monitoring and cost optimization
- Security and access control from day one

For questions or implementation assistance, refer to the troubleshooting section or consult AWS documentation for specific service configurations.