"""
ThinkRepair wrapper for CI-based repair plan generation.

Based on ThinkRepair (ISSTA 2024): https://github.com/vinci-grape/ThinkRepair
Generates repair plans using knowledge pool, which are then passed to minisweagent.
"""

from typing import Dict, List, Optional
import json
import os
from pathlib import Path

from baseline_think_repair.repair_ci import ThinkRepairCI


def generate_plan_thinkrepair(
    issue_description: str,
    changed_files: List[str],
    repo_path: str,
    model: str = "minimax-m2_5",
    diff: str = "",
    workflow: str = "",
    sha_fail: str = "",
    instance_id: str = "",
    k_shot: int = 2,
    knowledge_pool_path: Optional[str] = None
) -> Dict:
    """
    Generate repair PLAN using ThinkRepair approach for CI failures.

    This plan is then passed to minisweagent for actual patch generation.

    Args:
        issue_description: CI failure logs/analysis
        changed_files: List of files changed in failing commit
        repo_path: Path to repository
        model: LLM model to use (minimax-m2_5, deepseek-v4-flash, etc.)
        diff: Git diff of changes
        workflow: CI workflow file content
        sha_fail: Failing commit SHA
        instance_id: Instance identifier
        k_shot: Number of few-shot examples to use from knowledge pool
        knowledge_pool_path: Path to pre-built knowledge pool JSON

    Returns:
        Dict with keys:
            - plan: Generated repair plan (detailed instructions)
            - reasoning: Chain-of-thought reasoning
            - cost: API cost in dollars
            - error: Error message if any
            - examples_used: Number of examples used from knowledge pool
            - model: Model used
    """

    # Initialize ThinkRepair
    repairer = ThinkRepairCI(
        model=model,
        k_shot=k_shot,
        knowledge_pool_path=knowledge_pool_path
    )

    # Prepare context
    context = {
        "ci_logs": issue_description,
        "changed_files": changed_files,
        "repo_path": repo_path,
        "diff": diff,
        "workflow": workflow,
        "sha_fail": sha_fail,
        "instance_id": instance_id
    }

    # Generate plan
    try:
        result = repairer.generate_plan(context)
        return result
    except Exception as e:
        error_msg = str(e)

        # Check if it's a context length error
        if "context length" in error_msg.lower() or "maximum context" in error_msg.lower():
            print(f"  Context too large for instance {instance_id} - SKIPPING")
            return {
                "plan": "",
                "reasoning": "",
                "cost": 0.0,
                "error": "CONTEXT_TOO_LARGE",
                "examples_used": 0,
                "model": model,
                "skipped": True
            }

        # Other errors
        return {
            "plan": "",
            "reasoning": "",
            "cost": 0.0,
            "error": error_msg,
            "examples_used": 0,
            "model": model
        }
