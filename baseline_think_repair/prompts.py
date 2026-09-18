"""
Prompt templates for ThinkRepair adapted for CI failure plan generation.

Based on ThinkRepair (ISSTA 2024) prompt structure:
1. Role Designation
2. Task Description
3. Input Context (CI logs + files)
4. Chain-of-Thought Indicator ("Let's think step by step")
"""

from typing import Dict, List


def build_system_prompt() -> str:
    """System message defining the role."""
    return "You are an Automated Program Repair tool specialized in analyzing CI failures and creating repair plans."


def build_collection_prompt(ci_logs: str, changed_files: List[str]) -> str:
    """
    Collection phase prompt for building knowledge pool.
    Used offline to generate CoT reasoning from training data.
    """
    return f"""Analyze this CI failure and explain the reasoning for the fix.

// CI Failure Logs
{ci_logs[:2000]}

// Changed Files
{changed_files}

Provide detailed step-by-step reasoning about:
1. What is causing the failure
2. Why this fix is needed
3. What the fix accomplishes

Let's think step by step."""


def extract_reasoning_from_response(response: str) -> str:
    """
    Extract reasoning text from LLM response.

    Returns:
        Reasoning text (cleaned)
    """
    # Remove code blocks if any (we only want reasoning)
    if "```" in response:
        parts = response.split("```")
        # Take text before first code block
        return parts[0].strip()

    return response.strip()
