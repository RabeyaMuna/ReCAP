#!/bin/bash
# Complete ThinkRepair + MiniSWEAgent Pipeline
#
# Stage 1: ThinkRepair generates plans using knowledge pool
# Stage 2: MiniSWEAgent generates patches using plans as problem statements

set -e  # Exit on error

LIMIT=${1:-10}  # Default: 10 issues
MODEL=${2:-minimax-m2_5}  # Default: minimax-m2_5

echo "=========================================================="
echo "ThinkRepair + MiniSWEAgent Full Pipeline"
echo "=========================================================="
echo "Issues: $LIMIT"
echo "Model: $MODEL"
echo ""

# ─────────────────────────────────────────────────────────────
# STAGE 1: Generate Plans with ThinkRepair
# ─────────────────────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────"
echo "STAGE 1: Generating plans with ThinkRepair..."
echo "──────────────────────────────────────────────────────────"
echo ""

python baseline_think_repair/run_stage1_plans.py \
    --eval_data data/eval_set.jsonl \
    --model "$MODEL" \
    --k_shot 2 \
    --knowledge_pool baseline_think_repair/knowledge_pool_minimax.json \
    --output results/think_repair/ \
    --limit "$LIMIT"

echo ""
echo "✓ Stage 1 complete: Plans generated"
echo ""

# ─────────────────────────────────────────────────────────────
# STAGE 2: Prepare instances for MiniSWEAgent
# ─────────────────────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────"
echo "STAGE 2: Preparing instances with plans for MiniSWEAgent..."
echo "──────────────────────────────────────────────────────────"
echo ""

python baseline_think_repair/run_stage2_patches.py \
    --plans results/think_repair/plans.json \
    --output results/think_repair/ \
    --model "$MODEL"

echo ""
echo "✓ Stage 2 preparation complete"
echo ""

# ─────────────────────────────────────────────────────────────
# Run MiniSWEAgent with plans as problem statements
# ─────────────────────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────"
echo "Running MiniSWEAgent with ThinkRepair plans..."
echo "──────────────────────────────────────────────────────────"
echo ""

python -m minisweagent.run.benchmarks.cibench \
    --dataset results/think_repair/instances_with_plans.jsonl \
    --output results/think_repair/ \
    -m "openrouter/minimax/minimax-m2.5" \
    --no-memory-enabled

echo ""
echo "=========================================================="
echo "COMPLETE!"
echo "=========================================================="
echo ""
echo "Results:"
echo "  Plans: results/think_repair/plans.json"
echo "  Patches: results/think_repair/preds.json"
echo ""
echo "Check results:"
echo "  # Plans generated"
echo "  cat results/think_repair/plans.json | jq 'length'"
echo "  "
echo "  # Patches generated"
echo "  cat results/think_repair/preds.json | jq 'length'"
echo "  "
echo "  # Successful patches"
echo "  cat results/think_repair/preds.json | jq '[.[] | select(.diff != \"\")] | length'"
echo "=========================================================="
