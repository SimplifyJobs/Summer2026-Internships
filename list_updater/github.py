"""GitHub Actions utility functions."""

import os
import sys
import uuid
from typing import Any


def set_output(key: str, value: Any) -> None:
    """Set a GitHub Actions output variable.

    Args:
        key: The output variable name.
        value: The value to set (will be converted to string).
    """
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as fh:
            # Use delimiter format for multiline values
            delimiter = f"ghadelimiter_{uuid.uuid4()}"
            # Convert value to string and handle multiline
            value_str = str(value)
            if "\n" in value_str or any(char in value_str for char in ["*", "#", "`", "[", "]"]):
                # Use heredoc format for multiline or special character values
                print(f"{key}<<{delimiter}", file=fh)
                print(value_str, file=fh)
                print(delimiter, file=fh)
            else:
                # Simple format for single-line values
                print(f"{key}={value_str}", file=fh)


def fail(why: str) -> None:
    """Set error message and exit with failure.

    Args:
        why: The error message to output.
    """
    set_output("error_message", why)
    sys.exit(1)
