"""Motivational dashboard and analytics engine for BigFoot."""

import os
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum
from .database import Database


class PerformanceLevel(Enum):
    """User performance categorization for motivational messaging."""
    STARTING = "starting"          # New user or low activity
    BUILDING = "building"          # Moderate activity, building momentum  
    CRUSHING = "crushing"          # High performance, on fire!
    LEGENDARY = "legendary"        # Exceptional performance


@dataclass
class StreakData:
    """Streak information and progress."""
    current_streak: int
    longest_streak: int
    next_milestone: int
    goal_progress: float
    days_to_milestone: int
    is_active_today: bool


@dataclass
class MomentumMetrics:
    """Momentum and trend analysis."""
    this_week_commits: int
    last_week_commits: int
    week_over_week_change: float
    daily_trend: List[int]  # Last 7 days
    average_daily: float
    consistency_score: int  # Days active out of 7
    performance_level: PerformanceLevel


@dataclass
class Achievement:
    """Achievement/badge information."""
    id: str
    name: str
    description: str
    emoji: str
    unlocked_date: Optional[str]
    progress: Optional[float] = None


@dataclass
class GoalProgress:
    """Goal tracking and progress."""
    daily_goal: int
    weekly_goal: int
    monthly_goal: int
    daily_current: int
    weekly_current: int
    monthly_current: int
    daily_progress: float
    weekly_progress: float
    monthly_progress: float


