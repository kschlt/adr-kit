"""Unit tests for greeting utility functions."""

import pytest

from adr_kit.utils.greeting import farewell, greet, greet_all


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


def test_greet_all_with_single_name():
    """Test that greet_all() handles a single name."""
    result = greet_all(["Alice"])
    assert result == "Hello, Alice!"


def test_greet_all_with_two_names():
    """Test that greet_all() handles two names."""
    result = greet_all(["Alice", "Bob"])
    assert result == "Hello, Alice and Bob!"


def test_greet_all_with_multiple_names():
    """Test that greet_all() handles multiple names."""
    result = greet_all(["Alice", "Bob", "Charlie"])
    assert result == "Hello, Alice, Bob, and Charlie!"


def test_greet_all_with_empty_list_raises_error():
    """Test that greet_all() raises ValueError for empty list."""
    with pytest.raises(ValueError, match="Names list cannot be empty"):
        greet_all([])


def test_greet_all_with_empty_name_in_list_raises_error():
    """Test that greet_all() raises ValueError for empty name in list."""
    with pytest.raises(ValueError, match="Individual names cannot be empty"):
        greet_all(["Alice", "", "Bob"])


def test_greet_all_with_four_names():
    """Test that greet_all() handles four names correctly."""
    result = greet_all(["Alice", "Bob", "Charlie", "Diana"])
    assert result == "Hello, Alice, Bob, Charlie, and Diana!"
