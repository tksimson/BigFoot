"""Tests for utils module."""

import pytest
from bigfoot.utils import (
    format_progress_bar, format_streak_display, format_commit_count,
    validate_repo_name, get_week_dates, get_recent_dates,
    get_motivational_message
)


class TestUtils:
    """Test cases for utility functions."""
    
    def test_format_progress_bar(self):
        """Test progress bar formatting."""
        # Test with goal
        bar = format_progress_bar(5, 10, 10)
        assert "█████░░░░░" in bar
        assert "50%" in bar
        assert "(5/10)" in bar
        
        # Test with zero goal
        bar = format_progress_bar(5, 0, 10)
        assert "░░░░░░░░░░" in bar
        
        # Test with exceeded goal
        bar = format_progress_bar(15, 10, 10)
        assert "██████████" in bar
        assert "150%" in bar
        assert "(15/10)" in bar
    
    def test_format_streak_display(self):
        """Test streak display formatting."""
        # Test zero streak
        display = format_streak_display(0)
        assert "No active streak" in display
        assert "❄️" in display
        
        # Test short streak
        display = format_streak_display(2)
        assert "2 days" in display
        assert "🔥" in display
        
        # Test long streak
        display = format_streak_display(30)
        assert "30 days" in display
        assert "🔥" in display
    
    def test_format_commit_count(self):
        """Test commit count formatting."""
        # Test zero commits
        display = format_commit_count(0)
        assert "No commits today" in display
        assert "😴" in display
        
        # Test few commits
        display = format_commit_count(2)
        assert "2 commits today" in display
        assert "📝" in display
        
        # Test many commits
        display = format_commit_count(15)
        assert "15 commits today" in display
        assert "🚀" in display
    
    def test_validate_repo_name(self):
        """Test repository name validation."""
        # Valid repos
        assert validate_repo_name("user/repo") is True
        assert validate_repo_name("org/project") is True
        assert validate_repo_name("user123/repo456") is True
        
        # Invalid repos
        assert validate_repo_name("") is False
        assert validate_repo_name("user") is False
        assert validate_repo_name("user/") is False
        assert validate_repo_name("/repo") is False
        assert validate_repo_name("user/repo/extra") is False
        assert validate_repo_name("user /repo") is False
        assert validate_repo_name("user<repo") is False
        assert validate_repo_name("user:repo") is False
    
    def test_get_week_dates(self):
        """Test getting week dates."""
        # Test with specific date (Monday)
        dates = get_week_dates("2024-01-01")  # Monday
        assert len(dates) == 7
        assert "2024-01-01" in dates  # Monday
        assert "2024-01-07" in dates  # Sunday
        
        # Test with Wednesday
        dates = get_week_dates("2024-01-03")  # Wednesday
        assert len(dates) == 7
        assert "2024-01-01" in dates  # Monday
        assert "2024-01-03" in dates  # Wednesday
        assert "2024-01-07" in dates  # Sunday
    
    def test_get_recent_dates(self):
        """Test getting recent dates."""
        dates = get_recent_dates(5)
        assert len(dates) == 5
        
        # Should be consecutive days
        from datetime import date, timedelta
        today = date.today()
        expected_dates = [(today - timedelta(days=i)).isoformat() for i in range(5)]
        assert dates == expected_dates
    
    def test_get_motivational_message(self):
        """Test motivational message generation."""
        # Test with zero commits
        message = get_motivational_message(0, 0, 10)
        assert "journey starts" in message.lower()
        
        # Test with good progress
        message = get_motivational_message(8, 5, 10)
        assert "progress" in message.lower() or "great" in message.lower() or "crushing" in message.lower()
        
        # Test with goal achieved
        message = get_motivational_message(10, 5, 10)
        assert "goal" in message.lower() or "achieved" in message.lower() or "crushing" in message.lower()
        
        # Test with long streak
        message = get_motivational_message(5, 10, 10)
        assert "streak" in message.lower() or "unstoppable" in message.lower() or "progress" in message.lower()
