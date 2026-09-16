"""
ThinkRepair CI Repair Engine.

Adapted from ThinkRepair (ISSTA 2024) for CI-based program repair.
Main logic for collection and fixing phases.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import litellm
from litellm import completion

from baseline_think_repair import prompts


class ThinkRepairCI:
    """
    ThinkRepair adapted for CI failure repair.

    Two-phase approach:
    1. Collection Phase (offline): Build knowledge pool with CoT
    2. Fixing Phase (online): Few-shot selection + iterative repair
    """

    def __init__(
        self,
        model: str = "deepseek-v4-flash",
        max_interactions: int = 5,
        k_shot: int = 2,
        knowledge_pool_path: Optional[str] = None,
        temperature: float = 1.0
    ):
        self.model = model
        self.max_interactions = max_interactions
        self.k_shot = k_shot
        self.temperature = temperature
        self.knowledge_pool = self._load_knowledge_pool(knowledge_pool_path)
        self.total_cost = 0.0

    def _load_knowledge_pool(self, path: Optional[str]) -> List[Dict]:
        """Load pre-built knowledge pool with CoT examples."""
        if path and Path(path).exists():
            with open(path) as f:
                return json.load(f)
        return []

    def _call_llm(self, messages: List[Dict]) -> tuple[str, float]:
        """
        Call LLM and return (response, cost).

        Uses litellm for unified API across models.
        """
        try:
            # Map model names
            if self.model == "deepseek-v4-flash":
                model_name = "openrouter/deepseek/deepseek-chat"
            elif self.model == "gpt-5.4-mini":
                model_name = "gpt-4o-mini"
            else:
                model_name = self.model

            response = completion(
                model=model_name,
                messages=messages,
                temperature=self.temperature
            )

            content = response.choices[0].message.content

            # Calculate cost (rough estimate)
            # Input: $0.15 / 1M tokens, Output: $0.60 / 1M tokens (deepseek-chat)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000

            return content, cost

        except Exception as e:
            print(f"LLM call failed: {e}")
            return "", 0.0

    def _select_examples(self, context: Dict) -> List[Dict]:
        """
        Select few-shot examples from knowledge pool.

        Original ThinkRepair uses:
        - Semantic embeddings (UniXcoder)
        - Contrastive learning (R-Drop)
        - K-means clustering

        For simplicity, we use random selection for baseline.
        TODO: Implement semantic similarity matching.
        """
        if not self.knowledge_pool or self.k_shot == 0:
            return []

        # Simple: take first k examples
        # TODO: Implement cosine similarity on embeddings
        import random
        return random.sample(
            self.knowledge_pool,
            min(self.k_shot, len(self.knowledge_pool))
        )

    def _read_file_contents(self, repo_path: str, files: List[str]) -> Dict[str, str]:
        """Read contents of changed files."""
        contents = {}
        for filepath in files:
            full_path = Path(repo_path) / filepath
            if full_path.exists():
                try:
                    with open(full_path) as f:
                        contents[filepath] = f.read()
                except:
                    contents[filepath] = f"<Could not read {filepath}>"
        return contents

    def repair(self, context: Dict) -> Dict:
        """
        Main repair entry point.

        Args:
            context: Dict with keys:
                - ci_logs: CI failure logs
                - changed_files: List of changed files
                - repo_path: Repository path
                - diff: Git diff
                - workflow: Workflow file
                - validation_commands: Validation commands
                - sha_fail: Failing SHA
                - instance_id: Instance ID

        Returns:
            Dict with patch, cost, reasoning, etc.
        """
        ci_logs = context["ci_logs"]
        changed_files = context["changed_files"]
        repo_path = context["repo_path"]

        # Read file contents
        file_contents = self._read_file_contents(repo_path, changed_files)

        # Select few-shot examples
        examples = self._select_examples(context)

        # Build initial prompt with few-shot
        messages = prompts.build_fixing_prompt_fewshot(
            ci_logs=ci_logs,
            changed_files=changed_files,
            file_contents=file_contents,
            examples=examples
        )

        # Iterative repair with feedback
        for interaction in range(1, self.max_interactions + 1):
            print(f"[ThinkRepair] Interaction {interaction}/{self.max_interactions}")

            # Call LLM
            response, cost = self._call_llm(messages)
            self.total_cost += cost

            if not response:
                return {
                    "patch": "",
                    "applicable": False,
                    "cost": self.total_cost,
                    "error": "LLM call failed",
                    "reasoning": "",
                    "interactions": interaction
                }

            # Extract reasoning and patch
            reasoning, patch = prompts.extract_reasoning_and_patch(response)

            if not patch:
                # No patch generated, try one more time with clarification
                if interaction < self.max_interactions:
                    feedback_msg = prompts.build_feedback_prompt(
                        previous_response=response,
                        error_message="No patch was generated. Please provide a unified diff patch.",
                        interaction_num=interaction + 1
                    )
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": feedback_msg})
                    continue
                else:
                    return {
                        "patch": "",
                        "applicable": False,
                        "cost": self.total_cost,
                        "error": "No patch generated after all interactions",
                        "reasoning": reasoning,
                        "interactions": interaction
                    }

            # Validate patch (basic check)
            # In real ThinkRepair, this runs test suite
            # For baseline, we skip validation and return patch

            # Success!
            return {
                "patch": patch,
                "applicable": True,  # Assume applicable for baseline
                "cost": self.total_cost,
                "error": "",
                "reasoning": reasoning,
                "interactions": interaction
            }

        # Max interactions reached
        return {
            "patch": patch if 'patch' in locals() else "",
            "applicable": False,
            "cost": self.total_cost,
            "error": f"Max interactions ({self.max_interactions}) reached",
            "reasoning": reasoning if 'reasoning' in locals() else "",
            "interactions": self.max_interactions
        }
