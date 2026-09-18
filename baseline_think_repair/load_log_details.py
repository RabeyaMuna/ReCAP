"""
Utility to load and match log details with instances.
"""

import json
from typing import Dict, Optional


class LogDetailsLoader:
    """Load and lookup log details for CI issues."""

    def __init__(self, log_details_path: str = "data/log_details.json"):
        """Load log details once."""
        with open(log_details_path) as f:
            self.log_details_list = json.load(f)

        # Build lookup index by sha_fail and id
        self.by_sha = {}
        self.by_id = {}

        for entry in self.log_details_list:
            sha = entry.get('sha_fail')
            issue_id = entry.get('id')

            if sha:
                self.by_sha[sha] = entry
            if issue_id:
                self.by_id[str(issue_id)] = entry

    def get_for_instance(self, instance: Dict) -> Optional[Dict]:
        """
        Get log details for an instance.

        Tries to match by:
        1. sha_fail
        2. id/instance_id
        """
        # Try sha_fail first
        sha = instance.get('sha_fail')
        if sha and sha in self.by_sha:
            return self.by_sha[sha]

        # Try id
        issue_id = str(instance.get('instance_id') or instance.get('id') or '')
        if issue_id and issue_id in self.by_id:
            return self.by_id[issue_id]

        return None

    def format_as_description(self, log_details: Dict) -> str:
        """
        Format log details into a structured description for LLM.

        Returns a clear, structured description of the CI failure.
        """
        parts = []

        # Error context (high-level summary)
        if log_details.get('error_context'):
            context = log_details['error_context'][0] if isinstance(log_details['error_context'], list) else log_details['error_context']
            parts.append(f"## Error Context\n{context}\n")

        # Failure signals (specific errors)
        if log_details.get('failure_signals'):
            signals = log_details['failure_signals']
            if signals:
                parts.append("## Failure Signals")
                for i, signal in enumerate(signals[:5], 1):  # Limit to 5
                    parts.append(f"{i}. {signal}")
                parts.append("")

        # Relevant files (files with issues)
        if log_details.get('relevant_files'):
            files = log_details['relevant_files']
            if files:
                parts.append("## Relevant Files")
                for file_info in files[:10]:  # Limit to 10
                    file_path = file_info.get('file', 'unknown')
                    line_num = file_info.get('line_number', '?')
                    issue_type = file_info.get('issue_type', 'Unknown')
                    reason = file_info.get('reason', 'No reason provided')
                    parts.append(f"- **{file_path}:{line_num}** ({issue_type})")
                    parts.append(f"  {reason}")
                parts.append("")

        # Error types (categorized)
        if log_details.get('error_types'):
            error_types = log_details['error_types']
            if error_types:
                parts.append("## Error Types")
                seen = set()
                for err in error_types[:5]:  # Limit to 5
                    category = err.get('category', 'Unknown')
                    subcategory = err.get('subcategory', '')
                    key = f"{category}:{subcategory}"
                    if key not in seen:
                        parts.append(f"- **{category}**: {subcategory}")
                        seen.add(key)
                parts.append("")

        # Failed job info
        if log_details.get('failed_job'):
            jobs = log_details['failed_job']
            if jobs:
                parts.append("## Failed Job")
                for job_info in jobs[:3]:  # Limit to 3
                    job = job_info.get('job', 'unknown')
                    step = job_info.get('step', 'unknown')
                    command = job_info.get('command', 'unknown')
                    parts.append(f"- Job: {job}")
                    parts.append(f"  Step: {step}")
                    parts.append(f"  Command: `{command}`")
                parts.append("")

        return "\n".join(parts)
