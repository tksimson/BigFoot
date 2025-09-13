"""Motivation engine and achievements for BigFoot."""

from datetime import date, timedelta
from typing import List, Dict, Optional
from .database import Database
from .config import Config


class RewardsEngine:
    """Motivation engine for tracking achievements and rewards."""
    
    def __init__(self, database: Database, config: Config):
        """Initialize rewards engine.
        
        Args:
            database: Database instance
            config: Configuration instance
        """
        self.database = database
        self.config = config
    
    def check_achievements(self, commits: int, streak: int, date: str = None) -> List[Dict]:
        """Check for new achievements based on current progress.
        
        Args:
            commits: Number of commits today
            streak: Current streak length
            date: Date to check achievements for (defaults to today)
            
        Returns:
            List of new achievement dictionaries
        """
        if date is None:
            date = date.today().isoformat()
        
        achievements = []
        
        # Streak achievements
        streak_achievements = self._check_streak_achievements(streak, date)
        achievements.extend(streak_achievements)
        
        # Commit volume achievements
        commit_achievements = self._check_commit_achievements(commits, date)
        achievements.extend(commit_achievements)
        
        # Consistency achievements
        consistency_achievements = self._check_consistency_achievements(date)
        achievements.extend(consistency_achievements)
        
        # Save new achievements
        for achievement in achievements:
            self._save_achievement(achievement)
        
        return achievements
    
    def _check_streak_achievements(self, streak: int, date: str) -> List[Dict]:
        """Check for streak-based achievements.
        
        Args:
            streak: Current streak length
            date: Date to check
            
        Returns:
            List of streak achievements
        """
        achievements = []
        
        # Check if this is a new milestone
        milestones = [3, 7, 14, 30, 60, 100]
        
        for milestone in milestones:
            if streak == milestone:
                achievements.append({
                    'type': 'streak_milestone',
                    'message': f"🔥 {milestone} Day Streak! You're on fire!",
                    'date': date,
                    'triggered_by': f'streak_{milestone}'
                })
        
        return achievements
    
    def _check_commit_achievements(self, commits: int, date: str) -> List[Dict]:
        """Check for commit volume achievements.
        
        Args:
            commits: Number of commits today
            date: Date to check
            
        Returns:
            List of commit achievements
        """
        achievements = []
        
        # Daily commit milestones
        milestones = [5, 10, 20, 50]
        
        for milestone in milestones:
            if commits == milestone:
                achievements.append({
                    'type': 'daily_commits',
                    'message': f"🚀 {milestone} Commits Today! Amazing productivity!",
                    'date': date,
                    'triggered_by': f'daily_commits_{milestone}'
                })
        
        # Goal achievement
        daily_goal = self.config.get_daily_goal()
        if commits >= daily_goal:
            achievements.append({
                'type': 'daily_goal',
                'message': f"🎯 Daily Goal Achieved! {commits}/{daily_goal} commits",
                'date': date,
                'triggered_by': 'daily_goal_met'
            })
        
        return achievements
    
    def _check_consistency_achievements(self, date: str) -> List[Dict]:
        """Check for consistency-based achievements.
        
        Args:
            date: Date to check
            
        Returns:
            List of consistency achievements
        """
        achievements = []
        
        # Check weekly consistency
        week_dates = self._get_week_dates(date)
        week_commits = 0
        
        for week_date in week_dates:
            commits = self.database.get_total_commits_by_date(week_date)
            week_commits += commits
        
        # Weekly consistency milestones
        if week_commits >= 50:
            achievements.append({
                'type': 'weekly_consistency',
                'message': f"📈 {week_commits} commits this week! Consistent progress!",
                'date': date,
                'triggered_by': 'weekly_50_commits'
            })
        
        return achievements
    
    def _get_week_dates(self, target_date: str) -> List[str]:
        """Get dates for the week containing target_date.
        
        Args:
            target_date: Target date in YYYY-MM-DD format
            
        Returns:
            List of dates in YYYY-MM-DD format
        """
        target = date.fromisoformat(target_date)
        monday = target - timedelta(days=target.weekday())
        
        week_dates = []
        for i in range(7):
            week_date = monday + timedelta(days=i)
            week_dates.append(week_date.isoformat())
        
        return week_dates
    
    def _save_achievement(self, achievement: Dict) -> None:
        """Save achievement to database.
        
        Args:
            achievement: Achievement dictionary
        """
        import sqlite3
        with sqlite3.connect(self.database.db_path) as conn:
            conn.execute("""
                INSERT INTO rewards (type, message, date, triggered_by)
                VALUES (?, ?, ?, ?)
            """, (
                achievement['type'],
                achievement['message'],
                achievement['date'],
                achievement['triggered_by']
            ))
            conn.commit()
    
    def get_recent_achievements(self, days: int = 7) -> List[Dict]:
        """Get recent achievements.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent achievements
        """
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days)).isoformat()
        
        import sqlite3
        with sqlite3.connect(self.database.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT type, message, date, triggered_by, created_at
                FROM rewards 
                WHERE date BETWEEN ? AND ?
                ORDER BY created_at DESC
            """, (start_date, end_date))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_achievement_stats(self) -> Dict:
        """Get overall achievement statistics.
        
        Returns:
            Dictionary with achievement stats
        """
        import sqlite3
        with sqlite3.connect(self.database.db_path) as conn:
            # Total achievements
            cursor = conn.execute("SELECT COUNT(*) FROM rewards")
            total_achievements = cursor.fetchone()[0]
            
            # Achievements by type
            cursor = conn.execute("""
                SELECT type, COUNT(*) as count
                FROM rewards 
                GROUP BY type
                ORDER BY count DESC
            """)
            
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Recent achievements (last 30 days)
            thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
            cursor = conn.execute("""
                SELECT COUNT(*) FROM rewards 
                WHERE date >= ?
            """, (thirty_days_ago,))
            
            recent_achievements = cursor.fetchone()[0]
            
            return {
                'total_achievements': total_achievements,
                'by_type': by_type,
                'recent_achievements': recent_achievements
            }
    
    def get_motivational_message(self, commits: int, streak: int, goal: int) -> str:
        """Get contextual motivational message.
        
        Args:
            commits: Number of commits today
            streak: Current streak length
            goal: Daily goal
            
        Returns:
            Motivational message
        """
        # Streak-based messages
        if streak == 0:
            return "💡 Every journey starts with a single commit!"
        elif streak < 3:
            return f"🌱 {streak} day streak! Keep building momentum!"
        elif streak < 7:
            return f"💪 {streak} day streak! You're building great habits!"
        elif streak < 30:
            return f"🔥 {streak} day streak! You're on fire!"
        else:
            return f"🏆 {streak} day streak! You're unstoppable!"
        
        # Commit-based messages
        if commits == 0:
            return "😴 No commits today - time to get coding!"
        elif commits < goal * 0.5:
            return "🌱 Great start! Every commit counts!"
        elif commits < goal:
            return f"⚡ {commits} commits today! You're making progress!"
        elif commits == goal:
            return f"🎯 Goal achieved! {commits}/{goal} commits - perfect!"
        elif commits < goal * 1.5:
            return f"🚀 {commits} commits! Exceeding expectations!"
        else:
            return f"🏆 {commits} commits! You're crushing it!"
    
    def get_progress_encouragement(self, commits: int, goal: int) -> str:
        """Get progress-based encouragement.
        
        Args:
            commits: Number of commits today
            goal: Daily goal
            
        Returns:
            Encouragement message
        """
        if goal == 0:
            return "Set a daily goal to track your progress!"
        
        percentage = (commits / goal) * 100
        
        if percentage < 25:
            return "💡 You're just getting started - keep going!"
        elif percentage < 50:
            return "🌱 Making good progress - you've got this!"
        elif percentage < 75:
            return "⚡ You're more than halfway there!"
        elif percentage < 100:
            return "🎯 So close to your goal - push through!"
        elif percentage < 150:
            return "🚀 Goal achieved and then some - amazing!"
        else:
            return "🏆 Blowing past your goal - you're unstoppable!"