class DashboardAnalytics:
    """Analytics engine for dashboard data and insights."""
    
    def __init__(self, database: Database):
        """Initialize analytics with database connection.
        
        Args:
            database: Database instance
        """
        self.database = database
        self.db_path = database.db_path
    
    def get_streak_data(self, target_date: str = None) -> StreakData:
        """Calculate current streak information.
        
        Args:
            target_date: Date to calculate from (defaults to today)
            
        Returns:
            StreakData with current streak and progress
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        current_streak = self.database.calculate_streak(target_date)
        longest_streak = self._get_longest_streak()
        
        # Determine next milestone
        milestones = [7, 14, 21, 30, 50, 75, 100, 200, 365]
        next_milestone = next((m for m in milestones if m > current_streak), 1000)
        days_to_milestone = next_milestone - current_streak
        goal_progress = current_streak / next_milestone if next_milestone > 0 else 1.0
        
        # Check if user coded today
        today_commits = self.database.get_total_commits_by_date(target_date)
        is_active_today = today_commits > 0
        
        return StreakData(
            current_streak=current_streak,
            longest_streak=longest_streak,
            next_milestone=next_milestone,
            goal_progress=goal_progress,
            days_to_milestone=days_to_milestone,
            is_active_today=is_active_today
        )
    
    def calculate_momentum(self, target_date: str = None, days: int = 7) -> MomentumMetrics:
        """Calculate momentum and performance trends.
        
        Args:
            target_date: Reference date (defaults to today)
            days: Number of days to analyze
            
        Returns:
            MomentumMetrics with trend analysis
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        end_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        # Get this week's commits (last 7 days)
        week_start = end_date - timedelta(days=6)
        this_week_commits = self.database.get_weekly_commits(
            week_start.isoformat(), end_date.isoformat()
        )
        
        # Get last week's commits (7 days before that)
        last_week_end = week_start - timedelta(days=1)
        last_week_start = last_week_end - timedelta(days=6)
        last_week_commits = self.database.get_weekly_commits(
            last_week_start.isoformat(), last_week_end.isoformat()
        )
        
        # Calculate week-over-week change
        if last_week_commits > 0:
            week_change = ((this_week_commits - last_week_commits) / last_week_commits) * 100
        else:
            week_change = 100.0 if this_week_commits > 0 else 0.0
        
        # Get daily trend (last 7 days)
        daily_trend = []
        consistency_days = 0
        
        for i in range(days):
            day = end_date - timedelta(days=days-1-i)
            day_commits = self.database.get_total_commits_by_date(day.isoformat())
            daily_trend.append(day_commits)
            if day_commits > 0:
                consistency_days += 1
        
        average_daily = sum(daily_trend) / len(daily_trend) if daily_trend else 0
        
        # Determine performance level
        performance_level = self._categorize_performance(
            this_week_commits, consistency_days, average_daily
        )
        
        return MomentumMetrics(
            this_week_commits=this_week_commits,
            last_week_commits=last_week_commits,
            week_over_week_change=week_change,
            daily_trend=daily_trend,
            average_daily=average_daily,
            consistency_score=consistency_days,
            performance_level=performance_level
        )
    
    def get_achievements(self, target_date: str = None) -> List[Achievement]:
        """Get current achievements and progress.
        
        Args:
            target_date: Reference date for calculations
            
        Returns:
            List of Achievement objects
        """
        achievements = []
        
        # Get current metrics
        streak_data = self.get_streak_data(target_date)
        momentum = self.calculate_momentum(target_date)
        
        # Define achievements with progress calculation
        achievement_defs = [
            # Streak achievements
            {
                'id': 'first_step', 'name': 'First Step', 'emoji': '👶',
                'description': 'Made your first commit', 'threshold': 1,
                'current': max(streak_data.current_streak, streak_data.longest_streak)
            },
            {
                'id': 'fire_starter', 'name': 'Fire Starter', 'emoji': '🔥',
                'description': '3 day coding streak', 'threshold': 3,
                'current': streak_data.current_streak
            },
            {
                'id': 'consistent_coder', 'name': 'Consistent Coder', 'emoji': '⚡',
                'description': '7 day coding streak', 'threshold': 7,
                'current': streak_data.current_streak
            },
            {
                'id': 'streak_master', 'name': 'Streak Master', 'emoji': '🎯',
                'description': '21 day coding streak', 'threshold': 21,
                'current': streak_data.current_streak
            },
            {
                'id': 'code_warrior', 'name': 'Code Warrior', 'emoji': '🎖️',
                'description': '30 day coding streak', 'threshold': 30,
                'current': streak_data.current_streak
            },
            
            # Consistency achievements
            {
                'id': 'perfect_week', 'name': 'Perfect Week', 'emoji': '⭐',
                'description': '7 days of coding in a row', 'threshold': 7,
                'current': momentum.consistency_score
            },
            {
                'id': 'momentum_builder', 'name': 'Momentum Builder', 'emoji': '📈',
                'description': 'Increased weekly commits by 25%+', 'threshold': 25,
                'current': max(0, momentum.week_over_week_change)
            },
        ]
        
        # Create achievement objects
        for achv in achievement_defs:
            is_unlocked = achv['current'] >= achv['threshold']
            progress = min(1.0, achv['current'] / achv['threshold']) if not is_unlocked else None
            
            achievements.append(Achievement(
                id=achv['id'],
                name=achv['name'],
                emoji=achv['emoji'],
                description=achv['description'],
                unlocked_date=target_date if is_unlocked else None,
                progress=progress
            ))
        
        return achievements
    
    def get_goal_progress(self, daily_goal: int = 5, weekly_goal: int = 35, 
                         monthly_goal: int = 100, target_date: str = None) -> GoalProgress:
        """Get progress towards daily, weekly, and monthly goals.
        
        Args:
            daily_goal: Target commits per day
            weekly_goal: Target commits per week  
            monthly_goal: Target commits per month
            target_date: Reference date
            
        Returns:
            GoalProgress with current status
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        end_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        # Daily progress
        daily_current = self.database.get_total_commits_by_date(target_date)
        daily_progress = min(1.0, daily_current / daily_goal) if daily_goal > 0 else 0
        
        # Weekly progress (last 7 days)
        week_start = end_date - timedelta(days=6)
        weekly_current = self.database.get_weekly_commits(
            week_start.isoformat(), end_date.isoformat()
        )
        weekly_progress = min(1.0, weekly_current / weekly_goal) if weekly_goal > 0 else 0
        
        # Monthly progress (this month)
        month_start = end_date.replace(day=1)
        monthly_current = self.database.get_weekly_commits(
            month_start.isoformat(), end_date.isoformat()
        )
        monthly_progress = min(1.0, monthly_current / monthly_goal) if monthly_goal > 0 else 0
        
        return GoalProgress(
            daily_goal=daily_goal,
            weekly_goal=weekly_goal,
            monthly_goal=monthly_goal,
            daily_current=daily_current,
            weekly_current=weekly_current,
            monthly_current=monthly_current,
            daily_progress=daily_progress,
            weekly_progress=weekly_progress,
            monthly_progress=monthly_progress
        )
    
    def generate_heatmap_data(self, days: int = 30, target_date: str = None) -> Dict[str, int]:
        """Generate heatmap data for the last N days.
        
        Args:
            days: Number of days to include
            target_date: End date for heatmap
            
        Returns:
            Dictionary mapping dates to commit counts
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        end_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        start_date = end_date - timedelta(days=days-1)
        
        commits = self.database.get_commits_by_date_range(
            start_date.isoformat(), end_date.isoformat()
        )
        
        # Create date->commits mapping
        heatmap = {}
        current = start_date
        while current <= end_date:
            date_str = current.isoformat()
            heatmap[date_str] = sum(
                commit['count'] for commit in commits 
                if commit['date'] == date_str
            )
            current += timedelta(days=1)
        
        return heatmap
    
    def _get_longest_streak(self) -> int:
        """Calculate the longest ever streak from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT date
                    FROM commits 
                    WHERE count > 0
                    ORDER BY date ASC
                """)
                
                commit_dates = [row[0] for row in cursor.fetchall()]
                
                if not commit_dates:
                    return 0
                
                max_streak = 1
                current_streak = 1
                
                for i in range(1, len(commit_dates)):
                    prev_date = datetime.strptime(commit_dates[i-1], '%Y-%m-%d').date()
                    curr_date = datetime.strptime(commit_dates[i], '%Y-%m-%d').date()
                    
                    if (curr_date - prev_date).days == 1:
                        current_streak += 1
                        max_streak = max(max_streak, current_streak)
                    else:
                        current_streak = 1
                
                return max_streak
                
        except Exception:
            return 0
    
    def _categorize_performance(self, week_commits: int, consistency: int, 
                              daily_avg: float) -> PerformanceLevel:
        """Categorize user performance level for motivational messaging.
        
        Args:
            week_commits: Total commits this week
            consistency: Days active out of 7
            daily_avg: Average daily commits
            
        Returns:
            PerformanceLevel enum
        """
        # Legendary: exceptional performance across all metrics
        if week_commits >= 50 and consistency >= 6 and daily_avg >= 7:
            return PerformanceLevel.LEGENDARY
        
        # Crushing: high performance, on fire
        elif week_commits >= 25 and consistency >= 5 and daily_avg >= 4:
            return PerformanceLevel.CRUSHING
        
        # Building: moderate activity, building momentum
        elif week_commits >= 10 and consistency >= 3 and daily_avg >= 2:
            return PerformanceLevel.BUILDING
        
        # Starting: new user or low activity
        else:
            return PerformanceLevel.STARTING
