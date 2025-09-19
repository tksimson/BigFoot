"""Common utilities and helpers for BigFoot."""

import os
import sys
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
from rich.table import Table


def get_console() -> Console:
    """Get Rich console instance with appropriate settings."""
    return Console(
        color_system="auto" if os.getenv("TERM") != "dumb" else None,
        force_terminal=True if os.getenv("CI") else None
    )


def format_progress_bar(current: int, goal: int, width: int = 30) -> str:
    """Create ASCII progress bar.
    
    Args:
        current: Current progress value
        goal: Goal value
        width: Width of progress bar
        
    Returns:
        Formatted progress bar string
    """
    if goal == 0:
        return "░" * width
    
    filled = int((current / goal) * width)
    empty = width - filled
    
    bar = "█" * filled + "░" * empty
    percentage = int((current / goal) * 100)
    
    return f"┌{'─' * width}┐\n│{bar}│ {percentage}% ({current}/{goal})\n└{'─' * width}┘"


def format_streak_display(streak: int) -> str:
    """Format streak display with appropriate emoji.
    
    Args:
        streak: Current streak length
        
    Returns:
        Formatted streak string
    """
    if streak == 0:
        return "❄️  No active streak"
    elif streak < 3:
        return f"🔥 Current Streak: {streak} days"
    elif streak < 7:
        return f"🔥 Current Streak: {streak} days"
    elif streak < 30:
        return f"🔥 Current Streak: {streak} days"
    else:
        return f"🔥 Current Streak: {streak} days"


def format_commit_count(commits: int) -> str:
    """Format commit count with appropriate emoji.
    
    Args:
        commits: Number of commits
        
    Returns:
        Formatted commit count string
    """
    if commits == 0:
        return "😴 No commits today"
    elif commits < 3:
        return f"📝 {commits} commits today"
    elif commits < 10:
        return f"💪 {commits} commits today"
    else:
        return f"🚀 {commits} commits today"


def get_week_dates(target_date: str = None) -> List[str]:
    """Get list of dates for the week containing target_date.
    
    Args:
        target_date: Target date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        List of dates in YYYY-MM-DD format
    """
    if target_date is None:
        target_date = date.today().isoformat()
    
    target = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    # Get Monday of the week
    monday = target - timedelta(days=target.weekday())
    
    # Generate all 7 days
    week_dates = []
    for i in range(7):
        week_date = monday + timedelta(days=i)
        week_dates.append(week_date.isoformat())
    
    return week_dates


def get_recent_dates(days: int) -> List[str]:
    """Get list of recent dates.
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of dates in YYYY-MM-DD format
    """
    today = date.today()
    dates = []
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        dates.append(target_date.isoformat())
    
    return dates


def generate_date_range(days: int, reverse: bool = True) -> List[str]:
    """Generate date range for backfilling.
    
    Args:
        days: Number of days to go back from today
        reverse: If True, return oldest dates first (recommended for backfill)
        
    Returns:
        List of dates in YYYY-MM-DD format
    """
    today = date.today()
    dates = []
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        dates.append(target_date.isoformat())
    
    if reverse:
        dates.reverse()  # Oldest first for logical backfill order
    
    return dates


def validate_backfill_days(days: int) -> tuple[bool, str]:
    """Validate backfill date range parameters.
    
    Args:
        days: Number of days to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if days < 1:
        return False, "Days must be positive"
    if days > 365:
        return False, "Maximum 365 days supported (use multiple runs for more)"
    return True, ""


def format_date_range(start_date: str, end_date: str, days: int) -> str:
    """Format date range for display.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format  
        days: Number of days in range
        
    Returns:
        Formatted date range string
    """
    return f"{start_date} to {end_date} ({days} days)"


def validate_repo_name(repo: str) -> bool:
    """Validate repository name format.
    
    Args:
        repo: Repository name to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not repo or '/' not in repo:
        return False
    
    parts = repo.split('/')
    if len(parts) != 2:
        return False
    
    owner, repo_name = parts
    if not owner or not repo_name:
        return False
    
    # Basic validation - no spaces, special chars
    if ' ' in repo or any(char in repo for char in ['<', '>', ':', '"', '|', '?', '*']):
        return False
    
    return True


def format_repo_list(repos: List[str]) -> str:
    """Format list of repositories for display.
    
    Args:
        repos: List of repository names
        
    Returns:
        Formatted string
    """
    if not repos:
        return "No repositories configured"
    
    if len(repos) == 1:
        return f"1 repository: {repos[0]}"
    
    return f"{len(repos)} repositories:\n" + "\n".join(f"  • {repo}" for repo in repos)


def get_motivational_message(commits: int, goal: int, streak: int) -> str:
    """Get motivational message based on progress.
    
    Args:
        commits: Current commit count
        goal: Daily goal
        streak: Current streak
        
    Returns:
        Motivational message
    """
    if commits == 0:
        return "💡 Every journey starts with a single commit!"
    elif commits < goal * 0.5:
        return "🌱 Great start! Keep building momentum!"
    elif commits < goal:
        return "⚡ You're making progress! Keep it up!"
    elif commits == goal:
        return "🎯 Goal achieved! You're on fire!"
    elif commits < goal * 1.5:
        return "🚀 Exceeding expectations! Amazing work!"
    else:
        return "🏆 Outstanding! You're crushing it!"
    
    if streak >= 7:
        return f"🔥 {streak} day streak! You're unstoppable!"
    elif streak >= 3:
        return f"💪 {streak} day streak! Building great habits!"


def create_progress_table(commits_data: List[Dict]) -> Table:
    """Create Rich table for progress display.
    
    Args:
        commits_data: List of commit data dictionaries
        
    Returns:
        Rich Table instance
    """
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Repository", style="cyan")
    table.add_column("Commits", justify="right", style="green")
    table.add_column("Lines Added", justify="right", style="yellow")
    table.add_column("Lines Deleted", justify="right", style="red")
    
    for data in commits_data:
        table.add_row(
            data['repo'],
            str(data['count']),
            str(data['lines_added']),
            str(data['lines_deleted'])
        )
    
    return table


def show_error_panel(message: str, console: Console = None) -> None:
    """Show error message in a Rich panel.
    
    Args:
        message: Error message
        console: Rich console instance
    """
    if console is None:
        console = get_console()
    
    error_text = Text(message, style="red")
    panel = Panel(
        error_text,
        title="❌ Error",
        border_style="red",
        padding=(1, 2)
    )
    console.print(panel)


def show_success_panel(message: str, console: Console = None) -> None:
    """Show success message in a Rich panel.
    
    Args:
        message: Success message
        console: Rich console instance
    """
    if console is None:
        console = get_console()
    
    success_text = Text(message, style="green")
    panel = Panel(
        success_text,
        title="✅ Success",
        border_style="green",
        padding=(1, 2)
    )
    console.print(panel)


def show_info_panel(message: str, console: Console = None) -> None:
    """Show info message in a Rich panel.
    
    Args:
        message: Info message
        console: Rich console instance
    """
    if console is None:
        console = get_console()
    
    info_text = Text(message, style="blue")
    panel = Panel(
        info_text,
        title="ℹ️  Info",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(panel)
