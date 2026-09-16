"""
Prompt templates for ThinkRepair adapted for CI failures.

Based on ThinkRepair (ISSTA 2024) prompt structure:
1. Role Designation
2. Task Description
3. Input Context (buggy function → CI logs + files)
4. Chain-of-Thought Indicator ("Let's think step by step")
"""

from typing import Dict, List


def build_system_prompt() -> str:
    """System message defining the role."""
    return "You are an Automated Program Repair tool specialized in fixing CI failures."


def build_collection_prompt(ci_logs: str, changed_files: List[str],
                            file_contents: Dict[str, str]) -> str:
    """
    Collection phase prompt for building knowledge pool.
    Used offline to generate CoT examples from training data.

    Analogous to ThinkRepair's collection phase but for CI context.
    """
    files_text = "\n\n".join(
        f"### File: {filepath}\n```\n{content[:2000]}\n```"  # Limit file size
        for filepath, content in file_contents.items()
    )

    return f"""// Provide a fix for the buggy function
// CI Failure Logs
{ci_logs[:2000]}

// Changed Files
{changed_files}

// File Contents
{files_text}

Let's think step by step."""


def build_fixing_prompt_fewshot(
    ci_logs: str,
    changed_files: List[str],
    file_contents: Dict[str, str],
    examples: List[Dict]
) -> List[Dict]:
    """
    Fixing phase prompt with few-shot examples.

    Returns OpenAI-style message list with:
    - System message
    - Few-shot examples (user/assistant pairs)
    - Target instance (user message)

    Args:
        ci_logs: Current CI failure logs
        changed_files: Files modified
        file_contents: Content of changed files
        examples: List of {logs, reasoning, patch} from knowledge pool
    """
    messages = [
        {"role": "system", "content": build_system_prompt()}
    ]

    # Add few-shot examples
    for ex in examples:
        # User message: buggy context
        user_msg = f"""// Provide a fix for the buggy function
// CI Failure Logs
{ex['logs'][:1000]}

// Changed Files
{ex.get('changed_files', [])}

Let's think step by step."""

        # Assistant message: reasoning + fix
        assistant_msg = f"""{ex['reasoning']}

// Fixed Function
{ex['patch']}"""

        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})

    # Add target instance
    files_text = "\n\n".join(
        f"### File: {filepath}\n```\n{content[:2000]}\n```"
        for filepath, content in file_contents.items()
    )

    target_msg = f"""// Provide a fix for the buggy function
// CI Failure Logs
{ci_logs[:2000]}

// Changed Files
{changed_files}

// File Contents
{files_text}

Let's think step by step."""

    messages.append({"role": "user", "content": target_msg})

    return messages


def build_feedback_prompt(
    previous_response: str,
    error_message: str,
    interaction_num: int
) -> str:
    """
    Interaction feedback prompt when patch fails validation.

    Analogous to ThinkRepair's interaction verification phase.
    """
    return f"""The previous patch is still not correct.

// Previous Reasoning and Patch
{previous_response}

// Validation Error (Iteration {interaction_num})
{error_message}

Please fix it again. Analyze why the previous patch failed and provide a corrected version.

Let's think step by step."""


def extract_reasoning_and_patch(response: str) -> tuple[str, str]:
    """
    Extract reasoning and patch from LLM response.

    Returns:
        (reasoning, patch) tuple
    """
    # Look for "// Fixed Function" marker (ThinkRepair format)
    if "// Fixed Function" in response:
        split_point = response.find("// Fixed Function")
        reasoning = response[:split_point].strip()
        patch = response[split_point:].replace("// Fixed Function", "").strip()
    # Look for diff blocks
    elif "```diff" in response:
        split_point = response.find("```diff")
        reasoning = response[:split_point].strip()
        patch_start = split_point + 7
        patch_end = response.find("```", patch_start)
        patch = response[patch_start:patch_end].strip() if patch_end > patch_start else ""
    # Look for code blocks
    elif "```" in response:
        parts = response.split("```")
        reasoning = parts[0].strip()
        # Find the code part (usually the last code block)
        patch = ""
        for i, part in enumerate(parts):
            if i > 0 and i % 2 == 1:  # Odd indices are inside code blocks
                patch = part.strip()
    else:
        # No clear separation, treat all as reasoning
        reasoning = response.strip()
        patch = ""

    return reasoning, patch
