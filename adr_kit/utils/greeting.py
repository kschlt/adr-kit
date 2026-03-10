"""Simple greeting functions for workflow testing.

This module provides basic greeting utilities for testing purposes only.
"""


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


def greet_all(names: list[str]) -> str:
    """
    Generate a batch greeting for multiple names.

    Args:
        names: List of names to greet

    Returns:
        A greeting string addressing all names
    """
    if not names:
        raise ValueError("Names list cannot be empty")
    if any(not name for name in names):
        raise ValueError("Individual names cannot be empty")

    if len(names) == 1:
        return f"Hello, {names[0]}!"
    elif len(names) == 2:
        return f"Hello, {names[0]} and {names[1]}!"
    else:
        return f"Hello, {', '.join(names[:-1])}, and {names[-1]}!"
