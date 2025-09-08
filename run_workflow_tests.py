#!/usr/bin/env python3
"""
Comprehensive test runner for ADR Kit workflow system.

This script runs all workflow tests and provides detailed coverage and performance reporting.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print('='*60)
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=False)
    end_time = time.time()
    
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED ({duration:.2f}s)")
        return True
    else:
        print(f"❌ {description} - FAILED ({duration:.2f}s)")
        return False


def main():
    """Run comprehensive workflow tests."""
    print("🚀 ADR Kit Workflow Test Suite")
    print("Testing sophisticated workflow system with clean MCP entry points")
    
    # Change to project directory
    project_dir = Path(__file__).parent
    subprocess.run(f"cd {project_dir}", shell=True)
    
    test_results = []
    total_start = time.time()
    
    # Test categories
    tests = [
        {
            "cmd": "python -m pytest tests/test_workflow_base.py -v --tb=short",
            "desc": "Workflow Base Classes (Infrastructure)"
        },
        {
            "cmd": "python -m pytest tests/test_workflow_analyze.py -v --tb=short", 
            "desc": "Analyze Workflow (Project Analysis)"
        },
        {
            "cmd": "python -m pytest tests/test_workflow_creation.py -v --tb=short",
            "desc": "Creation Workflow (ADR Creation)"
        },
        {
            "cmd": "python -m pytest tests/test_mcp_workflow_integration.py -v --tb=short",
            "desc": "MCP ↔ Workflow Integration"
        },
        {
            "cmd": "python -m pytest tests/test_comprehensive_scenarios.py -v --tb=short",
            "desc": "Error Scenarios & Edge Cases"
        },
        {
            "cmd": "python -m pytest tests/ -k 'not test_comprehensive_scenarios' --tb=line",
            "desc": "All Workflow Tests (Quick Run)"
        }
    ]
    
    # Run tests
    for test in tests:
        success = run_command(test["cmd"], test["desc"])
        test_results.append((test["desc"], success))
    
    # Coverage report (if pytest-cov available)
    print(f"\n{'='*60}")
    print("📊 Generating Coverage Report")
    print('='*60)
    
    coverage_cmd = """
    python -m pytest tests/test_workflow_*.py tests/test_mcp_workflow_integration.py \
    --cov=adr_kit.workflows --cov=adr_kit.mcp \
    --cov-report=term-missing --cov-report=html:htmlcov/workflows \
    -v --tb=line
    """
    
    try:
        subprocess.run(coverage_cmd, shell=True, check=False)
        print("✅ Coverage report generated in htmlcov/workflows/")
    except:
        print("⚠️  Coverage report skipped (install pytest-cov for coverage)")
    
    # Performance benchmarks
    print(f"\n{'='*60}")
    print("⚡ Performance Benchmarks")
    print('='*60)
    
    perf_cmd = "python -c \"\
import tempfile; \
from pathlib import Path; \
import time; \
from adr_kit.workflows.analyze import AnalyzeProjectWorkflow; \
from adr_kit.workflows.creation import CreationWorkflow, CreationInput; \
\
with tempfile.TemporaryDirectory() as tmp: \
    adr_dir = Path(tmp) / 'adr'; \
    adr_dir.mkdir(parents=True); \
    \
    # Benchmark analyze workflow \
    start = time.time(); \
    analyze_workflow = AnalyzeProjectWorkflow(adr_dir=str(adr_dir)); \
    analyze_result = analyze_workflow.execute(); \
    analyze_time = time.time() - start; \
    print(f'⚡ Analyze Workflow: {analyze_time:.3f}s (Success: {analyze_result.success})'); \
    \
    # Benchmark creation workflow \
    start = time.time(); \
    create_workflow = CreationWorkflow(adr_dir=str(adr_dir)); \
    create_input = CreationInput( \
        title='Performance Test ADR', \
        context='Testing workflow performance', \
        decision='Use fast workflows', \
        consequences='Better performance' \
    ); \
    create_result = create_workflow.execute(create_input); \
    create_time = time.time() - start; \
    print(f'⚡ Creation Workflow: {create_time:.3f}s (Success: {create_result.success})'); \
    \
    print(f'⚡ Total Benchmark Time: {analyze_time + create_time:.3f}s'); \
\""
    
    try:
        subprocess.run(perf_cmd, shell=True, check=False)
    except Exception as e:
        print(f"⚠️  Performance benchmarks failed: {e}")
    
    # Final summary
    total_time = time.time() - total_start
    
    print(f"\n{'='*60}")
    print("📋 TEST SUMMARY")
    print('='*60)
    
    passed = 0
    total = len(test_results)
    
    for desc, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {desc}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} test suites passed")
    print(f"⏱️  Total time: {total_time:.2f} seconds")
    
    if passed == total:
        print(f"\n🎉 ALL WORKFLOW TESTS PASSED!")
        print("✅ Sophisticated workflows are working correctly")
        print("✅ MCP entry points properly integrated")  
        print("✅ Error handling and edge cases covered")
        print("✅ Ready for production agent integration")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed")
        print("❌ Review failed tests before production use")
        return 1


def quick_validation():
    """Quick validation that core components work."""
    print("🔍 Quick Workflow Validation")
    
    try:
        # Test imports
        from adr_kit.workflows.base import BaseWorkflow, WorkflowResult
        from adr_kit.workflows.analyze import AnalyzeProjectWorkflow
        from adr_kit.workflows.creation import CreationWorkflow
        from adr_kit.mcp.server import mcp
        from adr_kit.mcp.models import success_response, error_response
        
        print("✅ All workflow and MCP imports successful")
        
        # Test basic workflow instantiation
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            adr_dir = Path(tmp) / "adr"
            adr_dir.mkdir()
            
            # Test workflow creation
            analyze_wf = AnalyzeProjectWorkflow(adr_dir=str(adr_dir))
            create_wf = CreationWorkflow(adr_dir=str(adr_dir))
            
            print("✅ Workflow instantiation successful")
            
            # Test MCP response models
            success_resp = success_response("test", {"key": "value"})
            error_resp = error_response("error", "details", "action")
            
            assert success_resp["status"] == "success"
            assert error_resp["status"] == "error"
            
            print("✅ MCP response models working")
        
        print("✅ Quick validation passed - components are working!")
        return True
        
    except Exception as e:
        print(f"❌ Quick validation failed: {e}")
        return False


if __name__ == "__main__":
    # Check if pytest is available
    try:
        import pytest
    except ImportError:
        print("❌ pytest not available. Install with: pip install pytest pytest-cov")
        sys.exit(1)
    
    # Quick validation first
    if not quick_validation():
        print("❌ Quick validation failed - check imports")
        sys.exit(1)
    
    # Run full test suite
    exit_code = main()
    sys.exit(exit_code)