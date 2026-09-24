# Codex Agent

**Anonymized for double-blind review.**

This directory contains an implementation of a coding agent that is used as one of the baseline agents in this benchmark. The agent uses the Codex architecture for CI repair tasks.

## Overview

The Codex agent is a coding assistant that can:
- Analyze CI failure logs
- Generate repair patches
- Execute bash commands in sandboxed environments
- Integrate with various LLM backends via LiteLLM

## Usage

See the main project [README.md](../README.md) for instructions on running experiments with the Codex agent.

### Quick Start

```bash
# Run Codex agent with baseline (no memory)
bash ./run_codex_direct.sh "" baseline none <model> "" data/eval_set.jsonl 1

# Run with hierarchical memory
bash ./run_codex_direct.sh "" L1+L2+L3 bidirectional <model> "" data/eval_set.jsonl 1
```

## Configuration

The agent can be configured through:
- `litellm_config.yaml` - Model routing configuration
- Environment variables in `.env`

## Architecture

The Codex agent implements:
- CI failure analysis
- Memory-guided repair (when enabled)
- Patch generation and validation
- Integration with the repository test suite

## License

This implementation is anonymized for peer review purposes.
