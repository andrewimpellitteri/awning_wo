#!/usr/bin/env python
"""
Chatbot Behavior Test Script

This script tests the RAG chatbot with various prompts and logs:
- User prompts
- Context retrieved (RAG embeddings or tool calls)
- Model responses
- Metadata (tokens, sources, etc.)

Output: CSV file with test results for analysis
"""
import os
import sys
import csv
import json
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from services.rag_service import (
    chat_with_rag,
    chat_with_tools,
    search_all,
    check_deepseek_status,
    is_deepseek_available,
)

# Test scenarios with expected behaviors
TEST_SCENARIOS = [
    {
        "name": "Simple Question (RAG)",
        "prompt": "What customers do we have?",
        "type": "rag",
        "expected": "Should retrieve customer embeddings and list customers",
    },
    {
        "name": "Specific Search (Tools)",
        "prompt": "Find customer with name Smith",
        "type": "tools",
        "expected": "Should call search_customers tool with query='Smith'",
    },
    {
        "name": "Work Order Query (Tools)",
        "prompt": "Show me work orders for customer ABC123",
        "type": "tools",
        "expected": "Should call get_customer_work_orders tool",
    },
    {
        "name": "Multi-step Query (Tools)",
        "prompt": "Find all work orders with status 'In' and tell me which customers they belong to",
        "type": "tools",
        "expected": "Should call search_work_orders then get_customer_details for each",
    },
    {
        "name": "Item Search (Tools)",
        "prompt": "Find all blue awnings",
        "type": "tools",
        "expected": "Should call search_items with color='blue'",
    },
    {
        "name": "Statistics Query (Tools)",
        "prompt": "Give me work order statistics",
        "type": "tools",
        "expected": "Should call get_work_order_stats",
    },
    {
        "name": "General Question (RAG)",
        "prompt": "Tell me about recent work orders",
        "type": "rag",
        "expected": "Should retrieve work order embeddings and summarize",
    },
    {
        "name": "Complex Query (Tools)",
        "prompt": "Which customer has the most work orders?",
        "type": "tools",
        "expected": "Should call multiple tools to aggregate data",
    },
    {
        "name": "Semantic Search (RAG)",
        "prompt": "canvas awnings for boats",
        "type": "rag",
        "expected": "Should find semantically similar items/work orders",
    },
    {
        "name": "Follow-up Question",
        "prompt": "What's their contact information?",
        "type": "tools",
        "expected": "Should reference previous context (may fail without history)",
    },
]


def format_context(search_results: Dict = None, tool_calls: List[Dict] = None) -> str:
    """Format context/tools used for CSV output."""
    context_parts = []

    if search_results:
        # RAG semantic search results
        for result_type, results in search_results.items():
            if results and result_type != "error":
                context_parts.append(f"RAG-{result_type}: {len(results)} results")
                for r in results[:2]:  # Show top 2
                    similarity = r.get('similarity', 0)
                    context_parts.append(f"  - {r.get('content', '')[:80]}... (sim: {similarity:.3f})")

    if tool_calls:
        # Tool calling results
        context_parts.append(f"TOOLS: {len(tool_calls)} calls")
        for tc in tool_calls:
            tool_name = tc.get('tool', 'unknown')
            args = tc.get('arguments', {})
            result_preview = tc.get('result_preview', '')[:100]
            context_parts.append(f"  - {tool_name}({json.dumps(args)})")
            context_parts.append(f"    Result: {result_preview}...")

    if not context_parts:
        return "No context/tools used"

    return "\n".join(context_parts)


def test_rag_chat(prompt: str, app) -> Dict[str, Any]:
    """Test RAG-based chat (semantic search + DeepSeek)."""
    with app.app_context():
        try:
            # First, get search results to show context
            search_results = search_all(prompt, limit_per_type=3)

            # Then do the full RAG chat
            response_text, metadata = chat_with_rag(prompt)

            return {
                "success": True,
                "response": response_text,
                "context": format_context(search_results=search_results),
                "metadata": metadata,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "response": None,
                "context": None,
                "metadata": None,
                "error": str(e),
            }


def test_tools_chat(prompt: str, app) -> Dict[str, Any]:
    """Test tool-calling chat (function calling + DeepSeek)."""
    with app.app_context():
        try:
            response_text, metadata = chat_with_tools(prompt)

            tool_calls = metadata.get('tool_calls', [])

            return {
                "success": True,
                "response": response_text,
                "context": format_context(tool_calls=tool_calls),
                "metadata": metadata,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "response": None,
                "context": None,
                "metadata": None,
                "error": str(e),
            }


