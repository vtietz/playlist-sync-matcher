# Tests Structure

Layered test layout introduced during test pyramid migration.

## Directories
- `unit/`: Pure logic tests using `MockDatabase` + stubs. No filesystem or network I/O.
- `integration/`: Real sqlite DB usage; verifies schema, SQL queries, multi-module interaction.
- `e2e/`: CLI workflow smoke tests (network calls stubbed or avoided).
- `mocks/`: Test doubles (MockDatabase, stub clients, fixtures).

## Running
Use wrapper to ensure virtualenv:
```
run.bat py -m pytest -q                 # full
run.bat py -m pytest tests/unit -m unit # unit only
run.bat py -m pytest -m integration     # integration only
run.bat py -m pytest -m e2e             # e2e only
```

## Adding Unit Tests
1. Prefer dependency injection (`DatabaseInterface`).
2. Use `MockDatabase`; extend only needed methods.
3. Avoid touching `db.conn` directly—add interface methods instead.

## Migration Notes
Legacy tests remain at root until migrated. New pure logic tests must go into `tests/unit/`.
