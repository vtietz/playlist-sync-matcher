"""Test single provider validation."""
import pytest
from psm.config import validate_single_provider


def test_validate_single_provider_success():
    """Test validation passes with single configured provider."""
    cfg = {
        'providers': {
            'spotify': {
                'client_id': 'abc123',
                'redirect_port': 9876
            }
        }
    }
    result = validate_single_provider(cfg)
    assert result == 'spotify'


def test_validate_single_provider_multiple_providers_fails():
    """Test validation fails with multiple configured providers."""
    cfg = {
        'providers': {
            'spotify': {
                'client_id': 'abc123'
            },
            'apple_music': {
                'client_id': 'xyz789'
            }
        }
    }
    with pytest.raises(ValueError) as exc_info:
        validate_single_provider(cfg)
    
    assert 'Multiple providers configured' in str(exc_info.value)
    assert 'spotify' in str(exc_info.value)
    assert 'apple_music' in str(exc_info.value)
    assert 'Multi-provider mode is not yet supported' in str(exc_info.value)


def test_validate_single_provider_no_client_id_fails():
    """Test validation fails when provider section exists but no client_id."""
    cfg = {
        'providers': {
            'spotify': {
                'redirect_port': 9876
                # No client_id
            }
        }
    }
    with pytest.raises(ValueError) as exc_info:
        validate_single_provider(cfg)
    
    assert 'no client_id configured' in str(exc_info.value)
    assert 'PSM__PROVIDERS__SPOTIFY__CLIENT_ID' in str(exc_info.value)


def test_validate_single_provider_empty_providers_fails():
    """Test validation fails when providers section is empty."""
    cfg = {
        'providers': {}
    }
    with pytest.raises(ValueError) as exc_info:
        validate_single_provider(cfg)
    
    # Empty providers dict is treated as no providers section
    assert 'No providers section' in str(exc_info.value)


def test_validate_single_provider_no_providers_section_fails():
    """Test validation fails when providers section is missing."""
    cfg = {}
    with pytest.raises(ValueError) as exc_info:
        validate_single_provider(cfg)
    
    assert 'No providers section' in str(exc_info.value)


def test_validate_single_provider_ignores_providers_without_client_id():
    """Test validation ignores providers that don't have client_id set."""
    cfg = {
        'providers': {
            'spotify': {
                'client_id': 'abc123'
            },
            'apple_music': {
                # No client_id - should be ignored
                'redirect_port': 9999
            }
        }
    }
    result = validate_single_provider(cfg)
    assert result == 'spotify'


def test_validate_single_provider_handles_non_dict_provider():
    """Test validation handles non-dict provider configurations."""
    cfg = {
        'providers': {
            'spotify': {
                'client_id': 'abc123'
            },
            'broken': 'not a dict'
        }
    }
    result = validate_single_provider(cfg)
    assert result == 'spotify'
