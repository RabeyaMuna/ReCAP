#!/usr/bin/env python3
"""
Run ThinkRepair baseline: Generate plans that are passed to minisweagent.

Flow:
1. ThinkRepair generates plan using knowledge pool
2. Plan is passed to minisweagent for patch generation
3. Results saved in: results/think_repair/baseline_{model}/

Usage:
    python baseline_think_repair/run_baseline.py \
        --eval_data data/eval_set.jsonl \
        --model minimax-m2_5 \
        --k_shot 2 \
        --knowledge_pool baseline_think_repair/knowledge_pool_minimax.json
"""

import argparse
import json
import sys
from pathlib import Path
from tqdm import tqdm

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_think_repair.wrapper import generate_plan_thinkrepair


def main():
    parser = argparse.ArgumentParser(description="Run ThinkRepair baseline (plan generation)")
    parser.add_argument("--eval_data", default="data/eval_set.jsonl", help="Path to eval_set.jsonl")
    parser.add_argument("--model", default="minimax-m2_5", help="Model to use")
    parser.add_argument("--k_shot", type=int, default=2, help="Number of few-shot examples (0=zero-shot)")
    parser.add_argument("--knowledge_pool", default="baseline_think_repair/knowledge_pool_minimax.json",
                        help="Path to knowledge pool JSON")
    parser.add_argument("--start_from", type=str, default=None, help="Start from this instance_id (resume)")
    parser.add_argument("--output_dir", default=None, help="Output directory (default: results/think_repair/baseline_{model})")

    args = parser.parse_args()

    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(f"results/think_repair/baseline_{args.model}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save plans separately from patches
    plans_file = output_dir / "plans.json"

    # Load existing plans if resuming
    plans = {}
    if plans_file.exists():
        with open(plans_file) as f:
            plans = json.load(f)
        print(f"Loaded {len(plans)} existing plans")

    # Load eval data
    with open(args.eval_data) as f:
        instances = [json.loads(line) for line in f if line.strip()]

    print(f"Total instances: {len(instances)}")
    print(f"Model: {args.model}")
    print(f"K-shot: {args.k_shot}")
    print(f"Knowledge pool: {args.knowledge_pool}")
    print(f"Output: {plans_file}")
    print()

    # Filter instances to process
    start_processing = args.start_from is None
    to_process = []

    for instance in instances:
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        # Skip if already processed
        if instance_id in plans:
            continue

        # Skip until we reach start_from
        if not start_processing:
            if instance_id == args.start_from:
                start_processing = True
            else:
                continue

        to_process.append(instance)

    print(f"Instances to process: {len(to_process)}")

    if not to_process:
        print("No instances to process!")
        return

    # Generate plans for each instance
    total_cost = sum(p.get('cost', 0) for p in plans.values())

    for instance in tqdm(to_process, desc="Generating plans"):
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        # Get CI analysis
        try:
            from baseline_think_repair.ci_analysis_cache import get_ci_analysis_for_instance
            issue_description = get_ci_analysis_for_instance(instance, model=args.model)
        except Exception as e:
            print(f"\nWarning: CI analysis failed for {instance_id}, using raw logs: {e}")
            # Fallback to raw logs
            issue_description = '\n'.join(
                f"[{step.get('step_name', 'unknown')}]\n{step.get('log', '')}"
                for step in instance.get('logs', [])
            ) if isinstance(instance.get('logs'), list) else instance.get('logs', '')

        changed_files = instance.get('changed_files', [])
        repo_owner = instance.get('repo_owner', 'unknown')
        repo_name = instance.get('repo_name', 'unknown')
        repo_path = f"/tmp/thinkrepair_repos/{repo_owner}_{repo_name}"

        # Generate plan using ThinkRepair
        try:
            result = generate_plan_thinkrepair(
                issue_description=issue_description,
                changed_files=changed_files,
                repo_path=repo_path,
                model=args.model,
                diff=instance.get('diff', ''),
                workflow=instance.get('workflow', ''),
                sha_fail=instance.get('sha_fail', ''),
                instance_id=instance_id,
                k_shot=args.k_shot,
                knowledge_pool_path=args.knowledge_pool
            )
        except Exception as e:
            print(f"\nError processing {instance_id}: {e}")
            result = {
                "plan": "",
                "reasoning": "",
                "cost": 0.0,
                "error": str(e),
                "examples_used": 0,
                "model": args.model
            }

        # Store plan with metadata
        plans[instance_id] = {
            "id": instance_id,
            "sha_fail": instance.get('sha_fail', ''),
            "repo": f"{repo_owner}/{repo_name}",
            "plan": result["plan"],
            "reasoning": result["reasoning"],
            "cost": result["cost"],
            "error": result.get("error", ""),
            "examples_used": result.get("examples_used", 0),
            "model": result.get("model", args.model),
            # Keep instance info for minisweagent
            "changed_files": changed_files,
            "diff": instance.get('diff', ''),
            "workflow": instance.get('workflow', '')
        }

        total_cost += result["cost"]

        # Save incrementally
        with open(plans_file, 'w') as f:
            json.dump(plans, f, indent=2)

        print(f"\nProcessed {instance_id}: plan={'✓' if result['plan'] else '✗'}, cost=${result['cost']:.4f}, examples={result.get('examples_used', 0)}")

    print(f"\nDone! Total cost: ${total_cost:.4f}")
    print(f"Plans saved to: {plans_file}")

    # Summary
    successful = sum(1 for p in plans.values() if p["plan"] and not p.get("error"))
    print(f"Generated plans: {successful}/{len(plans)}")
    print()
    print("Next step: Pass these plans to minisweagent for patch generation")


if __name__ == "__main__":
    main()
