#!/usr/bin/env python3
"""
Collection Phase for ThinkRepair Baseline.

Builds knowledge pool from historical CI failures (memory_set.jsonl).
For each historical failure with known fix:
1. Use CI log analyzer to get structured failure description
2. Give LLM: Structured analysis + patch
3. Ask: "Explain the reasoning behind this fix"
4. Store: {analysis, reasoning, patch}

Output: knowledge_pool.json
"""

import argparse
import json
import sys
from pathlib import Path
from tqdm import tqdm
from typing import Dict, List
import litellm
from litellm import completion

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_think_repair.ci_analysis_cache import get_ci_analysis_for_instance


def format_ci_analysis(ci_analysis: Dict) -> str:
    """Format CI analysis dict into readable text."""
    parts = []

    # Error summary
    if ci_analysis.get('error_summary'):
        parts.append(f"**Error Summary:**\n{ci_analysis['error_summary']}\n")

    # Error context
    if ci_analysis.get('error_context'):
        context = ci_analysis['error_context']
        if isinstance(context, list):
            context = '\n'.join(context)
        parts.append(f"**Error Context:**\n{context}\n")

    # Relevant files
    if ci_analysis.get('relevant_files'):
        parts.append("**Relevant Files:**")
        for file_info in ci_analysis['relevant_files'][:5]:
            file_path = file_info.get('file', 'unknown')
            line_num = file_info.get('line_number', '?')
            reason = file_info.get('reason', '')
            parts.append(f"- {file_path}:{line_num}")
            if reason:
                parts.append(f"  {reason}")
        parts.append("")

    # Failure signals
    if ci_analysis.get('failure_signals'):
        parts.append("**Failure Signals:**")
        for signal in ci_analysis['failure_signals'][:5]:
            parts.append(f"- {signal}")
        parts.append("")

    return "\n".join(parts)


def build_reasoning_prompt(ci_analysis_text: str, patch: str, changed_files: List[str]) -> str:
    """
    Build prompt to generate reasoning for a known fix.

    Given: Structured CI failure analysis + the patch that fixed it
    Ask LLM: Explain the reasoning
    """
    return f"""You are an expert at analyzing CI failures and their fixes.

Given a CI failure analysis and the patch that fixed it, explain the reasoning step-by-step.

## CI Failure Analysis
{ci_analysis_text[:3000]}

## Changed Files
{', '.join(changed_files[:10])}

## The Patch That Fixed It
```diff
{patch[:2000]}
```

Analyze this repair. Explain:
1. What caused the CI failure?
2. What does the patch do?
3. Why does this patch fix the failure?
4. What pattern or strategy does this represent?

Let's think step by step."""


def call_llm(prompt: str, model: str = "minimax-m2_5") -> tuple[str, float]:
    """
    Call LLM and return (response, cost).
    """
    try:
        # Map model names
        if model == "deepseek-v4-flash":
            model_name = "openrouter/deepseek/deepseek-chat"
        elif model in ["minimax-m2_5", "minimax-m2.5"]:
            model_name = "openrouter/minimax/minimax-m2.5"
        elif model == "gpt-5.4-mini":
            model_name = "gpt-4o-mini"
        else:
            model_name = model

        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content

        # Calculate cost (rough estimate)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000

        return content, cost

    except Exception as e:
        print(f"LLM call failed: {e}")
        return "", 0.0


def main():
    parser = argparse.ArgumentParser(description="Build ThinkRepair knowledge pool")
    parser.add_argument("--train_data", default="data/memory_set.jsonl",
                       help="Path to memory_set.jsonl (training data)")
    parser.add_argument("--output", default="baseline_think_repair/knowledge_pool.json",
                       help="Output path for knowledge pool")
    parser.add_argument("--model", default="deepseek-v4-flash",
                       help="Model to use for reasoning generation")
    parser.add_argument("--context_model", default="deepseek-v4-flash",
                       help="Model to use for CI log analysis")
    parser.add_argument("--max_examples", type=int, default=None,
                       help="Maximum examples to process (None = all)")
    parser.add_argument("--start_from", type=int, default=0,
                       help="Start from this index (for resuming)")

    args = parser.parse_args()

    # Load existing knowledge pool if resuming
    knowledge_pool = []
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        with open(output_path) as f:
            knowledge_pool = json.load(f)
        print(f"Loaded {len(knowledge_pool)} existing examples")

    # Load training data
    train_data = []
    with open(args.train_data) as f:
        for line in f:
            if line.strip():
                train_data.append(json.loads(line))

    print(f"Total training instances: {len(train_data)}")

    # Limit if specified
    if args.max_examples:
        train_data = train_data[:args.max_examples]
        print(f"Limited to {len(train_data)} examples")

    # Skip already processed
    train_data = train_data[args.start_from:]
    print(f"Processing from index {args.start_from}: {len(train_data)} remaining")

    total_cost = 0.0
    successful = 0
    failed = 0

    # Process each training instance
    for idx, instance in enumerate(tqdm(train_data, desc="Building knowledge pool")):
        try:
            # Extract basic info
            patch = instance.get('diff', '') or instance.get('patch', '')
            changed_files = instance.get('changed_files', [])

            if not patch:
                print(f"\nSkipping instance {idx}: No patch found")
                failed += 1
                continue

            # Get CI analysis (from log_details.json or generate)
            try:
                analysis_text = get_ci_analysis_for_instance(instance, model=args.context_model)
            except Exception as e:
                print(f"\nCI analysis failed for instance {idx}: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
                continue

            if not analysis_text.strip():
                print(f"\nSkipping instance {idx}: Empty CI analysis")
                failed += 1
                continue

            # Build prompt to generate reasoning
            prompt = build_reasoning_prompt(analysis_text, patch, changed_files)

            # Call LLM to generate reasoning
            reasoning, cost = call_llm(prompt, model=args.model)
            total_cost += cost

            if not reasoning:
                print(f"\nFailed to generate reasoning for instance {idx}")
                failed += 1
                continue

            # Add to knowledge pool
            repo_owner = instance.get('repo_owner', 'unknown')
            repo_name = instance.get('repo_name', 'unknown')
            repo = f"{repo_owner}/{repo_name}"

            knowledge_pool.append({
                "id": instance.get('instance_id') or instance.get('id') or str(idx),
                "analysis": analysis_text[:3000],  # Structured CI analysis
                "reasoning": reasoning,  # LLM-generated reasoning
                "patch": patch[:2000],  # Truncate to save space
                "changed_files": changed_files[:10],  # Limit files
                "repo": repo,
                "sha_fail": instance.get('sha_fail', '')
            })

            successful += 1

            # Save incrementally every 10 examples
            if (idx + 1) % 10 == 0:
                with open(output_path, 'w') as f:
                    json.dump(knowledge_pool, f, indent=2)
                print(f"\nSaved checkpoint: {len(knowledge_pool)} examples, cost so far: ${total_cost:.4f}")

        except Exception as e:
            print(f"\nError processing instance {idx}: {e}")
            failed += 1
            continue

    # Final save
    with open(output_path, 'w') as f:
        json.dump(knowledge_pool, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Knowledge Pool Built Successfully!")
    print(f"{'='*60}")
    print(f"Output: {output_path}")
    print(f"Total examples: {len(knowledge_pool)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
