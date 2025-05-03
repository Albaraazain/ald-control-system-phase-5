# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Lint/Test Commands

- **Setup Environment**: `python -m venv myenv && source myenv/bin/activate && pip install -r requirements.txt`
- **Run Application**: `python main.py`
- **Run Tests**: `python -m pytest` (or for a single test: `python -m pytest path/to/test_file.py::test_function`)
- **Lint Code**: `python -m pylint --disable=C0103,C0111 --max-line-length=100 *.py`
- **Type Check**: `python -m mypy --ignore-missing-imports .`

## Code Style Guidelines

- **Imports**: Group in order: standard library, third-party, local application imports with a blank line between groups
- **Docstrings**: Use triple-quoted docstrings for modules, classes, and functions
- **Types**: Use type hints for function parameters and return values
- **Naming**:
  - Classes: CamelCase
  - Functions/Variables: snake_case
  - Constants: UPPERCASE
- **Error Handling**: Use try/except blocks with specific exceptions, log errors with context
- **Async Pattern**: Use async/await for asynchronous operations, particularly for I/O operations
- **Logging**: Use the logger from log_setup.py, include context in log messages
- **Line Length**: Keep lines under 100 characters
- **Formatting**: 4 spaces for indentation, no tabs
- **Function Parameters**: Use keyword arguments for clarity when calling functions with multiple parameters