def run_tests(output_file: str = None):
    """Run all test scenarios and save to CSV."""
    app = create_app()

    # Check API status first
    print("=" * 80)
    print("Checking API Status...")
    print("=" * 80)

    with app.app_context():
        status = check_deepseek_status()
        print(f"DeepSeek API: {'✓' if status.get('api_available') else '✗'}")
        print(f"  - Configured: {status.get('api_configured')}")
        print(f"  - Chat model: {status.get('chat_model')}")
        print(f"  - Available: {status.get('chat_model_available')}")

        print(f"\nOpenAI Embeddings: {'✓' if status.get('embed_model_available') else '✗'}")
        print(f"  - Configured: {status.get('embed_api_configured')}")
        print(f"  - Model: {status.get('embed_model')}")
        print(f"  - Dimension: {status.get('embed_dimension', 'N/A')}")

        if status.get('embed_error'):
            print(f"  - Error: {status['embed_error']}")

        if not status.get('api_available'):
            print("\n⚠️  WARNING: DeepSeek API not available!")
            print(f"Error: {status.get('error', 'Unknown')}")
            return

    print("\n" + "=" * 80)
    print("Running Test Scenarios...")
    print("=" * 80)

    results = []

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n[{i}/{len(TEST_SCENARIOS)}] {scenario['name']}")
        print(f"Prompt: {scenario['prompt']}")
        print(f"Type: {scenario['type'].upper()}")
        print(f"Expected: {scenario['expected']}")
        print("-" * 80)

        # Run appropriate test
        if scenario['type'] == 'rag':
            result = test_rag_chat(scenario['prompt'], app)
        else:
            result = test_tools_chat(scenario['prompt'], app)

        # Print results
        if result['success']:
            print(f"✓ Success")
            print(f"\nContext/Tools Used:")
            print(result['context'])
            print(f"\nResponse:")
            print(result['response'])

            metadata = result.get('metadata', {})
            print(f"\nMetadata:")
            print(f"  - Tokens: {metadata.get('total_tokens', 'N/A')}")
            print(f"  - Tool calls: {metadata.get('tool_calls_count', 0)}")
            if metadata.get('sources'):
                print(f"  - Sources: {metadata['sources']}")
        else:
            print(f"✗ Failed")
            print(f"Error: {result['error']}")

        # Save to results
        results.append({
            "scenario_name": scenario['name'],
            "prompt": scenario['prompt'],
            "test_type": scenario['type'],
            "expected_behavior": scenario['expected'],
            "success": result['success'],
            "response": result.get('response', ''),
            "context_tools_used": result.get('context', ''),
            "error": result.get('error', ''),
            "total_tokens": result.get('metadata', {}).get('total_tokens', ''),
            "tool_calls_count": result.get('metadata', {}).get('tool_calls_count', 0),
            "timestamp": datetime.now().isoformat(),
        })

    # Save to CSV
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"chatbot_test_results_{timestamp}.csv"

    print("\n" + "=" * 80)
    print(f"Saving results to: {output_file}")
    print("=" * 80)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"\n✓ Results saved to {output_file}")

    # Summary
    successful = sum(1 for r in results if r['success'])
    print(f"\nSummary: {successful}/{len(results)} tests passed")

    return results


def debug_tool_calling_issue():
    """Debug why chat seems to stop after tool call."""
    app = create_app()

    print("=" * 80)
    print("Debugging Tool Calling Flow")
    print("=" * 80)

    test_prompt = "Find customer with name Smith"

    print(f"\nTest prompt: {test_prompt}")
    print("\nStep-by-step execution:")

    with app.app_context():
        from services.rag_service import (
            get_deepseek_client,
            AVAILABLE_TOOLS,
            DEEPSEEK_CHAT_MODEL,
        )

        client = get_deepseek_client()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": test_prompt}
        ]

        print("\n1. Initial API call with tools...")
        response = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=messages,
            tools=AVAILABLE_TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2048,
        )

        assistant_message = response.choices[0].message

        print(f"\n2. Response from DeepSeek:")
        print(f"   - Content: {assistant_message.content}")
        print(f"   - Tool calls: {len(assistant_message.tool_calls) if assistant_message.tool_calls else 0}")

        if assistant_message.tool_calls:
            print(f"\n3. Tool calls requested:")
            for tc in assistant_message.tool_calls:
                print(f"   - Tool: {tc.function.name}")
                print(f"   - Arguments: {tc.function.arguments}")

            # Execute tool
            from services.rag_service import execute_tool

            tool_call = assistant_message.tool_calls[0]
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            print(f"\n4. Executing tool: {tool_name}")
            result = execute_tool(tool_name, arguments)
            print(f"   Result preview: {result[:200]}...")

            # Add tool result to conversation
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in assistant_message.tool_calls]
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

            print(f"\n5. Second API call with tool results...")
            response2 = client.chat.completions.create(
                model=DEEPSEEK_CHAT_MODEL,
                messages=messages,
                tools=AVAILABLE_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2048,
            )

            final_response = response2.choices[0].message

            print(f"\n6. Final response:")
            print(f"   - Content: {final_response.content}")
            print(f"   - Additional tool calls: {len(final_response.tool_calls) if final_response.tool_calls else 0}")

            if not final_response.content:
                print("\n⚠️  ISSUE FOUND: Final response has no content!")
                print("   This is why chat appears to stop after tool call.")
        else:
            print("\n✗ No tool calls made - model responded directly")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test chatbot behavior and log results")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output CSV file path (default: chatbot_test_results_TIMESTAMP.csv)"
    )
    parser.add_argument(
        "--debug-tools",
        action="store_true",
        help="Debug tool calling flow instead of running tests"
    )

    args = parser.parse_args()

    if args.debug_tools:
        debug_tool_calling_issue()
    else:
        run_tests(output_file=args.output)