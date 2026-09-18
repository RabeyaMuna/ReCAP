#!/usr/bin/env python3
"""
ThinkRepair + MiniSWEAgent Integration

Complete flow:
1. ThinkRepair generates repair plans using knowledge pool
2. Plans are passed to MiniSWEAgent for patch generation
3. Results saved with both plan and patch

Usage:
    python baseline_think_repair/run_thinkrepair_miniswe.py \
        --eval_data data/eval_set.jsonl \
        --model minimax-m2_5 \
        --k_shot 2 \
        --knowledge_pool baseline_think_repair/knowledge_pool_minimax.json \
        --output results/thinkrepair_full/
"""

import argparse
import json
import sys
import subprocess
import tempfile
from pathlib import Path
from tqdm import tqdm

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_think_repair.wrapper import generate_plan_thinkrepair
from baseline_think_repair.ci_analysis_cache import get_ci_analysis_for_instance


def run_minisweagent_on_plan(
    instance: dict,
    plan: str,
    output_dir: Path,
    model: str = "minimax-m2_5"
) -> dict:
    """
    Run minisweagent on a single instance with ThinkRepair's plan.

    Args:
        instance: Instance data
        plan: ThinkRepair generated plan
        output_dir: Output directory
        model: Model to use

    Returns:
        Result dict with patch
    """
    instance_id = str(instance.get('instance_id') or instance.get('id'))

    # Create temp file with single instance + plan
    temp_instance = dict(instance)
    temp_instance['thinkrepair_plan'] = plan  # Add plan to instance

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(temp_instance) + '\n')
        temp_file = f.name

    try:
        # Run minisweagent on this instance
        cmd = [
            'mini-swe-agent', 'cibench',
            '--dataset', temp_file,
            '--output', str(output_dir / 'miniswe_temp'),
            '-m', f'openrouter/{model}',
            '--no-memory-enabled',  # Baseline without memory
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes per instance
        )

        # Load generated patch
        preds_file = output_dir / 'miniswe_temp' / 'preds.json'
        if preds_file.exists():
            with open(preds_file) as f:
                preds = json.load(f)
                if instance_id in preds:
                    return preds[instance_id]

        return {
            "id": instance_id,
            "diff": "",
            "error": "No patch generated",
            "sha_fail": instance.get('sha_fail', '')
        }

    except subprocess.TimeoutExpired:
        return {
            "id": instance_id,
            "diff": "",
            "error": "Timeout",
            "sha_fail": instance.get('sha_fail', '')
        }
    except Exception as e:
        return {
            "id": instance_id,
            "diff": "",
            "error": str(e),
            "sha_fail": instance.get('sha_fail', '')
        }
    finally:
        # Cleanup temp file
        import os
        try:
            os.unlink(temp_file)
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description="Run ThinkRepair + MiniSWEAgent integration")
    parser.add_argument("--eval_data", default="data/eval_set.jsonl", help="Path to eval_set.jsonl")
    parser.add_argument("--model", default="minimax-m2_5", help="Model to use (default: minimax-m2_5)")
    parser.add_argument("--k_shot", type=int, default=2, help="Number of few-shot examples")
    parser.add_argument("--knowledge_pool", default="baseline_think_repair/knowledge_pool_minimax.json",
                        help="Path to knowledge pool JSON")
    parser.add_argument("--output", default="results/thinkrepair_full/", help="Output directory")
    parser.add_argument("--start_from", type=str, default=None, help="Start from this instance_id (resume)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of instances")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip instances that already have patches (default: True)")

    args = parser.parse_args()

    # Setup output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    plans_file = output_dir / "plans.json"
    results_file = output_dir / "preds.json"

    # Load existing results if resuming
    plans = {}
    results = {}

    if plans_file.exists():
        with open(plans_file) as f:
            plans = json.load(f)
        print(f"Loaded {len(plans)} existing plans")

    if results_file.exists():
        with open(results_file) as f:
            results = json.load(f)
        print(f"Loaded {len(results)} existing results")

    # Load eval data
    with open(args.eval_data) as f:
        instances = [json.loads(line) for line in f if line.strip()]

    if args.limit:
        instances = instances[:args.limit]

    print("="*60)
    print("ThinkRepair + MiniSWEAgent Integration")
    print("="*60)
    print(f"Total instances: {len(instances)}")
    print(f"Model: {args.model}")
    print(f"K-shot: {args.k_shot}")
    print(f"Knowledge pool: {args.knowledge_pool}")
    print(f"Output: {output_dir}")
    print()

    # Filter instances to process
    start_processing = args.start_from is None
    to_process = []
    skipped_existing = 0

    for instance in instances:
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        # Skip if already has patch (resume capability)
        if args.skip_existing and instance_id in results:
            # Check if patch exists
            if results[instance_id].get('diff'):
                skipped_existing += 1
                continue

        # Skip until we reach start_from
        if not start_processing:
            if instance_id == args.start_from:
                start_processing = True
            else:
                continue

        to_process.append(instance)

    if skipped_existing > 0:
        print(f"Skipped {skipped_existing} instances with existing patches")
    print(f"Instances to process: {len(to_process)}")

    if not to_process:
        print("No instances to process!")
        return

    # Process each instance
    total_cost = sum(p.get('cost', 0) for p in plans.values())

    for instance in tqdm(to_process, desc="Processing"):
        instance_id = str(instance.get('instance_id') or instance.get('id') or instance['sha_fail'])

        print(f"\n{'='*60}")
        print(f"Processing: {instance_id}")
        print(f"{'='*60}")

        # ────────────────────────────────────────────────────────────
        # STEP 1: Generate Plan with ThinkRepair
        # ────────────────────────────────────────────────────────────

        if instance_id not in plans:
            print(f"[1/2] Generating plan with ThinkRepair...")

            try:
                # Get CI analysis
                issue_description = get_ci_analysis_for_instance(instance, model=args.model)

                # Generate plan
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

                plans[instance_id] = {
                    "id": instance_id,
                    "sha_fail": instance.get('sha_fail', ''),
                    "repo": f"{instance.get('repo_owner')}/{instance.get('repo_name')}",
                    "plan": plan_result["plan"],
                    "reasoning": plan_result["reasoning"],
                    "cost": plan_result["cost"],
                    "error": plan_result.get("error", ""),
                    "examples_used": plan_result.get("examples_used", 0),
                    "model": args.model
                }

                total_cost += plan_result["cost"]

                # Save plan incrementally
                with open(plans_file, 'w') as f:
                    json.dump(plans, f, indent=2)

                print(f"✓ Plan generated (${plan_result['cost']:.4f}, {plan_result.get('examples_used', 0)} examples)")
                print(f"Plan preview: {plan_result['plan'][:200]}...")

            except Exception as e:
                print(f"✗ Plan generation failed: {e}")
                plans[instance_id] = {
                    "id": instance_id,
                    "plan": "",
                    "error": str(e),
                    "cost": 0.0
                }
                with open(plans_file, 'w') as f:
                    json.dump(plans, f, indent=2)
                continue
        else:
            print(f"[1/2] Plan already exists, skipping...")

        # ────────────────────────────────────────────────────────────
        # STEP 2: Generate Patch with MiniSWEAgent using Plan
        # ────────────────────────────────────────────────────────────

        print(f"[2/2] Generating patch with MiniSWEAgent using plan...")

        plan = plans[instance_id].get('plan', '')
        if not plan:
            print(f"✗ No plan available, skipping patch generation")
            results[instance_id] = {
                "id": instance_id,
                "sha_fail": instance.get('sha_fail', ''),
                "diff": "",
                "error": "No plan available",
                "plan_cost": 0.0
            }
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            continue

        try:
            # Run minisweagent with the plan
            patch_result = run_minisweagent_on_plan(
                instance=instance,
                plan=plan,
                output_dir=output_dir,
                model=args.model
            )

            # Combine plan and patch results
            results[instance_id] = {
                "id": instance_id,
                "sha_fail": instance.get('sha_fail', ''),
                "repo": f"{instance.get('repo_owner')}/{instance.get('repo_name')}",
                "diff": patch_result.get('diff', ''),
                "error": patch_result.get('error', ''),
                "plan": plan,
                "plan_cost": plans[instance_id].get('cost', 0.0),
                "examples_used": plans[instance_id].get('examples_used', 0),
                "model": args.model
            }

            # Save result incrementally
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)

            if patch_result.get('diff'):
                print(f"✓ Patch generated ({len(patch_result['diff'])} chars)")
            else:
                print(f"✗ No patch generated: {patch_result.get('error', 'unknown error')}")

        except Exception as e:
            print(f"✗ Patch generation failed: {e}")
            results[instance_id] = {
                "id": instance_id,
                "sha_fail": instance.get('sha_fail', ''),
                "diff": "",
                "error": f"Patch generation failed: {e}",
                "plan": plan,
                "plan_cost": plans[instance_id].get('cost', 0.0)
            }
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)

    # Final summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Plans generated: {len([p for p in plans.values() if p.get('plan')])} / {len(plans)}")
    print(f"Patches generated: {len([r for r in results.values() if r.get('diff')])} / {len(results)}")
    print(f"\nResults saved to:")
    print(f"  Plans: {plans_file}")
    print(f"  Patches: {results_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
