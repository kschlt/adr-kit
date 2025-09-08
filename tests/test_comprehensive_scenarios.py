"""Comprehensive scenario tests for workflow edge cases and error handling."""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from adr_kit.workflows.base import WorkflowStatus, WorkflowError
from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
from adr_kit.workflows.creation import CreationWorkflow, CreationInput
from adr_kit.workflows.preflight import PreflightWorkflow, PreflightInput


class TestErrorScenarios:
    """Test comprehensive error scenarios and edge cases."""
    
    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)
    
    def test_corrupted_adr_directory(self, temp_adr_dir):
        """Test handling of corrupted ADR directory."""
        # Create a corrupted ADR file
        corrupted_file = Path(temp_adr_dir) / "corrupted.md"
        corrupted_file.write_text("Invalid YAML\n---\nbroken: [content\n---\nContent")
        
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute()
        
        # Should handle corruption gracefully
        assert result is not None
        # Either succeeds by skipping corrupted files or fails with clear error
        if not result.success:
            assert len(result.errors) > 0
    
    def test_permission_denied_scenarios(self, temp_adr_dir):
        """Test various permission denied scenarios."""
        # Test read permission denied
        restricted_dir = Path(temp_adr_dir) / "restricted"
        restricted_dir.mkdir()
        
        # Create file in restricted directory
        test_file = restricted_dir / "test.md"
        test_file.write_text("test content")
        
        # Remove read permissions
        original_perms = restricted_dir.stat().st_mode
        
        try:
            restricted_dir.chmod(0o000)  # No permissions
            
            # Workflows should handle permission errors gracefully
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute()
            
            # Should complete with warnings or clear error messages
            assert result is not None
            
        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(original_perms)
    
    def test_disk_full_simulation(self, temp_adr_dir):
        """Test handling of disk full scenarios during file creation."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        
        creation_input = CreationInput(
            title="Test ADR",
            context="Testing disk full scenario",
            decision="Test decision",
            consequences="Test consequences"
        )
        
        # Mock write operation to raise disk full error
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            result = workflow.execute(creation_input)
            
            # Should fail gracefully with clear error message
            assert result.success is False
            assert len(result.errors) > 0
            assert any("space" in error.lower() or "disk" in error.lower() 
                      for error in result.errors)
    
    def test_network_timeout_simulation(self, temp_adr_dir):
        """Test handling of network timeouts in workflows that might make network calls."""
        # Some workflows might make network calls for semantic analysis or updates
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
        
        # Mock any potential network calls to timeout
        with patch('requests.get', side_effect=Exception("Connection timeout")):
            result = workflow.execute()
            
            # Should complete or fail gracefully
            assert result is not None
            assert isinstance(result.success, bool)
    
    def test_malformed_input_data(self, temp_adr_dir):
        """Test handling of malformed or unexpected input data."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        
        # Test with malformed policy data
        malformed_input = CreationInput(
            title="Test ADR",
            context="Testing malformed input",
            decision="Test decision",
            consequences="Test consequences",
            policy="invalid_policy_format"  # Should be dict, not string
        )
        
        result = workflow.execute(malformed_input)
        
        # Should handle malformed input gracefully
        assert result is not None
        if not result.success:
            assert len(result.errors) > 0
    
    def test_very_large_data_handling(self, temp_adr_dir):
        """Test handling of very large input data."""
        # Create very large content
        large_content = "Very large content " * 10000  # ~200KB of text
        
        large_input = CreationInput(
            title="Test ADR with large content",
            context=large_content,
            decision=large_content,
            consequences=large_content
        )
        
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(large_input)
        
        # Should handle large content or provide clear size limits
        assert result is not None
        
        if result.success:
            # Should create file successfully
            creation_result = result.data["creation_result"]
            created_file = Path(creation_result.file_path)
            assert created_file.exists()
            
            # File should contain the content
            content = created_file.read_text()
            assert len(content) > 100000  # Should be large
    
    def test_concurrent_workflow_execution(self, temp_adr_dir):
        """Test handling of concurrent workflow execution."""
        import threading
        import time
        
        results = []
        errors = []
        
        def run_workflow(index):
            try:
                workflow = CreationWorkflow(adr_dir=temp_adr_dir)
                input_data = CreationInput(
                    title=f"Concurrent ADR {index}",
                    context=f"Testing concurrent execution {index}",
                    decision=f"Decision {index}",
                    consequences=f"Consequences {index}"
                )
                
                result = workflow.execute(input_data)
                results.append((index, result))
            except Exception as e:
                errors.append((index, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=run_workflow, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout
        
        # Should handle concurrent execution
        assert len(results) == 3
        
        # All should complete (success or controlled failure)
        for index, result in results:
            assert result is not None
            assert isinstance(result.success, bool)
        
        # No unhandled exceptions
        assert len(errors) == 0
    
    def test_memory_pressure_handling(self, temp_adr_dir):
        """Test workflow behavior under memory pressure."""
        # Create many large objects to simulate memory pressure
        large_objects = []
        
        try:
            # Allocate significant memory
            for _ in range(100):
                large_objects.append("x" * 1000000)  # 1MB each = ~100MB total
            
            # Run workflow under memory pressure
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute()
            
            # Should complete or fail gracefully
            assert result is not None
            assert isinstance(result.success, bool)
            
        finally:
            # Clean up memory
            large_objects.clear()
    
    def test_unicode_and_encoding_handling(self, temp_adr_dir):
        """Test handling of various Unicode characters and encoding issues."""
        # Test with various Unicode characters
        unicode_input = CreationInput(
            title="ADR with Unicode: 测试 🚀 Ñoël café",
            context="Unicode context: العربية русский 日本語 emoji: 🎉🔥💯",
            decision="Decision with symbols: ±∞≠≤≥∑∫∆",
            consequences="Consequences: →←↑↓⟵⟶⟷"
        )
        
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        result = workflow.execute(unicode_input)
        
        # Should handle Unicode properly
        assert result.success is True
        
        creation_result = result.data["creation_result"]
        created_file = Path(creation_result.file_path)
        
        # File should exist and contain Unicode content
        assert created_file.exists()
        content = created_file.read_text(encoding='utf-8')
        assert "测试" in content
        assert "🚀" in content
        assert "العربية" in content
    
    def test_extremely_long_processing_time(self, temp_adr_dir):
        """Test workflow timeout and long processing scenarios."""
        workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
        
        # Mock a step to take very long time
        original_detect = workflow._detect_technologies
        
        def slow_detect(*args, **kwargs):
            import time
            time.sleep(2)  # Simulate slow processing
            return original_detect(*args, **kwargs)
        
        workflow._detect_technologies = slow_detect
        
        import time
        start_time = time.time()
        
        result = workflow.execute()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete or timeout gracefully
        assert result is not None
        
        # Should track timing information
        if result.success:
            assert result.duration_ms > 2000  # Should reflect the 2+ second delay
    
    def test_invalid_adr_directory_scenarios(self):
        """Test various invalid ADR directory scenarios."""
        # Test non-existent directory
        workflow = AnalyzeProjectWorkflow(adr_dir="/nonexistent/path")
        result = workflow.execute()
        
        assert result.success is False
        assert len(result.errors) > 0
        
        # Test file instead of directory
        with tempfile.NamedTemporaryFile() as temp_file:
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_file.name)
            result = workflow.execute()
            
            assert result.success is False
            assert len(result.errors) > 0
    
    def test_workflow_state_consistency(self, temp_adr_dir):
        """Test that workflow state remains consistent during errors."""
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        
        # Create initial state
        initial_adr_files = list(Path(temp_adr_dir).glob("*.md"))
        
        # Execute workflow that fails mid-way
        invalid_input = CreationInput(
            title="Test ADR",
            context="Test context",
            decision="",  # Empty decision should cause failure
            consequences="Test consequences"
        )
        
        result = workflow.execute(invalid_input)
        
        # Workflow should fail
        assert result.success is False
        
        # File system state should be consistent (no partial files created)
        final_adr_files = list(Path(temp_adr_dir).glob("*.md"))
        assert len(final_adr_files) == len(initial_adr_files)
        
        # Workflow result should have proper error state
        assert len(result.errors) > 0
        assert result.status in [WorkflowStatus.FAILED, WorkflowStatus.VALIDATION_ERROR]


class TestPerformanceScenarios:
    """Test performance characteristics of workflows."""
    
    @pytest.fixture
    def temp_adr_dir(self):
        """Create temporary ADR directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adr_dir = Path(tmpdir) / "docs" / "adr"
            adr_dir.mkdir(parents=True)
            yield str(adr_dir)
    
    def test_large_project_analysis_performance(self, temp_adr_dir):
        """Test performance of analyzing very large projects."""
        # Create large project structure
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            
            # Create many directories and files
            for i in range(10):  # 10 directories
                dir_path = project_path / f"module_{i}"
                dir_path.mkdir()
                
                for j in range(20):  # 20 files each = 200 files total
                    (dir_path / f"file_{j}.py").write_text(f"# File {i}_{j}\nprint('hello')")
            
            # Add some config files
            (project_path / "requirements.txt").write_text("django==4.2.0\npostgresql==1.0.0")
            
            import time
            start_time = time.time()
            
            workflow = AnalyzeProjectWorkflow(adr_dir=temp_adr_dir)
            result = workflow.execute(project_path=str(project_path))
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete in reasonable time (less than 30 seconds)
            assert execution_time < 30
            
            # Should complete successfully
            assert result.success is True
            
            # Should detect Python
            technologies = result.data["project_context"]["technologies"]
            assert "python" in str(technologies).lower()
    
    def test_many_existing_adrs_performance(self, temp_adr_dir):
        """Test performance when many ADRs already exist."""
        # Create many existing ADRs
        for i in range(50):  # 50 existing ADRs
            adr_content = f"""---
id: ADR-{i+1:04d}
title: Decision {i+1}
status: accepted
date: 2024-01-{(i % 28) + 1:02d}
---

## Context
Context for decision {i+1}

## Decision
Decision {i+1}

## Consequences
Consequences for decision {i+1}
"""
            adr_file = Path(temp_adr_dir) / f"adr-{i+1:04d}-decision-{i+1}.md"
            adr_file.write_text(adr_content)
        
        import time
        start_time = time.time()
        
        # Test creation workflow with many existing ADRs
        workflow = CreationWorkflow(adr_dir=temp_adr_dir)
        input_data = CreationInput(
            title="New ADR with many existing",
            context="Testing performance with many existing ADRs",
            decision="Make new decision",
            consequences="New consequences"
        )
        
        result = workflow.execute(input_data)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete in reasonable time (less than 10 seconds)
        assert execution_time < 10
        
        if result.success:
            # Should generate correct next ID
            creation_result = result.data["creation_result"]
            assert creation_result.adr_id == "ADR-0051"  # Next after ADR-0050
    
    def test_memory_efficient_processing(self, temp_adr_dir):
        """Test that workflows are memory efficient with large data."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Process many workflows
        for i in range(20):
            workflow = CreationWorkflow(adr_dir=temp_adr_dir)
            input_data = CreationInput(
                title=f"ADR {i}",
                context=f"Context {i} " * 1000,  # Large context
                decision=f"Decision {i} " * 1000,
                consequences=f"Consequences {i} " * 1000
            )
            
            result = workflow.execute(input_data)
            assert result is not None
        
        # Check memory usage hasn't grown excessively
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Should not grow more than 100MB (reasonable threshold)
        assert memory_growth < 100 * 1024 * 1024  # 100MB


if __name__ == "__main__":
    pytest.main([__file__, "-v"])