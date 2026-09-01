import json
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas import Assertion
from app.llm import get_llm
from app.models import AppMapNode, GraphNode

class MatrixTestCase(BaseModel):
    name: str = Field(..., description="Short name of the test case, e.g. 'Happy Path - Valid Checkout'")
    prompt: str = Field(..., description="Natural language instructions for the QA agent to execute this test.")
    success_criteria: str = Field(..., description="What constitutes a successful outcome for this test.")
    assertions: List[Assertion] = Field(..., description="List of assertions to verify the test outcome.")


class TestMatrix(BaseModel):
    test_cases: List[MatrixTestCase] = Field(..., description="A list of 3-5 drafted test cases covering happy path, negative path, and edge cases.")


def _build_system_prompt() -> str:
    return """You are an expert QA Automation Engineer.
Your task is to generate a comprehensive "Test Matrix" (a draft suite of 3-5 test cases) for a specific application flow/node.
You will be provided with the node's name, description, and context.
You MUST generate a structured JSON output with the following test cases:
1. Happy Path: The standard, expected successful flow.
2. Negative Path(s): Testing invalid inputs, missing fields, or unauthorized access.
3. Edge Case(s): Boundary conditions, unusual but valid inputs.

For each test case, provide a clear, step-by-step `prompt` for an autonomous AI web agent to follow, a `success_criteria`, and up to 3 `assertions`.
"""

def generate_test_matrix_for_node(node: GraphNode, app_map_node: Optional[AppMapNode] = None) -> TestMatrix:
    """Generate a test matrix using the LLM for a given graph node."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(TestMatrix)

    node_label = node.label if node else (app_map_node.label if app_map_node else "Unknown Flow")
    node_desc = node.description if node else (app_map_node.description if app_map_node else "")
    node_url = app_map_node.url if app_map_node else ""

    user_prompt = f"Flow Name: {node_label}\n"
    if node_url:
        user_prompt += f"Target URL: {node_url}\n"
    if node_desc:
        user_prompt += f"Description: {node_desc}\n"
    
    if app_map_node and app_map_node.suggested_prompt:
        user_prompt += f"\nInitial Suggested Test: {app_map_node.suggested_prompt}\n"
    
    messages = [
        ("system", _build_system_prompt()),
        ("human", user_prompt),
    ]

    result = structured_llm.invoke(messages)
    return result
