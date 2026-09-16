"""
ThinkRepair wrapper for CI-based repair.
Matches the interface used by ExpeRepair baseline.

Based on ThinkRepair (ISSTA 2024): https://github.com/vinci-grape/ThinkRepair
"""

from typing import Dict, List, Optional
import json
import os
from pathlib import Path

from baseline_think_repair.repair_ci import ThinkRepairCI


def generate_patch_thinkrepair(
    issue_description: str,
    changed_files: List[str],
    repo_path: str,
    model: str = "deepseek-v4-flash",
    diff: str = "",
    workflow: str = "",
    validation_commands: str = "",
    memory_context: Optional[Dict] = None,
    sha_fail: str = "",
    instance_id: str = "",
    max_interactions: int = 5,
    k_shot: int = 2,
    knowledge_pool_path: Optional[str] = None
) -> Dict:
    """
    Generate patch using ThinkRepair approach for CI failures.

    Args:
        issue_description: CI failure logs
        changed_files: List of files changed in failing commit
        repo_path: Path to repository
        model: LLM model to use (deepseek-v4-flash, gpt-5.4-mini, etc.)
        diff: Git diff of changes
        workflow: CI workflow file content
        validation_commands: Commands to validate patch
        memory_context: Memory context (unused for baseline)
        sha_fail: Failing commit SHA
        instance_id: Instance identifier
        max_interactions: Maximum iterations for repair
        k_shot: Number of few-shot examples to use
        knowledge_pool_path: Path to pre-built knowledge pool JSON

    Returns:
        Dict with keys:
            - patch: Generated unified diff patch
            - applicable: Whether patch is applicable
            - cost: API cost in dollars
            - error: Error message if any
            - reasoning: Chain-of-thought reasoning
            - interactions: Number of interactions used
    """

    # Initialize ThinkRepair
    repairer = ThinkRepairCI(
        model=model,
        max_interactions=max_interactions,
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
        "validation_commands": validation_commands,
        "sha_fail": sha_fail,
        "instance_id": instance_id
    }

    # Run repair
    try:
        result = repairer.repair(context)
        return result
    except Exception as e:
        return {
            "patch": "",
            "applicable": False,
            "cost": 0.0,
            "error": str(e),
            "reasoning": "",
            "interactions": 0
        }
