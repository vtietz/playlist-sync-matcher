# Architecture & Design Principles

## Code Organization
* **Separation of Concerns**: Keep CLI commands thin - they should only handle user interaction (parsing args, formatting output). Business logic belongs in service modules.
* **Service Layer Pattern**: Extract orchestration logic into dedicated service modules (e.g., `spx/services/`). Services should accept data, perform operations, and return structured results.
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
* **Test Behavior, Not Logging**: Tests should verify functional correctness (database state, file existence) rather than checking for specific log messages, which may not be captured by test runners.
* **Backward Compatibility**: When refactoring, ensure all existing tests pass. Add new tests for new functionality.
* **All Tests Must Pass**: Run full test suite after any changes. Never leave tests failing.

## Code Quality
* **Remove Unused Code**: Delete unused imports, variables, and helper functions after refactoring. Don't leave dead code.
* **Use Standard Library**: Prefer built-in modules (copy.deepcopy, functools.lru_cache) over custom implementations.
* **Performance Awareness**: Cache expensive operations (normalization, OAuth sessions), use connection pooling, avoid redundant work.
* **Type Hints**: Add type hints to function signatures for better IDE support and self-documentation.

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
