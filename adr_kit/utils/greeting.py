"""Simple greeting functions for workflow testing."""


def greet(name: str) -> str:
    """
    Generate a greeting for the given name.

    Args:
        name: The name to greet

    Returns:
        A friendly greeting string
    """
    if not name:
        raise ValueError("Name cannot be empty")
    return f"Hello, {name}!"
