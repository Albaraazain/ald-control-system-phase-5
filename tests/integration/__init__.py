"""
Integration tests for ALD Control System.

This package contains comprehensive integration tests that verify multi-terminal
interactions, cross-service coordination, and system-level behavior.

Test Files:
- test_multi_terminal_workflows.py: 51 tests covering all 54 scenarios from
  cross_terminal_integration_requirements.md
- test_plc_singleton_consistency.py: 18 tests verifying PLC singleton pattern
  across all 3 terminals

Run integration tests with:
    pytest tests/integration/ --run-integration -v
"""