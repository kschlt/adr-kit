"""Unit tests for greeting utility functions."""

import pytest

from adr_kit.utils.greeting import greet


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
