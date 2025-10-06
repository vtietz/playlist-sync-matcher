"""Tests for database concurrency protection and locking mechanism."""

import json
import os
import time
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from psm.db import Database, DatabaseLock


def test_database_lock_basic(tmp_path: Path):
    """Test basic lock acquisition and release."""
    db_path = tmp_path / "test.db"
    lock = DatabaseLock(db_path)
    
    # Initially no lock file
    assert not lock.lock_file.exists()
    assert not lock.acquired
    
    # Acquire lock
    assert lock.acquire()
    assert lock.acquired
    assert lock.lock_file.exists()
    
    # Lock file contains correct info
    with open(lock.lock_file, 'r') as f:
        lock_info = json.loads(f.read())
    assert lock_info['pid'] == os.getpid()
    assert 'command' in lock_info
    assert 'timestamp' in lock_info
    
    # Release lock
    lock.release()
    assert not lock.acquired
    assert not lock.lock_file.exists()


def test_database_lock_context_manager(tmp_path: Path):
    """Test lock works properly as context manager."""
    db_path = tmp_path / "test.db"
    
    with DatabaseLock(db_path) as acquired:
        assert acquired
        assert (db_path.with_suffix('.lock')).exists()
    
    # Lock should be released after context
    assert not (db_path.with_suffix('.lock')).exists()


def test_database_lock_concurrent_access(tmp_path: Path):
    """Test that concurrent access is properly blocked."""
    db_path = tmp_path / "test.db"
    
    # First lock succeeds
    lock1 = DatabaseLock(db_path)
    assert lock1.acquire()
    
    # Second lock fails due to conflict
    lock2 = DatabaseLock(db_path)
    assert not lock2.acquire(timeout=0.5)  # Short timeout for test speed
    
    # After first lock is released, second can acquire
    lock1.release()
    assert lock2.acquire()
    lock2.release()


def test_database_lock_stale_cleanup(tmp_path: Path):
    """Test cleanup of stale locks from dead processes."""
    db_path = tmp_path / "test.db"
    lock_file = db_path.with_suffix('.lock')
    
    # Create a stale lock file with fake PID
    fake_pid = 999999  # Very unlikely to exist
    stale_lock_info = {
        'pid': fake_pid,
        'command': 'fake command',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(lock_file, 'w') as f:
        json.dump(stale_lock_info, f)
    
    # Acquiring should clean up the stale lock and succeed
    lock = DatabaseLock(db_path)
    
    # Mock os.kill to raise ProcessLookupError for the fake PID
    def mock_kill(pid, sig):
        if pid == fake_pid:
            raise ProcessLookupError("Process not found")
        # For other PIDs, we don't need to call the original os.kill in tests
    
    with patch('os.kill', side_effect=mock_kill):
        assert lock.acquire()
        assert lock.acquired
    
    lock.release()


def test_database_with_locking(tmp_path: Path):
    """Test Database class with locking enabled."""
    db_path = tmp_path / "test.db"
    
    # Database should acquire lock by default
    db = Database(db_path, acquire_lock=True)
    assert db.lock is not None
    assert db.lock.acquired
    assert db.lock.lock_file.exists()
    
    # Another Database instance should fail to acquire lock
    with pytest.raises(RuntimeError, match="Could not acquire database lock"):
        Database(db_path, acquire_lock=True)
    
    # Close releases the lock
    db.close()
    assert not db.lock.lock_file.exists()
    
    # Now another instance can acquire it
    db2 = Database(db_path, acquire_lock=True)
    assert db2.lock is not None
    assert db2.lock.acquired
    db2.close()


def test_database_without_locking(tmp_path: Path):
    """Test Database class with locking disabled."""
    db_path = tmp_path / "test.db"
    
    # Database without locking
    db = Database(db_path, acquire_lock=False)
    assert db.lock is None
    assert not db_path.with_suffix('.lock').exists()
    
    db.close()


def test_database_lock_threading(tmp_path: Path):
    """Test database locking behavior with threading."""
    db_path = tmp_path / "test.db"
    results = {}
    
    def acquire_lock(thread_id):
        """Function to run in thread."""
        try:
            db = Database(db_path, acquire_lock=True)
            results[thread_id] = "success"
            time.sleep(0.1)  # Hold lock briefly
            db.close()
        except RuntimeError:
            results[thread_id] = "blocked"
    
    # Start two threads trying to acquire the same lock
    thread1 = threading.Thread(target=acquire_lock, args=("thread1",))
    thread2 = threading.Thread(target=acquire_lock, args=("thread2",))
    
    thread1.start()
    time.sleep(0.05)  # Small delay to ensure thread1 starts first
    thread2.start()
    
    thread1.join()
    thread2.join()
    
    # One should succeed, one should be blocked
    success_count = sum(1 for result in results.values() if result == "success")
    blocked_count = sum(1 for result in results.values() if result == "blocked")
    
    assert success_count == 1
    assert blocked_count == 1


def test_database_lock_invalid_json(tmp_path: Path):
    """Test handling of corrupted lock files."""
    db_path = tmp_path / "test.db"
    lock_file = db_path.with_suffix('.lock')
    
    # Create invalid JSON lock file
    with open(lock_file, 'w') as f:
        f.write("invalid json content")
    
    # Should clean up corrupted lock and acquire successfully
    lock = DatabaseLock(db_path)
    assert lock.acquire()
    assert lock.acquired
    
    lock.release()


def test_database_lock_empty_pid(tmp_path: Path):
    """Test handling of lock files with missing/invalid PID."""
    db_path = tmp_path / "test.db"
    lock_file = db_path.with_suffix('.lock')
    
    # Create lock file without PID
    lock_info = {
        'command': 'test command',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(lock_file, 'w') as f:
        json.dump(lock_info, f)
    
    # Should clean up invalid lock and acquire successfully
    lock = DatabaseLock(db_path)
    assert lock.acquire()
    assert lock.acquired
    
    lock.release()


def test_database_context_manager_with_lock(tmp_path: Path):
    """Test Database context manager properly releases locks."""
    db_path = tmp_path / "test.db"
    lock_file = db_path.with_suffix('.lock')
    
    with Database(db_path, acquire_lock=True) as db:
        assert db.lock is not None
        assert db.lock.acquired
        assert lock_file.exists()
    
    # Lock should be released after context
    assert not lock_file.exists()


def test_database_lock_timeout_behavior(tmp_path: Path):
    """Test lock acquisition timeout behavior."""
    db_path = tmp_path / "test.db"
    
    # First lock
    lock1 = DatabaseLock(db_path)
    assert lock1.acquire()
    
    # Second lock with very short timeout should fail quickly
    lock2 = DatabaseLock(db_path)
    start_time = time.time()
    result = lock2.acquire(timeout=0.2)
    elapsed = time.time() - start_time
    
    assert not result
    assert elapsed < 0.5  # Should timeout quickly, not wait long
    
    lock1.release()


def test_database_lock_double_release(tmp_path: Path):
    """Test that releasing an already released lock is safe."""
    db_path = tmp_path / "test.db"
    lock = DatabaseLock(db_path)
    
    assert lock.acquire()
    lock.release()
    
    # Double release should not crash
    lock.release()
    assert not lock.acquired