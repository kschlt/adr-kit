"""Tests for ADR parsing functionality."""

import pytest
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from adr_kit.core.parse import (
    parse_front_matter, 
    parse_adr_content, 
    parse_adr_file,
    find_adr_files,
    ParseError
)
from adr_kit.core.model import ADRStatus


class TestParseFrontMatter:
    """Test front-matter parsing."""
    
    def test_valid_front_matter(self):
        """Test parsing valid YAML front-matter."""
        content = """---
id: ADR-0001
title: Use React Query
status: accepted
date: 2025-09-03
tags: [frontend, data]
---

# Decision

Use React Query for data fetching."""
        
        front_matter, markdown = parse_front_matter(content)
        
        assert front_matter["id"] == "ADR-0001"
        assert front_matter["title"] == "Use React Query"
        assert front_matter["status"] == "accepted"
        assert front_matter["date"] == date(2025, 9, 3)
        assert front_matter["tags"] == ["frontend", "data"]
        assert markdown == "# Decision\n\nUse React Query for data fetching."
    
    def test_missing_front_matter(self):
        """Test that missing front-matter raises ParseError."""
        content = "# Just markdown content"
        
        with pytest.raises(ParseError, match="No YAML front-matter found"):
            parse_front_matter(content)
    
    def test_invalid_yaml(self):
        """Test that invalid YAML raises ParseError."""
        content = """---
invalid: yaml: content: [
---

# Content"""
        
        with pytest.raises(ParseError, match="Invalid YAML"):
            parse_front_matter(content)
    
    def test_empty_front_matter(self):
        """Test that empty front-matter raises ParseError."""
        content = """---
---

# Content"""
        
        with pytest.raises(ParseError, match="Empty front-matter"):
            parse_front_matter(content)


class TestParseADRContent:
    """Test ADR content parsing."""
    
    def test_valid_adr_content(self):
        """Test parsing valid ADR content."""
        content = """---
id: ADR-0001
title: Use FastAPI
status: accepted
date: 2025-09-03
deciders: [backend-team]
tags: [backend, api]
---

# Context

We need a Python web framework.

# Decision

Use FastAPI for the backend API.

# Consequences

- Fast development
- Great documentation"""
        
        adr = parse_adr_content(content)
        
        assert adr.front_matter.id == "ADR-0001"
        assert adr.front_matter.title == "Use FastAPI"
        assert adr.front_matter.status == ADRStatus.ACCEPTED
        assert adr.front_matter.deciders == ["backend-team"]
        assert adr.front_matter.tags == ["backend", "api"]
        assert "# Context" in adr.content
        assert "# Decision" in adr.content
        assert "# Consequences" in adr.content
    
    def test_strict_validation(self):
        """Test strict validation mode."""
        content = """---
id: INVALID-ID
title: Test
status: accepted
date: 2025-09-03
---

# Content"""
        
        # Strict mode should raise validation error
        with pytest.raises(ParseError, match="validation failed"):
            parse_adr_content(content, strict=True)
        
        # Non-strict mode should work but print warning
        adr = parse_adr_content(content, strict=False)
        assert adr is not None


class TestParseADRFile:
    """Test ADR file parsing."""
    
    def test_valid_adr_file(self):
        """Test parsing a valid ADR file."""
        adr_content = """---
id: ADR-0001
title: Use PostgreSQL
status: accepted  
date: 2025-09-03
tags: [database]
---

# Context

We need a reliable database.

# Decision

Use PostgreSQL as our primary database.

# Consequences

- ACID compliance
- Strong community support"""
        
        with NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(adr_content)
            f.flush()
            
            adr = parse_adr_file(f.name)
            
            assert adr.front_matter.id == "ADR-0001"
            assert adr.front_matter.title == "Use PostgreSQL"
            assert adr.file_path == Path(f.name)
        
        # Clean up
        Path(f.name).unlink()
    
    def test_nonexistent_file(self):
        """Test that nonexistent file raises ParseError."""
        with pytest.raises(ParseError, match="File not found"):
            parse_adr_file("nonexistent.md")
    
    def test_directory_instead_of_file(self):
        """Test that directory raises ParseError."""
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(ParseError, match="Not a file"):
                parse_adr_file(tmpdir)


class TestFindADRFiles:
    """Test ADR file discovery."""
    
    def test_find_adr_files(self):
        """Test finding ADR files in directory."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create some ADR files
            (tmpdir_path / "ADR-0001-test.md").write_text("# Test ADR 1")
            (tmpdir_path / "ADR-0002-another.md").write_text("# Test ADR 2") 
            (tmpdir_path / "README.md").write_text("# README")
            (tmpdir_path / "not-adr.txt").write_text("Not an ADR")
            
            adr_files = find_adr_files(tmpdir_path)
            
            assert len(adr_files) == 2
            assert any("ADR-0001-test.md" in str(f) for f in adr_files)
            assert any("ADR-0002-another.md" in str(f) for f in adr_files)
            assert not any("README.md" in str(f) for f in adr_files)
            assert not any("not-adr.txt" in str(f) for f in adr_files)
    
    def test_find_adr_files_nonexistent_directory(self):
        """Test finding ADR files in nonexistent directory returns empty list."""
        adr_files = find_adr_files("nonexistent-directory")
        assert adr_files == []
    
    def test_custom_pattern(self):
        """Test finding ADR files with custom pattern."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create files with different patterns
            (tmpdir_path / "ADR-0001-test.md").write_text("# Test ADR")
            (tmpdir_path / "decision-001.md").write_text("# Decision")
            (tmpdir_path / "other.md").write_text("# Other")
            
            # Default pattern should find ADR-* files
            adr_files = find_adr_files(tmpdir_path)
            assert len(adr_files) == 1
            assert "ADR-0001-test.md" in str(adr_files[0])
            
            # Custom pattern should find decision-* files  
            decision_files = find_adr_files(tmpdir_path, "decision-*.md")
            assert len(decision_files) == 1
            assert "decision-001.md" in str(decision_files[0])