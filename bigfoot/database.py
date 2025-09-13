"""Database operations and schema management for BigFoot."""

import sqlite3
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class Database:
    """SQLite database manager for BigFoot."""
    
    def __init__(self, db_path: str = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to data/bigfoot.db
        """
        if db_path is None:
            # Default to data/bigfoot.db relative to package
            package_dir = Path(__file__).parent
            data_dir = package_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "bigfoot.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    date DATE NOT NULL,
                    count INTEGER DEFAULT 0,
                    lines_added INTEGER DEFAULT 0,
                    lines_deleted INTEGER DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo, date)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS streaks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    length INTEGER NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('daily', 'weekly')),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    date DATE NOT NULL,
                    triggered_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_commits_date ON commits(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_commits_repo_date ON commits(repo, date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_streaks_active ON streaks(is_active)")
            
            conn.commit()
    
    def save_commits(self, commits: List[Dict]) -> None:
        """Save commit data to database.
        
        Args:
            commits: List of commit dictionaries with keys:
                - repo: Repository name
                - date: Date (YYYY-MM-DD)
                - count: Number of commits
                - lines_added: Lines added (optional)
                - lines_deleted: Lines deleted (optional)
        """
        with sqlite3.connect(self.db_path) as conn:
            for commit in commits:
                conn.execute("""
                    INSERT OR REPLACE INTO commits 
                    (repo, date, count, lines_added, lines_deleted)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    commit['repo'],
                    commit['date'],
                    commit['count'],
                    commit.get('lines_added', 0),
                    commit.get('lines_deleted', 0)
                ))
            conn.commit()
    
    def get_commits_by_date(self, target_date: str) -> List[Dict]:
        """Get commits for a specific date.
        
        Args:
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            List of commit dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT repo, date, count, lines_added, lines_deleted
                FROM commits 
                WHERE date = ?
                ORDER BY repo
            """, (target_date,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_commits_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get commits for a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of commit dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT repo, date, count, lines_added, lines_deleted
                FROM commits 
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, repo
            """, (start_date, end_date))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_total_commits_by_date(self, target_date: str) -> int:
        """Get total commit count for a specific date.
        
        Args:
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Total number of commits
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT SUM(count) as total
                FROM commits 
                WHERE date = ?
            """, (target_date,))
            
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
    
    def get_weekly_commits(self, start_date: str, end_date: str) -> int:
        """Get total commits for a week.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Total number of commits for the week
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT SUM(count) as total
                FROM commits 
                WHERE date BETWEEN ? AND ?
            """, (start_date, end_date))
            
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
    
    def calculate_streak(self, target_date: str = None) -> int:
        """Calculate current daily coding streak.
        
        Args:
            target_date: Date to calculate streak from (defaults to today)
            
        Returns:
            Current streak length in days
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all dates with commits, ordered by date descending
            cursor = conn.execute("""
                SELECT DISTINCT date
                FROM commits 
                WHERE count > 0
                ORDER BY date DESC
            """)
            
            commit_dates = [row[0] for row in cursor.fetchall()]
            
            if not commit_dates:
                return 0
            
            # Calculate streak
            streak = 0
            current_date = target_date
            
            for commit_date in commit_dates:
                if commit_date == current_date:
                    streak += 1
                    # Move to previous day
                    from datetime import datetime, timedelta
                    current_dt = datetime.strptime(current_date, '%Y-%m-%d')
                    current_dt -= timedelta(days=1)
                    current_date = current_dt.strftime('%Y-%m-%d')
                else:
                    break
            
            return streak
    
    def save_streak(self, start_date: str, end_date: str, length: int, streak_type: str = 'daily') -> None:
        """Save streak data to database.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (None for active streaks)
            length: Streak length in days
            streak_type: Type of streak ('daily' or 'weekly')
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO streaks (start_date, end_date, length, type, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (start_date, end_date, length, streak_type, end_date is None))
            conn.commit()
    
    def get_active_streak(self) -> Optional[Dict]:
        """Get the current active streak.
        
        Returns:
            Streak dictionary or None if no active streak
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT start_date, end_date, length, type
                FROM streaks 
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_recent_commits(self, days: int = 7) -> List[Dict]:
        """Get recent commits for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of commit dictionaries
        """
        from datetime import datetime, timedelta
        
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days)).isoformat()
        
        return self.get_commits_by_date_range(start_date, end_date)
    
    def get_repositories(self) -> List[str]:
        """Get list of all tracked repositories.
        
        Returns:
            List of repository names
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT repo
                FROM commits 
                ORDER BY repo
            """)
            
            return [row[0] for row in cursor.fetchall()]
