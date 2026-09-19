"""
ThinkRepair CI Plan Generator.

Adapted from ThinkRepair (ISSTA 2024) for generating repair plans.
Uses knowledge pool with Chain-of-Thought reasoning to generate plans,
which are then passed to minisweagent for actual patch generation.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import litellm
from litellm import completion


class ThinkRepairCI:
    """
    ThinkRepair adapted for CI failure repair PLAN generation.

    Two-phase approach:
    1. Collection Phase (offline): Build knowledge pool with CoT
    2. Fixing Phase (online): Few-shot selection + plan generation

    Output: A detailed plan/reasoning for minisweagent to execute.
    """

    def __init__(
        self,
        model: str = "minimax-m2_5",
        k_shot: int = 2,
        knowledge_pool_path: Optional[str] = None,
        temperature: float = 0.7
    ):
        self.model = model
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
        """
        try:
            # Map model names
            if self.model == "deepseek-v4-flash":
                model_name = "openrouter/deepseek/deepseek-chat"
            elif self.model in ["minimax-m2_5", "minimax-m2.5"]:
                model_name = "openrouter/minimax/minimax-m2.5"
            elif self.model == "gpt-4o-mini":
                model_name = "gpt-4o-mini"
            else:
                model_name = self.model

            response = completion(
                model=model_name,
                messages=messages,
                temperature=self.temperature
            )

            content = response.choices[0].message.content

            # Calculate cost
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

        For simplicity, uses random selection.
        TODO: Implement semantic similarity matching.
        """
        if not self.knowledge_pool or self.k_shot == 0:
            return []

        import random
        return random.sample(
            self.knowledge_pool,
            min(self.k_shot, len(self.knowledge_pool))
        )

    def _build_plan_prompt(
        self,
        ci_logs: str,
        changed_files: List[str],
        examples: List[Dict]
    ) -> List[Dict]:
        """
        Build prompt for generating repair plan using few-shot examples.
        """
        messages = [
            {"role": "system", "content": "You are an expert at analyzing CI failures and creating detailed repair plans."}
        ]

        # Add few-shot examples from knowledge pool
        for ex in examples:
            ci_info = ex.get('analysis', ex.get('logs', ''))[:800]

            # Truncate reasoning to prevent context overflow
            reasoning = ex.get('reasoning', '')[:3000]  # Limit to ~750 tokens per example

            user_ex = f"""Analyze this CI failure and create a repair plan:

CI Failure Analysis:
{ci_info}

Changed Files: {ex.get('changed_files', [])}

Provide a detailed plan to fix this."""

            # Show the reasoning from knowledge pool (TRUNCATED)
            asst_ex = f"""{reasoning}

Files to modify: {ex.get('changed_files', [])}"""

            messages.append({"role": "user", "content": user_ex})
            messages.append({"role": "assistant", "content": asst_ex})

        # Add target instance
        target_msg = f"""Analyze this CI failure and create a detailed repair plan:

## CI Failure Analysis
{ci_logs[:2000]}

## Changed Files
{changed_files}

INSTRUCTIONS:
Provide a detailed plan with:

1. **Root Cause Analysis**: What exactly is causing the CI failure?

2. **Fix Strategy**: What needs to be changed and why?

3. **Implementation Steps**: Specific step-by-step instructions:
   - Which files to modify
   - What changes to make (be specific about lines/functions)
   - What to add/remove/change

4. **Validation**: How to verify the fix works

Be specific and detailed - this plan will be given to an automated tool to implement.

Let's think step by step."""

        messages.append({"role": "user", "content": target_msg})

        return messages

    def generate_plan(self, context: Dict) -> Dict:
        """
        Generate repair plan using knowledge pool.

        Args:
            context: Dict with keys:
                - ci_logs: CI failure logs
                - changed_files: List of changed files
                - repo_path: Repository path
                - sha_fail: Failing SHA
                - instance_id: Instance ID

        Returns:
            Dict with plan, reasoning, cost, etc.
        """
        ci_logs = context["ci_logs"]
        changed_files = context["changed_files"]

        # Select few-shot examples from knowledge pool
        examples = self._select_examples(context)

        print(f"[ThinkRepair] Using {len(examples)} examples from knowledge pool")

        # Build prompt
        messages = self._build_plan_prompt(
            ci_logs=ci_logs,
            changed_files=changed_files,
            examples=examples
        )

        # Call LLM to generate plan
        print(f"[ThinkRepair] Generating repair plan...")
        response, cost = self._call_llm(messages)
        self.total_cost += cost

        if not response:
            return {
                "plan": "",
                "reasoning": "",
                "cost": self.total_cost,
                "error": "LLM call failed",
                "examples_used": len(examples)
            }

        print(f"[ThinkRepair] ✓ Plan generated (${cost:.4f})")

        # Return plan and metadata
        return {
            "plan": response,  # Full plan text
            "reasoning": response,  # Same for compatibility
            "cost": self.total_cost,
            "error": "",
            "examples_used": len(examples),
            "model": self.model
        }
