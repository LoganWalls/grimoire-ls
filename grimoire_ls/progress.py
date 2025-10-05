from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ProgressOptions:
    """Options for progress reporting."""

    enabled: bool = True
    task_name: str | None = None
    success_message: str = "Success"
    # If `None`, the error message will be used as the failure message.
    failure_message: str | None = None

    def with_attrs(self, **kwargs: str | bool) -> "ProgressOptions":
        """Return a new instance with the given attributes replaced."""
        return replace(self, **kwargs)
