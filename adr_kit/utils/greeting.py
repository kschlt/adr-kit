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


def farewell(name: str) -> str:
    """
    Generate a farewell message for the given name.

    Args:
        name: The name to bid farewell

    Returns:
        A farewell message string
    """
    if not name:
        raise ValueError("Name cannot be empty")
    return f"Goodbye, {name}!"
