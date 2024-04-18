from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class ProgressOptions:
    """Options for progress reporting."""

    enabled: bool = True
    task_name: Optional[str] = None
    success_message: str = "Success"
    # If `None`, the error message will be used as the failure message.
    failure_message: Optional[str] = None

    def with_attrs(self, **kwargs) -> "ProgressOptions":
        """Return a new instance with the given attributes replaced."""
        return replace(self, **kwargs)
