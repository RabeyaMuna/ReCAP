# CI-Repair Bench

**ANONYMIZED FOR DOUBLE-BLIND PEER REVIEW**

Benchmark for evaluating CI repair agents with hierarchical memory (L1/L2/L3).

**Agents:** Mini-SWE-Agent, Codex  
**Ablations:** BASELINE, L1, L1+L2, L1+L2+L3  
**Directions:** backward, forward, bidirectional  
**Models:** minimax2.5, deepseek-v4-flash, glm5.2, gpt-4o-mini, gpt-5.4-mini

## Setup

```bash
# Method 1: Auto install
bash INSTALL.sh
source .venv-codex/bin/activate

# Method 2: Manual install
python3 -m venv .venv-codex
source .venv-codex/bin/activate
pip install -r requirements.txt
pip install -e ./miniswe-agent

# Configure API keys
cp .env.example .env
# Edit .env: OPENAI_API_KEY, OPENROUTER_API_KEY, HUGGINGFACE_TOKEN
```

## Baseline: ThinkRepair

```bash
# Stage 1: Generate plans
python baseline_think_repair/run_stage1_plans.py \
    --eval_data data/eval_set.jsonl \
    --model minimax-m2_5 \
    --k_shot 2 \
    --knowledge_pool baseline_think_repair/knowledge_pool_minimax.json \
    --output results/thinkrepair_plans/

# Stage 2: Generate patches using plans
python baseline_think_repair/run_stage2_patches.py \
    --plans results/thinkrepair_plans/plans.json \
    --output results/thinkrepair_full/ \
    --model minimax-m2_5

# Or with DeepSeek
python baseline_think_repair/run_stage1_plans.py \
    --eval_data data/eval_set.jsonl \
    --model deepseek-v4-flash \
    --k_shot 2 \
    --knowledge_pool baseline_think_repair/knowledge_pool_deepseek.json \
    --output results/thinkrepair_plans_deepseek/

python baseline_think_repair/run_stage2_patches.py \
    --plans results/thinkrepair_plans_deepseek/plans.json \
    --output results/thinkrepair_deepseek/ \
    --model deepseek-v4-flash
```

## Decompose and Build Memory

```bash
source .venv-codex/bin/activate
set -a && source .env && set +a

# 1. Split dataset
python3 scripts/split_before_decomposition.py

# 2. Decompose (choose direction)
# Backward
python3 scripts/decompose_backward.py --batch --dataset data/memory_set.jsonl --model minimax2.5 --output-dir data/back_trs

# Forward  
python3 scripts/decompose_commits.py --batch --dataset data/memory_set.jsonl --model minimax2.5 --output-dir data/fwr_trs

# Bidirectional
python3 scripts/decompose_bidirectional.py --batch --dataset data/memory_set.jsonl --model minimax2.5 --output-dir data/bidirect_trs
```

## Run Evaluation

### Full Dataset

```bash
# Mini-SWE-Agent
bash ./run_miniswe_direct.sh "" BASELINE none minimax2.5 "" data/eval_set.jsonl 1
bash ./run_miniswe_direct.sh "" L1 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_miniswe_direct.sh "" L1+L2 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_miniswe_direct.sh "" L1+L2+L3 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_miniswe_direct.sh "" L1+L2+L3 forward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_miniswe_direct.sh "" L1+L2+L3 bidirectional minimax2.5 "" data/eval_set.jsonl 1

# Codex Agent
bash ./run_codex_direct.sh "" baseline none minimax2.5 "" data/eval_set.jsonl 1
bash ./run_codex_direct.sh "" L1 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_codex_direct.sh "" L1+L2 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_codex_direct.sh "" L1+L2+L3 backward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_codex_direct.sh "" L1+L2+L3 forward minimax2.5 "" data/eval_set.jsonl 1
bash ./run_codex_direct.sh "" L1+L2+L3 bidirectional minimax2.5 "" data/eval_set.jsonl 1
```

### Partial Dataset (with slice)

```bash
# Mini-SWE-Agent - Direct script with slice
PYTHONPATH=. python scripts/run_miniswe_ci_bench.py \
  --dataset data/eval_set.jsonl \
  --slice "0:200" \
  --ablation L1 \
  --direction bidirectional \
  --model deepseek-v4-flash \
  --workers 1

PYTHONPATH=. python scripts/run_miniswe_ci_bench.py \
  --dataset data/eval_set.jsonl \
  --slice "0:200" \
  --ablation L1+L2 \
  --direction bidirectional \
  --model deepseek-v4-flash \
  --workers 1

PYTHONPATH=. python scripts/run_miniswe_ci_bench.py \
  --dataset data/eval_set.jsonl \
  --slice "0:200" \
  --ablation L1+L2+L3 \
  --direction bidirectional \
  --model deepseek-v4-flash \
  --workers 1

# Codex Agent - With slice parameter
bash ./run_codex_direct.sh "" L1+L2+L3 bidirectional deepseek-v4-flash "" data/eval_set.jsonl "0:200" 1
```

## Script Arguments

```bash
./run_miniswe_direct.sh <issue_ids> <ablation> <direction> <model> <repo_filter> <dataset> <slice> <workers>
./run_codex_direct.sh <issue_ids> <ablation> <direction> <model> <repo_filter> <dataset> <slice> <workers>

# Or direct Python script
PYTHONPATH=. python scripts/run_miniswe_ci_bench.py \
  --dataset <dataset> \
  --slice <slice> \
  --ablation <ablation> \
  --direction <direction> \
  --model <model> \
  --workers <workers>
```

- `issue_ids`: Comma-separated IDs or "" for all
- `ablation`: BASELINE | L1 | L1+L2 | L1+L2+L3
- `direction`: none (baseline only) | backward | forward | bidirectional
- `model`: minimax2.5 | deepseek-v4-flash etc.
- `repo_filter`: Repo name or "" for all
- `dataset`: data/eval_set.jsonl
- `slice`: Dataset slice like "0:200" or "" for all
- `workers`: 1

## Results

```
results/miniswe-agent/<direction>/<ablation>_<model>/predictions.json
results/codex/<direction>/<ablation>_<model>/predictions.json
```
