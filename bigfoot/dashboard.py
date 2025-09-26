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


@dataclass
class PersonalRecord:
    """Personal best performance record."""
    record_type: str  # 'daily_commits', 'daily_lines', 'weekly_commits', etc.
    value: int
    date: str
    description: str


@dataclass
class HallOfFame:
    """Hall of Fame with personal records and achievements."""
    best_single_day_commits: PersonalRecord
    best_single_day_lines: PersonalRecord
    best_week_commits: PersonalRecord
    current_day_commits: int
    current_day_lines: int
    days_until_record: int  # Days since last record was set
    record_chase_progress: float  # How close to beating current record


@dataclass 
class HistoricalPeriod:
    """Single time period data for historical charts."""
    label: str              # Display label (e.g., "Mar 15", "W12", "March")
    start_date: str         # ISO date string
    end_date: str           # ISO date string  
    commits: int            # Total commits in period
    period_type: str        # 'daily', 'weekly', 'monthly'


@dataclass
class HistoricalData:
    """Complete historical chart data and analysis."""
    periods: List[HistoricalPeriod]
    chart_type: str                    # 'daily', 'weekly', 'monthly'
    total_commits: int
    peak_commits: int
    average_commits: float
    trend_direction: str               # 'up', 'down', 'stable'
    trend_percentage: float
    date_range_label: str              # "Last 90 days", "Last 13 weeks", etc.


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
        # Ensure target_date is set for unlocked_date field
        if target_date is None:
            target_date = date.today().isoformat()
        
        achievements = []
        
        # Get current metrics
        streak_data = self.get_streak_data(target_date)
        momentum = self.calculate_momentum(target_date)
        
        # Get current daily performance for volume achievements
        today_commits = self.database.get_total_commits_by_date(target_date)
        today_lines = self._get_daily_lines(target_date)
        hall_of_fame = self.get_hall_of_fame(target_date)
        
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
            
            # Volume achievements - Daily Commits
            {
                'id': 'commit_surge', 'name': 'Commit Surge', 'emoji': '💥',
                'description': '5 commits in one day', 'threshold': 5,
                'current': hall_of_fame.best_single_day_commits.value
            },
            {
                'id': 'commit_storm', 'name': 'Commit Storm', 'emoji': '⛈️',
                'description': '8 commits in one day', 'threshold': 8,
                'current': hall_of_fame.best_single_day_commits.value
            },
            {
                'id': 'commit_hurricane', 'name': 'Commit Hurricane', 'emoji': '🌪️',
                'description': '12 commits in one day', 'threshold': 12,
                'current': hall_of_fame.best_single_day_commits.value
            },
            {
                'id': 'commit_legend', 'name': 'Commit Legend', 'emoji': '👑',
                'description': '15 commits in one day', 'threshold': 15,
                'current': hall_of_fame.best_single_day_commits.value
            },
            
            # Volume achievements - Daily Lines
            {
                'id': 'line_crusher', 'name': 'Line Crusher', 'emoji': '💪',
                'description': '1,000 lines in one day', 'threshold': 1000,
                'current': hall_of_fame.best_single_day_lines.value
            },
            {
                'id': 'code_beast', 'name': 'Code Beast', 'emoji': '🦁',
                'description': '5,000 lines in one day', 'threshold': 5000,
                'current': hall_of_fame.best_single_day_lines.value
            },
            {
                'id': 'coding_machine', 'name': 'Coding Machine', 'emoji': '🤖',
                'description': '10,000 lines in one day', 'threshold': 10000,
                'current': hall_of_fame.best_single_day_lines.value
            },
            {
                'id': 'line_god', 'name': 'Line God', 'emoji': '🚀',
                'description': '50,000 lines in one day', 'threshold': 50000,
                'current': hall_of_fame.best_single_day_lines.value
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
    
    def _get_daily_lines(self, target_date: str) -> int:
        """Get total lines of code changed on a specific date.
        
        Args:
            target_date: Date to get lines for
            
        Returns:
            Total lines added + deleted for the date
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT SUM(lines_added + lines_deleted)
                FROM commits
                WHERE date = ?
            """, (target_date,))
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
    
    def get_hall_of_fame(self, target_date: str = None) -> HallOfFame:
        """Get Hall of Fame with personal records and current performance.
        
        Args:
            target_date: Reference date for calculations
            
        Returns:
            HallOfFame with personal records and progress
        """
        if target_date is None:
            target_date = date.today().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get best single day for commits
            cursor = conn.execute("""
                SELECT date, SUM(count) as daily_commits
                FROM commits 
                GROUP BY date 
                ORDER BY daily_commits DESC 
                LIMIT 1
            """)
            best_commits_row = cursor.fetchone()
            
            if best_commits_row:
                best_commits_record = PersonalRecord(
                    record_type="daily_commits",
                    value=best_commits_row[1],
                    date=best_commits_row[0],
                    description=f"{best_commits_row[1]} commits in one day"
                )
            else:
                best_commits_record = PersonalRecord("daily_commits", 0, target_date, "No commits yet")
            
            # Get best single day for lines
            cursor = conn.execute("""
                SELECT date, SUM(lines_added + lines_deleted) as daily_lines
                FROM commits 
                GROUP BY date 
                ORDER BY daily_lines DESC 
                LIMIT 1
            """)
            best_lines_row = cursor.fetchone()
            
            if best_lines_row:
                best_lines_record = PersonalRecord(
                    record_type="daily_lines",
                    value=best_lines_row[1],
                    date=best_lines_row[0],
                    description=f"{best_lines_row[1]:,} lines in one day"
                )
            else:
                best_lines_record = PersonalRecord("daily_lines", 0, target_date, "No lines yet")
            
            # Get best week for commits
            cursor = conn.execute("""
                SELECT 
                    date,
                    SUM(count) OVER (
                        ORDER BY date 
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                    ) as week_commits
                FROM (
                    SELECT date, SUM(count) as count
                    FROM commits
                    GROUP BY date
                    ORDER BY date
                )
                ORDER BY week_commits DESC
                LIMIT 1
            """)
            best_week_row = cursor.fetchone()
            
            if best_week_row:
                best_week_record = PersonalRecord(
                    record_type="weekly_commits",
                    value=best_week_row[1],
                    date=best_week_row[0],
                    description=f"{best_week_row[1]} commits in one week"
                )
            else:
                best_week_record = PersonalRecord("weekly_commits", 0, target_date, "No weekly data yet")
            
            # Get current day performance
            current_day_commits = self.database.get_total_commits_by_date(target_date)
            current_day_lines = self._get_daily_lines(target_date)
            
            # Calculate days since last record (simplified - just check if today beat a record)
            days_since_record = 0  # Could be expanded to calculate actual days
            
            # Calculate progress toward beating current record
            if best_commits_record.value > 0:
                record_chase_progress = min(1.0, current_day_commits / best_commits_record.value)
            else:
                record_chase_progress = 0.0
        
        return HallOfFame(
            best_single_day_commits=best_commits_record,
            best_single_day_lines=best_lines_record,
            best_week_commits=best_week_record,
            current_day_commits=current_day_commits,
            current_day_lines=current_day_lines,
            days_until_record=days_since_record,
            record_chase_progress=record_chase_progress
        )
    
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
    
    def get_historical_data(self, chart_type: str = 'daily', periods: int = None) -> HistoricalData:
        """Get historical commit data for charts.
        
        Args:
            chart_type: 'daily', 'weekly', or 'monthly'
            periods: Number of periods to include (auto-calculated if None)
            
        Returns:
            HistoricalData with periods and analysis
        """
        if chart_type == 'daily':
            return self._get_daily_historical_data(periods or 90)
        elif chart_type == 'weekly':
            return self._get_weekly_historical_data(periods or 13)
        elif chart_type == 'monthly':
            return self._get_monthly_historical_data(periods or 3)
        else:
            raise ValueError(f"Invalid chart_type: {chart_type}")
    
    def _get_daily_historical_data(self, days: int) -> HistoricalData:
        """Get daily commit data for the last N days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get raw commit data
        raw_data = self.database.get_commits_by_date_range(
            start_date.isoformat(), 
            end_date.isoformat()
        )
        
        # Create date-to-commits mapping
        commits_by_date = {}
        for commit in raw_data:
            date_key = commit['date']
            commits_by_date[date_key] = commits_by_date.get(date_key, 0) + commit['count']
        
        # Build periods list
        periods = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            commits_count = commits_by_date.get(date_str, 0)
            
            # Create readable label (e.g., "Mar 15")
            label = current_date.strftime("%b %d")
            
            periods.append(HistoricalPeriod(
                label=label,
                start_date=date_str,
                end_date=date_str,
                commits=commits_count,
                period_type='daily'
            ))
            
            current_date += timedelta(days=1)
        
        return self._calculate_historical_metrics(periods, 'daily', f'Last {days} days')
    
    def _get_weekly_historical_data(self, weeks: int) -> HistoricalData:
        """Get weekly commit data for the last N weeks."""
        periods = []
        
        for week_offset in range(weeks):
            week_end = date.today() - timedelta(days=week_offset*7)
            week_start = week_end - timedelta(days=6)
            
            # Get commits for this week
            weekly_commits = self.database.get_weekly_commits(
                week_start.isoformat(), 
                week_end.isoformat()
            )
            
            # Create readable label (e.g., "W12")
            week_number = weeks - week_offset
            label = f"W{week_number}"
            
            periods.append(HistoricalPeriod(
                label=label,
                start_date=week_start.isoformat(),
                end_date=week_end.isoformat(),
                commits=weekly_commits,
                period_type='weekly'
            ))
        
        # Reverse to show oldest first
        periods.reverse()
        
        return self._calculate_historical_metrics(periods, 'weekly', f'Last {weeks} weeks')
    
    def _get_monthly_historical_data(self, months: int) -> HistoricalData:
        """Get monthly commit data for the last N months."""
        periods = []
        
        current_date = date.today()
        
        for month_offset in range(months):
            # Calculate target month
            if month_offset == 0:
                target_date = current_date
            else:
                target_date = current_date.replace(day=1) - timedelta(days=1)
                for _ in range(month_offset - 1):
                    target_date = target_date.replace(day=1) - timedelta(days=1)
            
            # Get first and last day of month
            month_start = target_date.replace(day=1)
            if month_offset == 0:
                # Current month: up to today
                month_end = current_date
            else:
                # Previous months: full month
                next_month = month_start.replace(day=28) + timedelta(days=4)
                month_end = (next_month - timedelta(days=next_month.day)).replace(day=1) + timedelta(days=31)
                month_end = month_end.replace(day=1) - timedelta(days=1)
            
            # Get commits for this month
            monthly_commits = sum(
                commit['count'] for commit in self.database.get_commits_by_date_range(
                    month_start.isoformat(),
                    month_end.isoformat()
                )
            )
            
            # Create readable label (e.g., "March")
            label = target_date.strftime("%B")
            if months > 12:  # Include year if spanning multiple years
                label = target_date.strftime("%b %Y")
            
            periods.append(HistoricalPeriod(
                label=label,
                start_date=month_start.isoformat(),
                end_date=month_end.isoformat(),
                commits=monthly_commits,
                period_type='monthly'
            ))
        
        # Reverse to show oldest first
        periods.reverse()
        
        return self._calculate_historical_metrics(periods, 'monthly', f'Last {months} months')
    
    def _calculate_historical_metrics(self, periods: List[HistoricalPeriod], 
                                    chart_type: str, date_range_label: str) -> HistoricalData:
        """Calculate metrics and trends from historical periods."""
        if not periods:
            return HistoricalData(
                periods=[],
                chart_type=chart_type,
                total_commits=0,
                peak_commits=0,
                average_commits=0.0,
                trend_direction='stable',
                trend_percentage=0.0,
                date_range_label=date_range_label
            )
        
        # Basic metrics
        commit_counts = [p.commits for p in periods]
        total_commits = sum(commit_counts)
        peak_commits = max(commit_counts)
        average_commits = total_commits / len(periods)
        
        # Calculate trend
        trend_direction, trend_percentage = self._calculate_trend(commit_counts)
        
        return HistoricalData(
            periods=periods,
            chart_type=chart_type,
            total_commits=total_commits,
            peak_commits=peak_commits,
            average_commits=average_commits,
            trend_direction=trend_direction,
            trend_percentage=trend_percentage,
            date_range_label=date_range_label
        )
    
    def _calculate_trend(self, values: List[int]) -> Tuple[str, float]:
        """Calculate trend direction and percentage change."""
        if len(values) < 2:
            return 'stable', 0.0
        
        # Compare first half to second half for trend
        midpoint = len(values) // 2
        first_half_avg = sum(values[:midpoint]) / midpoint if midpoint > 0 else 0
        second_half_avg = sum(values[midpoint:]) / (len(values) - midpoint)
        
        if first_half_avg == 0:
            if second_half_avg > 0:
                return 'up', 100.0  # Started from zero
            else:
                return 'stable', 0.0
        
        percentage_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if percentage_change > 10:
            return 'up', percentage_change
        elif percentage_change < -10:
            return 'down', abs(percentage_change)
        else:
            return 'stable', abs(percentage_change)
