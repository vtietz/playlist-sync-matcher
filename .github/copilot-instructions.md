# Architecture & Design Principles

## Code Organization
* **Separation of Concerns**: Keep CLI commands thin - they should only handle user interaction (parsing args, formatting output). Business logic belongs in service modules.
* **Service Layer Pattern**: Extract orchestration logic into dedicated service modules (e.g., `psm/services/`). Services should accept data, perform operations, and return structured results.
* **Return Structured Data**: Services should return dataclass objects or structured dicts, not print directly. Let callers decide how to present results.
* **Single Responsibility**: Each module, class, and function should have one clear purpose. If a function does authentication AND makes API calls AND processes results, split it.

## Configuration & Defaults
* **Consistency is Critical**: Default values must match between fallback code (`get('key', 'default')`) and config definitions (`_DEFAULTS`).
* **Type Safety**: When adding typed config (dataclasses), ensure field types match actual runtime usage (e.g., `fuzzy_threshold: float` not `int` if engine expects 0.0-1.0).
* **Avoid Duplication**: Configuration should be loaded once. Don't call `_configure_logging()` multiple times or reinitialize settings unnecessarily.

## Database & Data Access
* **Know Your Schema**: Use correct column names in SQL queries. Check table definitions before writing WHERE clauses.
* **Handle sqlite3.Row Correctly**: Use subscript access `row['column']` or check `'column' in row.keys()` - don't use `.get()` which doesn't exist on Row objects.
* **Encapsulation**: Add count/query methods to Database class rather than scattering raw SQL throughout the codebase.

## Error Handling & Logging
* **Never Swallow Exceptions Silently**: Always log errors, especially for I/O operations like cache writes. Use `logger.warning()` with context (file paths, error messages).
* **Resource Cleanup**: Use try/finally blocks for resources that need cleanup (threads, sockets, file handles). Call `.join()` on threads, `.close()` on sockets.
* **Proper Logging Levels**: Use DEBUG for detailed traces, INFO for normal operation, WARNING for recoverable issues, ERROR for failures.

## Testing & Validation
* **Run Tests in Environment**: Always activate virtualenv first (use `run.bat` or `.venv\Scripts\activate`).
* **Use Project Runner for Python**: Invoke Python via `run.bat py ...` (Windows) or `./run.sh py ...` to ensure the virtualenv is active (e.g., `run.bat py -m psm.cli --version`). Avoid calling the system `python` directly in automation.
* **Module Execution**: For `python -m psm.cli`, a `psm/cli/__main__.py` exists; ensure dependencies are installed via `run.bat install` before executing.
* **Test Behavior, Not Logging**: Tests should verify functional correctness (database state, file existence) rather than checking for specific log messages, which may not be captured by test runners.
* **Backward Compatibility**: When refactoring, ensure all existing tests pass. Add new tests for new functionality.
* **All Tests Must Pass**: Run full test suite after any changes. Never leave tests failing.
* **Finally remove all backward compatibility code**: If a feature or code path is deprecated, remove it entirely rather than leaving it commented out or behind flags.

## Style Guidelines (PEP 8 + Project Rules)
* **Code Formatting**: Use Black formatter with 120 character line length. All code must pass Black formatting checks.
* **Line Length**: Max 120 characters (not 80). Break long lines at logical points.
* **Blank Lines**: 2 blank lines after top-level class/function definitions, 1 blank line before nested functions.
* **Whitespace**: No trailing whitespace, space after commas `[a, b, c]`, spaces around operators `x = y + 1`.
* **Imports**: No unused imports. Remove them immediately when refactoring.
* **F-strings**: Only use f-strings when you have placeholders. Use regular strings otherwise: `"text"` not `f"text"`.
* **Line Breaks**: Break BEFORE operators for long expressions, not after. Align continuation lines properly.
* **File Endings**: All files must end with a single newline.
* **Click Commands**: When adding new CLI commands, import the module in `psm/cli/core.py` to register it.

# Code Quality

## Goals
- Keep code simple, small, and safe.
- Prefer clear types & interfaces over dynamic dicts/strings.
- Changes must pass local quality gates before commit/PR.

## Design & Clean Code (musts)
- Single responsibility: each file/class/function has one clear job. If a file exceeds the limits below, split it.
- APIs over ad-hoc dicts: use dataclasses/TypedDict/Pydantic (or language equivalent). Avoid getattr/hasattr tricks.
- Small units: default max function length 80 lines; file length 500–800 lines; cyclomatic complexity ≤10 (warn) / ≤15 (fail).
- Explicit errors: raise typed exceptions; no silent excepts. Log with context.
- Dependency hygiene: minimize imports; no side effects at import time.
- Naming: descriptive, consistent, no abbreviations without reason.
- Immutability by default: avoid mutating global state.
* **Remove Unused Code**: Delete unused imports, variables, and helper functions after refactoring. Don't leave dead code.
* **Use Standard Library**: Prefer built-in modules (copy.deepcopy, functools.lru_cache) over custom implementations.
* **Performance Awareness**: Cache expensive operations (normalization, OAuth sessions), use connection pooling, avoid redundant work.
* **Type Hints**: Add type hints to function signatures for better IDE support and self-documentation.
* **Avoid Nested If Statements**: Use early returns/exits to reduce nesting. Check failure conditions first and return early, then handle the success path in the main flow. This improves readability and reduces cognitive load.

