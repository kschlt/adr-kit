"""Unit tests for greeting utility functions."""

import pytest

from adr_kit.utils.greeting import farewell, greet


def test_greet_with_valid_name():
    """Test that greet() returns a proper greeting."""
    result = greet("Alice")
    assert result == "Hello, Alice!"


def test_greet_with_different_names():
    """Test that greet() works with various names."""
    assert greet("Bob") == "Hello, Bob!"
    assert greet("Charlie") == "Hello, Charlie!"


def test_greet_with_empty_name_raises_error():
    """Test that greet() raises ValueError for empty name."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        greet("")


def test_farewell_with_valid_name():
    """Test that farewell() returns a proper farewell message."""
    result = farewell("Alice")
    assert result == "Goodbye, Alice!"


def test_farewell_with_different_names():
    """Test that farewell() works with various names."""
    assert farewell("Bob") == "Goodbye, Bob!"
    assert farewell("Charlie") == "Goodbye, Charlie!"


def test_farewell_with_empty_name_raises_error():
    """Test that farewell() raises ValueError for empty name."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        farewell("")
