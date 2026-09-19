#!/usr/bin/env python3
"""
Stage 1: ThinkRepair Plan Generation ONLY

ThinkRepair uses knowledge pool to generate repair plans.
NO patch generation here - just plans.

Plans are then passed to MiniSWEAgent in Stage 2 as problem statements.

Usage:
    python baseline_think_repair/run_stage1_plans.py \
        --eval_data data/eval_set.jsonl \
        --model minimax-m2_5 \
        --limit 10
"""

import argparse
import json
import sys
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_think_repair.wrapper import generate_plan_thinkrepair
from baseline_think_repair.ci_analysis_cache import get_ci_analysis_for_instance


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Generate ThinkRepair plans")
    parser.add_argument("--eval_data", default="data/eval_set.jsonl")
    parser.add_argument("--model", default="minimax-m2_5")
    parser.add_argument("--k_shot", type=int, default=2)
    parser.add_argument("--knowledge_pool", default="baseline_think_repair/knowledge_pool_minimax.json")
    parser.add_argument("--output", default="results/think_repair/")
    parser.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    plans_file = output_dir / "plans.json"

    # Load existing plans
    plans = {}
    if plans_file.exists():
        with open(plans_file) as f:
            plans = json.load(f)
        print(f"Loaded {len(plans)} existing plans")

    # Load eval data
    with open(args.eval_data) as f:
        instances = [json.loads(line) for line in f if line.strip()]

    if args.limit:
        instances = instances[:args.limit]

    print("="*60)
    print("STAGE 1: ThinkRepair Plan Generation")
    print("="*60)
    print(f"Total instances: {len(instances)}")
    print(f"Model: {args.model}")
    print(f"K-shot: {args.k_shot}")
    print(f"Output: {plans_file}")
    print()

    # Filter to unprocessed
    to_process = []
    for instance in instances:
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])
        if instance_id not in plans or not plans[instance_id].get('plan'):
            to_process.append(instance)

    print(f"Instances to process: {len(to_process)}")

    if not to_process:
        print("All plans already generated!")
        return

    # Generate plans
    total_cost = sum(p.get('cost', 0) for p in plans.values())

    for instance in tqdm(to_process, desc="Generating plans"):
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        try:
            # Get CI analysis
            issue_description = get_ci_analysis_for_instance(instance, model=args.model)

            # Generate plan with ThinkRepair
            plan_result = generate_plan_thinkrepair(
                issue_description=issue_description,
                changed_files=instance.get('changed_files', []),
                repo_path=f"/tmp/thinkrepair_repos/{instance.get('repo_owner')}_{instance.get('repo_name')}",
                model=args.model,
                diff=instance.get('diff', ''),
                workflow=instance.get('workflow', ''),
                sha_fail=instance.get('sha_fail', ''),
                instance_id=instance_id,
                k_shot=args.k_shot,
                knowledge_pool_path=args.knowledge_pool
            )

            # Extract repo owner and name
            repo_owner = instance.get('repo_owner')
            repo_name = instance.get('repo_name')

            # If not present, parse from 'repo' field (format: "owner/name")
            if not repo_owner or not repo_name:
                repo = instance.get('repo', '')
                if '/' in repo:
                    repo_owner, repo_name = repo.split('/', 1)
                else:
                    repo_owner = repo_owner or ''
                    repo_name = repo_name or ''

            # Save plan with all metadata needed for Stage 2
            plans[instance_id] = {
                "id": instance_id,
                "instance_id": instance_id,
                "sha_fail": instance.get('sha_fail', ''),
                "repo": f"{repo_owner}/{repo_name}",
                "repo_owner": repo_owner,
                "repo_name": repo_name,

                # ThinkRepair outputs
                "plan": plan_result["plan"],
                "reasoning": plan_result["reasoning"],
                "cost": plan_result["cost"],
                "error": plan_result.get("error", ""),
                "examples_used": plan_result.get("examples_used", 0),
                "model": args.model,

                # Original instance data (needed for Stage 2)
                "changed_files": instance.get('changed_files', []),
                "workflow": instance.get('workflow', ''),
                "workflow_path": instance.get('workflow_path', ''),
                "workflow_name": instance.get('workflow_name', ''),
                "logs": instance.get('logs', [])
            }

            total_cost += plan_result["cost"]

            # Save incrementally
            with open(plans_file, 'w') as f:
                json.dump(plans, f, indent=2)

        except Exception as e:
            print(f"\n✗ Error on {instance_id}: {e}")
            plans[instance_id] = {
                "id": instance_id,
                "plan": "",
                "error": str(e),
                "cost": 0.0
            }
            with open(plans_file, 'w') as f:
                json.dump(plans, f, indent=2)

    # Also create instances_with_plans.jsonl (ready for cibench)
    print(f"\nCreating instances file for MiniSWEAgent...")
    instances_file = output_dir / "instances_with_plans.jsonl"
    instances_with_plans = []

    for instance_id, plan_data in plans.items():
        if not plan_data.get('plan'):
            continue  # Skip instances without plans

        # Format plan as problem statement
        plan_as_problem = f"""# ThinkRepair Repair Plan

{plan_data['plan']}

## Repair Instructions

Follow the plan above to fix the CI failure. The plan was generated using ThinkRepair
with {plan_data.get('examples_used', 0)} similar historical examples from the knowledge pool.

Implement the fix step-by-step as described in the plan.
"""

        instance = {
            "id": instance_id,
            "instance_id": instance_id,
            "sha_fail": plan_data.get('sha_fail', ''),
            "repo_owner": plan_data.get('repo_owner', ''),
            "repo_name": plan_data.get('repo_name', ''),
            "workflow": plan_data.get('workflow', ''),
            "workflow_path": plan_data.get('workflow_path', ''),
            "workflow_name": plan_data.get('workflow_name', ''),
            "logs": plan_as_problem,  # Plan as problem statement
            "changed_files": plan_data.get('changed_files', []),
        }

        instances_with_plans.append(instance)

    with open(instances_file, 'w') as f:
        for inst in instances_with_plans:
            f.write(json.dumps(inst) + '\n')

    print(f"✓ Created {len(instances_with_plans)} instances ready for MiniSWEAgent")

    print(f"\n{'='*60}")
    print("STAGE 1 COMPLETE")
    print(f"{'='*60}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Plans generated: {len([p for p in plans.values() if p.get('plan')])} / {len(plans)}")
    print(f"Plans saved to: {plans_file}")
    print(f"Instances ready: {instances_file}")
    print()
    print("✓ Next step: Run MiniSWEAgent directly")
    print(f"  python3 -m minisweagent.run.benchmarks.cibench \\")
    print(f"    --dataset {instances_file} \\")
    print(f"    --output {output_dir} \\")
    print(f"    -m openrouter/minimax/minimax-m2.5 \\")
    print(f"    --no-memory-enabled")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
