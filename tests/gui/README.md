# GUI Tests

This directory contains tests for the GUI components of the Playlist Sync Matcher.

## Structure

```
tests/gui/
├── __init__.py              # Package marker
├── README.md                # This file
├── test_components.py       # Tests for GUI components (SortFilterTable, LogPanel, FilterBar, UnifiedTracksProxyModel)
├── test_models.py           # Tests for data models (PlaylistsModel, UnifiedTracksModel)
├── test_data_facade.py      # Tests for DataFacade
└── test_integration.py      # Integration tests (to be added)
```

## Running GUI Tests

### Run all GUI tests:
```bash
.\run.bat py -m pytest tests/gui/ -v
```

### Run specific test file:
```bash
.\run.bat py -m pytest tests/gui/test_models.py -v
```

### Run specific test class:
```bash
.\run.bat py -m pytest tests/gui/test_models.py::TestPlaylistsModel -v
```

### Run specific test:
```bash
.\run.bat py -m pytest tests/gui/test_models.py::TestPlaylistsModel::test_initial_state -v
```

## Test Coverage

### Components (`test_components.py`)
- ✅ SortFilterTable - creation, sorting, filtering, selection
- ✅ LogPanel - log appending, clearing
- ✅ FilterBar - filter values, clearing, signal emission
- ✅ UnifiedTracksProxyModel - playlist filter, status filter, search filter, debouncing

### Models (`test_models.py`)
- ✅ PlaylistsModel - initial state, column headers, data setting, "All Playlists" row, row data retrieval
- ✅ UnifiedTracksModel - initial state, column headers, data setting, matched/unmatched tracks, row data retrieval

### Data Layer (`test_data_facade.py`)
- ✅ DataFacade - playlist listing with "All Playlists", match statistics, unified tracks view, playlist details, counts

### Integration (`test_integration.py`) - TODO
- ⏳ End-to-end workflow tests
- ⏳ Signal/slot connections
- ⏳ User interaction simulations

## Writing New Tests

### Component Tests
When testing GUI components:
1. Use the `qapp` fixture to ensure QApplication exists
2. Test creation, basic functionality, and signal emission
3. Avoid relying on visual rendering (use data/state checks instead)

Example:
```python
def test_my_component(self, qapp):
    """Test component functionality."""
    component = MyComponent()
    
    # Test state
    assert component.some_property == expected_value
    
    # Test signal emission
    signal_received = []
    component.my_signal.connect(lambda: signal_received.append(True))
    component.trigger_action()
    assert len(signal_received) == 1
```

### Model Tests
When testing models:
1. Test initial state (rowCount, columnCount, headers)
2. Test data setting and retrieval
3. Test special cases (empty data, invalid indices)

Example:
```python
def test_model_data(self):
    """Test setting and getting model data."""
    model = MyModel()
    
    data = [{'id': '1', 'name': 'Test'}]
    model.set_data(data)
    
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0), Qt.DisplayRole) == 'Test'
```

### Data Facade Tests
When testing DataFacade:
1. Use fixtures to create test databases
2. Test data retrieval methods
3. Verify calculated statistics and aggregations

Example:
```python
@pytest.fixture
def db_with_data(tmp_path):
    """Create test database."""
    db = create_test_db(tmp_path)
    # ... populate with test data
    yield db
    db.close()

def test_facade_method(self, db_with_data):
    """Test facade data retrieval."""
    facade = DataFacade(db_with_data)
    result = facade.some_method()
    assert result == expected
```

## Common Issues

### QApplication not found
If you see errors about QApplication, ensure the `qapp` fixture is used:
```python
def test_something(self, qapp):  # Add qapp parameter
    # Test code here
```

### Import errors in IDE
Lint errors for pytest and PySide6 imports are expected in some IDEs. The tests will run correctly when executed via pytest.

### Database schema issues
If database-related tests fail, check:
1. The database schema matches your test expectations
2. Fixtures properly set up and tear down test data
3. Provider filtering is applied correctly

## Test Philosophy

Following the project's architecture guidelines:

1. **Test Behavior, Not Implementation**: Focus on what the component does, not how it does it
2. **Separation of Concerns**: Test components in isolation when possible
3. **Use Fixtures**: Reuse test data setup across multiple tests
4. **Descriptive Names**: Test names should clearly describe what they test
5. **One Assert Per Concept**: Each test should verify one logical concept (but can have multiple asserts for that concept)

## CI/CD Integration

These tests are part of the main test suite and run automatically with:
```bash
.\run.bat test
```

All tests must pass before committing changes.
