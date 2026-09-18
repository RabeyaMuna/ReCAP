#!/usr/bin/env python3
"""
Stage 2: Generate Patches using ThinkRepair Plans

Takes plans from Stage 1 and passes them to MiniSWEAgent AS problem statements.
The plan is passed in the 'logs' field, just like other baselines pass log details.

MiniSWEAgent will read the plan and generate patches based on it.

Usage:
    python baseline_think_repair/run_stage2_patches.py \
        --plans results/thinkrepair_plans/plans.json \
        --output results/thinkrepair_full/
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Generate patches with MiniSWEAgent using plans")
    parser.add_argument("--plans", required=True, help="Path to plans.json from Stage 1")
    parser.add_argument("--output", default="results/think_repair/", help="Output directory")
    parser.add_argument("--model", default="minimax-m2_5", help="Model for MiniSWEAgent")

    args = parser.parse_args()

    # Load plans
    with open(args.plans) as f:
        plans = json.load(f)

    print("="*60)
    print("STAGE 2: Patch Generation with MiniSWEAgent")
    print("="*60)
    print(f"Plans loaded: {len(plans)}")
    print(f"Plans file: {args.plans}")
    print(f"Output: {args.output}")
    print()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create JSONL file with plans AS problem statements
    instances_with_plans = []

    for instance_id, plan_data in plans.items():
        if not plan_data.get('plan'):
            print(f"⚠ Skipping {instance_id}: No plan available")
            continue

        # Format plan as problem statement for MiniSWEAgent
        # The plan is passed in the 'logs' field (like other baselines do)
        plan_as_problem = f"""# ThinkRepair Repair Plan

{plan_data['plan']}

## Repair Instructions

Follow the plan above to fix the CI failure. The plan was generated using ThinkRepair
with {plan_data.get('examples_used', 0)} similar historical examples from the knowledge pool.

Implement the fix step-by-step as described in the plan.
"""

        # Create instance with plan AS the problem statement
        instance = {
            "id": instance_id,
            "instance_id": instance_id,
            "sha_fail": plan_data.get('sha_fail', ''),
            "repo_owner": plan_data.get('repo_owner', ''),
            "repo_name": plan_data.get('repo_name', ''),
            "workflow": plan_data.get('workflow', ''),
            "workflow_path": plan_data.get('workflow_path', ''),
            "workflow_name": plan_data.get('workflow_name', ''),

            # Pass ThinkRepair plan AS the logs/problem description
            # This is how MiniSWEAgent receives the problem statement
            "logs": plan_as_problem,

            "changed_files": plan_data.get('changed_files', []),
        }

        instances_with_plans.append(instance)

    # Save as JSONL for MiniSWEAgent
    instances_file = output_dir / "instances_with_plans.jsonl"
    with open(instances_file, 'w') as f:
        for instance in instances_with_plans:
            f.write(json.dumps(instance) + '\n')

    print(f"✓ Created {len(instances_with_plans)} instances with plans as problem statements")
    print(f"✓ Saved to: {instances_file}")
    print()
    print("="*60)
    print("NEXT: Run MiniSWEAgent on these instances")
    print("="*60)
    print()
    print("Command:")
    print(f"""
python -m minisweagent.run.benchmarks.cibench \\
    --dataset {instances_file} \\
    --output {output_dir} \\
    -m openrouter/minimax/minimax-m2.5 \\
    --no-memory-enabled
""")
    print()
    print("MiniSWEAgent will:")
    print("  1. Read the ThinkRepair plan from the 'logs' field")
    print("  2. Use it as the problem statement to guide repair")
    print("  3. Generate patches based on the plan")
    print()
    print("After completion, patches will be in:")
    print(f"  {output_dir}/preds.json")
    print("="*60)


if __name__ == "__main__":
    main()
