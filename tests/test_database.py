"""Tests for database module."""

import pytest
import tempfile
import os
from datetime import date, timedelta
from bigfoot.database import Database


class TestDatabase:
    """Test cases for Database class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = Database(db_path)
        yield db
        
        # Cleanup
        os.unlink(db_path)
    
    def test_database_initialization(self, temp_db):
        """Test database initialization creates required tables."""
        import sqlite3
        
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
        
        assert 'commits' in tables
        assert 'streaks' in tables
        assert 'rewards' in tables
    
    def test_save_commits(self, temp_db):
        """Test saving commit data."""
        commits = [
            {
                'repo': 'user/repo1',
                'date': '2024-01-01',
                'count': 5,
                'lines_added': 50,
                'lines_deleted': 10
            },
            {
                'repo': 'user/repo2',
                'date': '2024-01-01',
                'count': 3,
                'lines_added': 30,
                'lines_deleted': 5
            }
        ]
        
        temp_db.save_commits(commits)
        
        # Verify data was saved
        saved_commits = temp_db.get_commits_by_date('2024-01-01')
        assert len(saved_commits) == 2
        assert saved_commits[0]['repo'] == 'user/repo1'
        assert saved_commits[0]['count'] == 5
        assert saved_commits[1]['repo'] == 'user/repo2'
        assert saved_commits[1]['count'] == 3
    
    def test_get_total_commits_by_date(self, temp_db):
        """Test getting total commits for a date."""
        commits = [
            {'repo': 'user/repo1', 'date': '2024-01-01', 'count': 5, 'lines_added': 50, 'lines_deleted': 10},
            {'repo': 'user/repo2', 'date': '2024-01-01', 'count': 3, 'lines_added': 30, 'lines_deleted': 5}
        ]
        
        temp_db.save_commits(commits)
        
        total = temp_db.get_total_commits_by_date('2024-01-01')
        assert total == 8
    
    def test_calculate_streak(self, temp_db):
        """Test streak calculation."""
        # Add commits for consecutive days
        today = date.today()
        for i in range(5):
            commit_date = (today - timedelta(days=i)).isoformat()
            commits = [{
                'repo': 'user/repo1',
                'date': commit_date,
                'count': 1,
                'lines_added': 10,
                'lines_deleted': 2
            }]
            temp_db.save_commits(commits)
        
        streak = temp_db.calculate_streak()
        assert streak == 5
    
    def test_calculate_streak_with_gap(self, temp_db):
        """Test streak calculation with gaps."""
        today = date.today()
        
        # Add commits for 3 consecutive days
        for i in range(3):
            commit_date = (today - timedelta(days=i)).isoformat()
            commits = [{
                'repo': 'user/repo1',
                'date': commit_date,
                'count': 1,
                'lines_added': 10,
                'lines_deleted': 2
            }]
            temp_db.save_commits(commits)
        
        # Add gap (no commits for 2 days)
        # Add commits for 2 more days
        for i in range(5, 7):
            commit_date = (today - timedelta(days=i)).isoformat()
            commits = [{
                'repo': 'user/repo1',
                'date': commit_date,
                'count': 1,
                'lines_added': 10,
                'lines_deleted': 2
            }]
            temp_db.save_commits(commits)
        
        # Streak should be 3 (most recent consecutive days)
        streak = temp_db.calculate_streak()
        assert streak == 3
    
    def test_get_commits_by_date_range(self, temp_db):
        """Test getting commits by date range."""
        # Add commits for different dates
        dates = ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-05']
        for commit_date in dates:
            commits = [{
                'repo': 'user/repo1',
                'date': commit_date,
                'count': 1,
                'lines_added': 10,
                'lines_deleted': 2
            }]
            temp_db.save_commits(commits)
        
        # Get commits for range
        commits = temp_db.get_commits_by_date_range('2024-01-01', '2024-01-03')
        assert len(commits) == 3
        
        # Verify dates are in range
        commit_dates = [commit['date'] for commit in commits]
        assert '2024-01-01' in commit_dates
        assert '2024-01-02' in commit_dates
        assert '2024-01-03' in commit_dates
        assert '2024-01-05' not in commit_dates
    
    def test_get_repositories(self, temp_db):
        """Test getting list of repositories."""
        commits = [
            {'repo': 'user/repo1', 'date': '2024-01-01', 'count': 1, 'lines_added': 10, 'lines_deleted': 2},
            {'repo': 'user/repo2', 'date': '2024-01-01', 'count': 1, 'lines_added': 10, 'lines_deleted': 2},
            {'repo': 'user/repo1', 'date': '2024-01-02', 'count': 1, 'lines_added': 10, 'lines_deleted': 2}
        ]
        
        temp_db.save_commits(commits)
        
        repos = temp_db.get_repositories()
        assert len(repos) == 2
        assert 'user/repo1' in repos
        assert 'user/repo2' in repos
    
    def test_save_streak(self, temp_db):
        """Test saving streak data."""
        temp_db.save_streak('2024-01-01', '2024-01-05', 5, 'daily')
        
        # Verify streak was saved
        import sqlite3
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT * FROM streaks WHERE length = 5")
            result = cursor.fetchone()
            assert result is not None
            assert result[1] == '2024-01-01'  # start_date
            assert result[2] == '2024-01-05'  # end_date
            assert result[3] == 5  # length
            assert result[4] == 'daily'  # type
    
    def test_get_active_streak(self, temp_db):
        """Test getting active streak."""
        # Save an active streak
        temp_db.save_streak('2024-01-01', None, 5, 'daily')
        
        # Save an inactive streak
        temp_db.save_streak('2023-12-01', '2023-12-10', 10, 'daily')
        
        active_streak = temp_db.get_active_streak()
        assert active_streak is not None
        assert active_streak['length'] == 5
        assert active_streak['start_date'] == '2024-01-01'
