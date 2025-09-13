"""Tests for config module."""

import pytest
import tempfile
import os
from bigfoot.config import Config


class TestConfig:
    """Test cases for Config class."""
    
    @pytest.fixture
    def temp_config(self):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
github:
  token: "test_token"
  repos:
    - "user/repo1"
    - "user/repo2"
  rate_limit: 5000
settings:
  timezone: "UTC"
  daily_goal: 10
  show_progress: true
  color_output: true
  compact_mode: false
            """)
            config_path = f.name
        
        config = Config(config_path)
        yield config
        
        # Cleanup
        os.unlink(config_path)
    
    def test_load_config(self, temp_config):
        """Test loading configuration from file."""
        assert temp_config.get_github_token() == "test_token"
        assert temp_config.get_repositories() == ["user/repo1", "user/repo2"]
        assert temp_config.get_daily_goal() == 10
        assert temp_config.get_rate_limit() == 5000
    
    def test_get_github_token(self, temp_config):
        """Test getting GitHub token."""
        assert temp_config.get_github_token() == "test_token"
    
    def test_set_github_token(self, temp_config):
        """Test setting GitHub token."""
        temp_config.set_github_token("new_token")
        assert temp_config.get_github_token() == "new_token"
    
    def test_get_repositories(self, temp_config):
        """Test getting repositories."""
        repos = temp_config.get_repositories()
        assert len(repos) == 2
        assert "user/repo1" in repos
        assert "user/repo2" in repos
    
    def test_add_repository(self, temp_config):
        """Test adding repository."""
        temp_config.add_repository("user/repo3")
        repos = temp_config.get_repositories()
        assert len(repos) == 3
        assert "user/repo3" in repos
    
    def test_add_duplicate_repository(self, temp_config):
        """Test adding duplicate repository."""
        initial_repos = temp_config.get_repositories()
        temp_config.add_repository("user/repo1")  # Already exists
        repos = temp_config.get_repositories()
        assert len(repos) == len(initial_repos)  # No change
    
    def test_remove_repository(self, temp_config):
        """Test removing repository."""
        temp_config.remove_repository("user/repo1")
        repos = temp_config.get_repositories()
        assert len(repos) == 1
        assert "user/repo1" not in repos
        assert "user/repo2" in repos
    
    def test_get_daily_goal(self, temp_config):
        """Test getting daily goal."""
        assert temp_config.get_daily_goal() == 10
    
    def test_set_daily_goal(self, temp_config):
        """Test setting daily goal."""
        temp_config.set_daily_goal(20)
        assert temp_config.get_daily_goal() == 20
    
    def test_get_setting(self, temp_config):
        """Test getting setting value."""
        assert temp_config.get_setting('timezone') == 'UTC'
        assert temp_config.get_setting('show_progress') is True
        assert temp_config.get_setting('nonexistent', 'default') == 'default'
    
    def test_set_setting(self, temp_config):
        """Test setting setting value."""
        temp_config.set_setting('timezone', 'EST')
        assert temp_config.get_setting('timezone') == 'EST'
    
    def test_is_configured(self, temp_config):
        """Test configuration status."""
        assert temp_config.is_configured() is True
        
        # Test with empty token
        temp_config.set_github_token("")
        assert temp_config.is_configured() is False
        
        # Test with empty repos
        temp_config.set_github_token("test_token")
        temp_config.config['github']['repos'] = []
        assert temp_config.is_configured() is False
    
    def test_get_rate_limit(self, temp_config):
        """Test getting rate limit."""
        assert temp_config.get_rate_limit() == 5000
    
    def test_set_rate_limit(self, temp_config):
        """Test setting rate limit."""
        temp_config.set_rate_limit(10000)
        assert temp_config.get_rate_limit() == 10000
    
    def test_save_config(self, temp_config):
        """Test saving configuration."""
        temp_config.set_daily_goal(15)
        temp_config.save_config()
        
        # Reload config to verify
        new_config = Config(temp_config.config_path)
        assert new_config.get_daily_goal() == 15
    
    def test_default_config(self):
        """Test default configuration when no file exists."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        # Remove file to test default config
        os.unlink(config_path)
        
        config = Config(config_path)
        assert config.get_github_token() == ""
        assert config.get_repositories() == []
        assert config.get_daily_goal() == 10
        assert config.get_rate_limit() == 5000
