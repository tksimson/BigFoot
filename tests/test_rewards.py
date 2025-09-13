"""Tests for rewards module."""

import pytest
import tempfile
import os
from datetime import date, timedelta
from bigfoot.rewards import RewardsEngine
from bigfoot.config import Config
from bigfoot.database import Database


class TestRewardsEngine:
    """Test cases for RewardsEngine class."""
    
    @pytest.fixture
    def temp_components(self):
        """Create temporary components for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
github:
  token: "test_token"
  repos: ["user/repo1"]
settings:
  daily_goal: 10
            """)
            config_path = f.name
        
        database = Database(db_path)
        config = Config(config_path)
        rewards = RewardsEngine(database, config)
        
        yield rewards, database, config
        
        # Cleanup
        os.unlink(db_path)
        os.unlink(config_path)
    
    def test_check_streak_achievements(self, temp_components):
        """Test streak achievement checking."""
        rewards, database, config = temp_components
        
        # Test milestone achievements
        achievements = rewards._check_streak_achievements(7, "2024-01-01")
        assert len(achievements) == 1
        assert achievements[0]['type'] == 'streak_milestone'
        assert "7 Day Streak" in achievements[0]['message']
        
        # Test no achievement for non-milestone
        achievements = rewards._check_streak_achievements(6, "2024-01-01")
        assert len(achievements) == 0
    
    def test_check_commit_achievements(self, temp_components):
        """Test commit achievement checking."""
        rewards, database, config = temp_components
        
        # Test daily commit milestone
        achievements = rewards._check_commit_achievements(10, "2024-01-01")
        assert len(achievements) == 2  # Both milestone and goal
        achievement_types = [a['type'] for a in achievements]
        assert 'daily_commits' in achievement_types
        assert 'daily_goal' in achievement_types
        
        # Test daily goal achievement
        achievements = rewards._check_commit_achievements(10, "2024-01-01")
        assert len(achievements) == 2  # Both milestone and goal
        goal_achievement = next(a for a in achievements if a['type'] == 'daily_goal')
        assert "Daily Goal Achieved" in goal_achievement['message']
    
    def test_check_consistency_achievements(self, temp_components):
        """Test consistency achievement checking."""
        rewards, database, config = temp_components
        
        # Add commits for the week
        today = date.today()
        for i in range(7):
            commit_date = (today - timedelta(days=i)).isoformat()
            database.save_commits([{
                'repo': 'user/repo1',
                'date': commit_date,
                'count': 10,  # 10 commits per day = 70 total
                'lines_added': 100,
                'lines_deleted': 20
            }])
        
        achievements = rewards._check_consistency_achievements(today.isoformat())
        assert len(achievements) == 1
        assert achievements[0]['type'] == 'weekly_consistency'
        assert "commits this week" in achievements[0]['message']
    
    def test_save_achievement(self, temp_components):
        """Test saving achievement to database."""
        rewards, database, config = temp_components
        
        achievement = {
            'type': 'test_achievement',
            'message': 'Test achievement message',
            'date': '2024-01-01',
            'triggered_by': 'test_trigger'
        }
        
        rewards._save_achievement(achievement)
        
        # Verify achievement was saved
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT * FROM rewards WHERE type = 'test_achievement'")
            result = cursor.fetchone()
            assert result is not None
            assert result[1] == 'test_achievement'  # type
            assert result[2] == 'Test achievement message'  # message
    
    def test_get_recent_achievements(self, temp_components):
        """Test getting recent achievements."""
        rewards, database, config = temp_components
        
        # Add some achievements
        achievements = [
            {
                'type': 'test1',
                'message': 'Test 1',
                'date': (date.today() - timedelta(days=1)).isoformat(),
                'triggered_by': 'test1'
            },
            {
                'type': 'test2',
                'message': 'Test 2',
                'date': (date.today() - timedelta(days=3)).isoformat(),
                'triggered_by': 'test2'
            }
        ]
        
        for achievement in achievements:
            rewards._save_achievement(achievement)
        
        recent = rewards.get_recent_achievements(7)
        assert len(recent) == 2
        assert recent[0]['type'] == 'test1'  # More recent first
    
    def test_get_achievement_stats(self, temp_components):
        """Test getting achievement statistics."""
        rewards, database, config = temp_components
        
        # Add some achievements
        achievements = [
            {'type': 'streak', 'message': 'Streak 1', 'date': '2024-01-01', 'triggered_by': 'test'},
            {'type': 'streak', 'message': 'Streak 2', 'date': '2024-01-02', 'triggered_by': 'test'},
            {'type': 'commits', 'message': 'Commits 1', 'date': '2024-01-03', 'triggered_by': 'test'}
        ]
        
        for achievement in achievements:
            rewards._save_achievement(achievement)
        
        stats = rewards.get_achievement_stats()
        assert stats['total_achievements'] == 3
        assert stats['by_type']['streak'] == 2
        assert stats['by_type']['commits'] == 1
    
    def test_get_motivational_message(self, temp_components):
        """Test motivational message generation."""
        rewards, database, config = temp_components
        
        # Test zero streak
        message = rewards.get_motivational_message(0, 0, 10)
        assert "journey starts" in message.lower()
        
        # Test good progress
        message = rewards.get_motivational_message(8, 5, 10)
        assert "progress" in message.lower() or "great" in message.lower()
        
        # Test long streak
        message = rewards.get_motivational_message(5, 15, 10)
        assert "streak" in message.lower() or "unstoppable" in message.lower()
    
    def test_get_progress_encouragement(self, temp_components):
        """Test progress encouragement generation."""
        rewards, database, config = temp_components
        
        # Test different progress levels
        message = rewards.get_progress_encouragement(2, 10)
        assert "getting started" in message.lower()
        
        message = rewards.get_progress_encouragement(5, 10)
        assert "progress" in message.lower() or "halfway" in message.lower()
        
        message = rewards.get_progress_encouragement(8, 10)
        assert "halfway" in message.lower() or "close" in message.lower()
        
        message = rewards.get_progress_encouragement(10, 10)
        assert "goal" in message.lower()
        
        message = rewards.get_progress_encouragement(15, 10)
        assert "unstoppable" in message.lower()
    
    def test_check_achievements_integration(self, temp_components):
        """Test full achievement checking integration."""
        rewards, database, config = temp_components
        
        # Test with good progress
        achievements = rewards.check_achievements(10, 7, "2024-01-01")
        
        # Should have both commit and streak achievements
        assert len(achievements) >= 1
        achievement_types = [a['type'] for a in achievements]
        assert 'daily_commits' in achievement_types or 'daily_goal' in achievement_types
        assert 'streak_milestone' in achievement_types