**Example - Bad (nested):**
```python
if condition1:
    if condition2:
        if condition3:
            # Do work
            return result
```

**Example - Good (early returns):**
```python
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
# Do work
return result
```

## Documentation
* **Update README.md**: Document new features, changed behavior, and important configuration options.
* **Docstrings Matter**: Write clear docstrings explaining what services do, their parameters, and return values.
* **No Unrequested Artifacts**: Don't create summary files or documentation unless explicitly requested.

## Before Committing
1. ✅ All tests pass
2. ✅ No unused imports or variables
3. ✅ Defaults consistent across config files
4. ✅ Service layer properly separates concerns
5. ✅ Error handling includes proper logging
6. ✅ Resources cleaned up properly (threads, sockets, files)
7. ✅ README updated if functionality changed
8. ✅ Any new workflow steps use virtualenv-safe invocation (`run.bat` or install + python -m) and avoid raw system Python when project dependencies are required.
9. ✅ **Code quality analysis passed** - Run code analysis after bigger implementations to check:
   - **Command**: `run.bat py scripts\analyze_code.py changed` (or `run.bat py -m scripts.analyze_code`)
   - Complexity (Lizard): Functions should have CCN ≤ 15 and NLOC ≤ 100
   - Style (flake8): No style violations, max line length 120
   - Formatting (Black): Code must be formatted with Black (120 char line length)
   - Types (mypy - optional): Type hints where applicable

## Code Quality Analysis
* **When to Run**: After bigger implementations, refactorings, or before committing significant changes
* **How to Run**:
  - `run.bat py scripts\analyze_code.py changed` - Analyze only changed files (default, quick)
  - `run.bat py scripts\analyze_code.py all` - Analyze entire project (comprehensive)
  - `run.bat py scripts\analyze_code.py files <path>` - Analyze specific files
* **What to Check**:
  - **Complexity (Lizard)**: Functions with CCN > 15 need refactoring. Extract logic into smaller functions.
  - **Function Length**: Functions > 100 lines (NLOC) should be split into smaller, focused functions.
  - **Style (flake8)**: Fix any reported style issues. Project uses 120 char line length, Black-compatible ignores (E203, W503).
  - **Formatting (Black)**: All code must be formatted with Black. Run cleanup script to auto-format.
  - **Types (mypy)**: Optional but helpful. Add type hints to new functions.
* **Addressing Issues**:
  - **High Complexity**: Extract nested logic into helper functions, use early returns to reduce nesting
  - **Long Functions**: Split into multiple functions with clear single responsibilities
  - **Style Issues**: Follow PEP 8 with project-specific rules (120 char line length, Black-compatible)
  - **Formatting Issues**: Run `run.bat py scripts\cleanup_code.py changed` to auto-format with Black
  - **Import Issues**: Remove unused imports, organize imports logically

## Code Cleanup
* **Safe Automated Cleanup**: Use the cleanup script to fix low-hanging fruit automatically
* **What It Fixes**:
  - Code formatting with Black (PEP 8 compliant, 120 char line length)
  - Trailing whitespace on lines
  - Whitespace-only blank lines
  - Missing newline at end of file
  - Unused imports (safe removal only)
* **How to Use**:
  - `run.bat py scripts\cleanup_code.py --dry-run changed` - Preview changes before applying
  - `run.bat py scripts\cleanup_code.py changed` - Clean only changed files (safe for daily use)
  - `run.bat py scripts\cleanup_code.py all` - Clean entire project (use before major commits)
  - `run.bat py scripts\cleanup_code.py --skip-formatting all` - Skip Black formatting, only whitespace/imports
  - `run.bat py scripts\cleanup_code.py --skip-imports all` - Skip import removal, only formatting/whitespace
* **Order of Operations**: The script runs in this order: 1) Whitespace cleanup, 2) Unused import removal, 3) Black formatting
* **Safety**: Black is opinionated but safe - it only changes formatting, never logic. Other operations are also safe and non-breaking.

# Required final actions
* Run tests to ensure all changes pass.
* After your summary always propose clear, concise commit messages that accurately describe the changes made. Just a header, no details.
* Use the imperative mood in the subject line (e.g., "Add feature", "Fix bug", "Update docs").
