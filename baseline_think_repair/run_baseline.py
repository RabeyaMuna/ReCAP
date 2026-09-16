#!/usr/bin/env python3
"""
Run ThinkRepair baseline on CI-repair benchmark.
Saves results in: results/think_repair/baseline_{model}/preds.json

Usage:
    python baseline_think_repair/run_baseline.py \
        --eval_data data/eval_set.jsonl \
        --model deepseek-v4-flash \
        --k_shot 0
"""

import argparse
import json
import sys
from pathlib import Path
from tqdm import tqdm

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_think_repair.wrapper import generate_patch_thinkrepair


def main():
    parser = argparse.ArgumentParser(description="Run ThinkRepair baseline")
    parser.add_argument("--eval_data", default="data/eval_set.jsonl", help="Path to eval_set.jsonl")
    parser.add_argument("--model", default="deepseek-v4-flash", help="Model to use")
    parser.add_argument("--k_shot", type=int, default=0, help="Number of few-shot examples (0=zero-shot)")
    parser.add_argument("--max_interactions", type=int, default=5, help="Max iterations")
    parser.add_argument("--knowledge_pool", default=None, help="Path to knowledge pool JSON")
    parser.add_argument("--start_from", type=str, default=None, help="Start from this instance_id (resume)")

    args = parser.parse_args()

    # Setup output directory
    output_dir = Path(f"results/think_repair/baseline_{args.model}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "preds.json"

    # Load existing results if resuming
    predictions = {}
    if output_file.exists():
        with open(output_file) as f:
            predictions = json.load(f)
        print(f"Loaded {len(predictions)} existing predictions")

    # Load eval data
    with open(args.eval_data) as f:
        instances = [json.loads(line) for line in f if line.strip()]

    print(f"Total instances: {len(instances)}")
    print(f"Model: {args.model}")
    print(f"K-shot: {args.k_shot}")
    print(f"Max interactions: {args.max_interactions}")
    print(f"Output: {output_file}")
    print()

    # Filter instances to process
    start_processing = args.start_from is None
    to_process = []

    for instance in instances:
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        # Skip if already processed
        if instance_id in predictions:
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

    # Run repair on each instance
    total_cost = sum(p.get('cost', 0) for p in predictions.values())

    for instance in tqdm(to_process, desc="Repairing"):
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        # Prepare inputs
        issue_description = '\n'.join(
            f"[{step.get('step_name', 'unknown')}]\n{step.get('log', '')}"
            for step in instance.get('logs', [])
        ) if isinstance(instance.get('logs'), list) else instance.get('logs', '')

        changed_files = instance.get('changed_files', [])
        repo_path = f"/tmp/thinkrepair_repos/{instance['repo_owner']}_{instance['repo_name']}"

        # Run repair
        result = generate_patch_thinkrepair(
            issue_description=issue_description,
            changed_files=changed_files,
            repo_path=repo_path,
            model=args.model,
            diff=instance.get('diff', ''),
            workflow=instance.get('workflow', ''),
            validation_commands=instance.get('validation_commands', ''),
            memory_context={},
            sha_fail=instance['sha_fail'],
            instance_id=instance_id,
            max_interactions=args.max_interactions,
            k_shot=args.k_shot,
            knowledge_pool_path=args.knowledge_pool
        )

        # Store in format matching miniswe-agent baseline
        predictions[instance_id] = {
            "id": instance_id,
            "sha_fail": instance['sha_fail'],
            "diff": result["patch"],
            "cost": result["cost"],
            # Extra info for debugging
            "applicable": result.get("applicable", False),
            "error": result.get("error", ""),
            "interactions": result.get("interactions", 0)
        }

        total_cost += result["cost"]

        # Save incrementally
        with open(output_file, 'w') as f:
            json.dump(predictions, f, indent=2)

    print(f"\nDone! Total cost: ${total_cost:.4f}")
    print(f"Results saved to: {output_file}")

    # Summary
    successful = sum(1 for p in predictions.values() if p["diff"] and not p.get("error"))
    print(f"Generated patches: {successful}/{len(predictions)}")


if __name__ == "__main__":
    main()
