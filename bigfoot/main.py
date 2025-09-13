"""Main CLI interface for BigFoot."""

import click
import os
import sys
from datetime import date, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config
from .database import Database
from .tracker import GitHubTracker
from .rewards import RewardsEngine
from .utils import (
    get_console, format_progress_bar, format_streak_display, 
    format_commit_count, get_motivational_message, show_error_panel,
    show_success_panel, show_info_panel, validate_repo_name,
    format_repo_list, create_progress_table
)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """BigFoot - Personal Progress Tracker
    
    A lightweight CLI tool that motivates developers to code daily by tracking 
    GitHub activity and providing instant motivational feedback.
    """
    pass


@cli.command()
@click.option('--token', prompt='GitHub Personal Access Token', 
              help='Your GitHub personal access token')
@click.option('--repos', prompt='Repositories (comma-separated)', 
              help='GitHub repositories to track (format: owner/repo)')
@click.option('--goal', default=10, help='Daily commit goal (default: 10)')
def init(token: str, repos: str, goal: int):
    """Initialize BigFoot with your GitHub token and repositories."""
    console = get_console()
    
    try:
        # Initialize components
        config = Config()
        database = Database()
        tracker = GitHubTracker(config, database)
        
        # Validate token
        console.print("🔑 Validating GitHub token...")
        if not tracker.test_connection():
            show_error_panel("Invalid GitHub token. Please check your token and try again.")
            sys.exit(1)
        
        # Set token
        config.set_github_token(token)
        
        # Parse and validate repositories
        repo_list = [repo.strip() for repo in repos.split(',') if repo.strip()]
        
        if not repo_list:
            show_error_panel("No repositories provided.")
            sys.exit(1)
        
        # Validate each repository
        valid_repos = []
        for repo in repo_list:
            if not validate_repo_name(repo):
                console.print(f"⚠️  Invalid repository format: {repo}")
                continue
            
            is_accessible, error = tracker.validate_repository_access(repo)
            if is_accessible:
                valid_repos.append(repo)
                console.print(f"✅ {repo}")
            else:
                console.print(f"❌ {repo}: {error}")
        
        if not valid_repos:
            show_error_panel("No valid repositories found. Please check your repository names and permissions.")
            sys.exit(1)
        
        # Add repositories to config
        for repo in valid_repos:
            config.add_repository(repo)
        
        # Set daily goal
        config.set_daily_goal(goal)
        
        # Save configuration
        config.save_config()
        
        # Show success
        success_message = f"""
BigFoot initialized successfully!

📊 Configuration:
  • {len(valid_repos)} repositories configured
  • Daily goal: {goal} commits
  • Token: {'*' * 20}{token[-4:] if len(token) > 4 else '****'}

🚀 Next steps:
  • Run 'bigfoot track' to see your progress
  • Run 'bigfoot status' for a quick overview
        """
        
        show_success_panel(success_message)
        
    except Exception as e:
        show_error_panel(f"Initialization failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--date', help='Track commits for specific date (YYYY-MM-DD)')
def track(date: str = None):
    """Track today's commits and show progress."""
    console = get_console()
    
    try:
        # Initialize components
        config = Config()
        database = Database()
        tracker = GitHubTracker(config, database)
        rewards = RewardsEngine(database, config)
        
        # Check if configured
        if not config.is_configured():
            show_error_panel(
                "BigFoot not configured. Run 'bigfoot init' to set up your GitHub token and repositories."
            )
            sys.exit(1)
        
        # Determine target date
        if date:
            target_date = date
        else:
            target_date = date.today().isoformat()
        
        # Track commits
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Tracking commits...", total=None)
            
            if date:
                # Track specific date
                start_date = target_date
                end_date = target_date
                results = tracker.track_date_range(start_date, end_date)
            else:
                # Track today
                results = tracker.track_today()
        
        # Display results
        console.print()
        
        # Progress header
        commits = results['total_commits']
        goal = config.get_daily_goal()
        streak = results.get('streak', 0)
        
        console.print(f"🎯 {format_commit_count(commits)}")
        console.print()
        
        # Progress bar
        if goal > 0:
            progress_bar = format_progress_bar(commits, goal)
            console.print(progress_bar)
            console.print()
        
        # Streak information
        console.print(format_streak_display(streak))
        console.print()
        
        # Repository breakdown
        if 'repositories' in results and results['repositories']:
            table = create_progress_table(results['repositories'])
            console.print(table)
            console.print()
        
        # Motivational message
        message = rewards.get_motivational_message(commits, streak, goal)
        console.print(f"💬 {message}")
        
        # Check for new achievements
        achievements = rewards.check_achievements(commits, streak, target_date)
        if achievements:
            console.print()
            for achievement in achievements:
                console.print(f"🏆 {achievement['message']}")
        
    except Exception as e:
        show_error_panel(f"Tracking failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--days', default=7, help='Number of days to show (default: 7)')
def status(days: int):
    """Show current status and recent progress."""
    console = get_console()
    
    try:
        # Initialize components
        config = Config()
        database = Database()
        rewards = RewardsEngine(database, config)
        
        # Check if configured
        if not config.is_configured():
            show_error_panel(
                "BigFoot not configured. Run 'bigfoot init' to set up your GitHub token and repositories."
            )
            sys.exit(1)
        
        # Get current streak
        current_streak = database.calculate_streak()
        
        # Get recent commits
        recent_commits = database.get_recent_commits(days)
        
        # Calculate totals
        total_commits = sum(commit['count'] for commit in recent_commits)
        unique_days = len(set(commit['date'] for commit in recent_commits))
        
        # Get today's commits
        today = date.today().isoformat()
        today_commits = database.get_total_commits_by_date(today)
        
        # Display status
        console.print("📊 BigFoot Status")
        console.print()
        
        # Current streak
        console.print(format_streak_display(current_streak))
        console.print()
        
        # Today's progress
        goal = config.get_daily_goal()
        console.print(f"📅 Today: {format_commit_count(today_commits)}")
        if goal > 0:
            progress_bar = format_progress_bar(today_commits, goal)
            console.print(progress_bar)
        console.print()
        
        # Recent activity
        console.print(f"📈 Last {days} days: {total_commits} commits across {unique_days} days")
        console.print()
        
        # Repository list
        repos = database.get_repositories()
        console.print(f"📁 Tracking {len(repos)} repositories:")
        for repo in repos:
            console.print(f"  • {repo}")
        console.print()
        
        # Recent achievements
        achievements = rewards.get_recent_achievements(7)
        if achievements:
            console.print("🏆 Recent Achievements:")
            for achievement in achievements[:3]:  # Show last 3
                console.print(f"  • {achievement['message']}")
            console.print()
        
        # Motivational message
        message = rewards.get_motivational_message(today_commits, current_streak, goal)
        console.print(f"💬 {message}")
        
    except Exception as e:
        show_error_panel(f"Status check failed: {e}")
        sys.exit(1)


@cli.command()
def doctor():
    """Run diagnostics to check BigFoot configuration and connectivity."""
    console = get_console()
    
    console.print("🔧 BigFoot Diagnostics")
    console.print()
    
    # Check configuration
    config = Config()
    console.print("📋 Configuration Check:")
    
    if config.get_github_token():
        console.print("  ✅ GitHub token configured")
    else:
        console.print("  ❌ GitHub token not configured")
    
    repos = config.get_repositories()
    if repos:
        console.print(f"  ✅ {len(repos)} repositories configured")
        for repo in repos:
            console.print(f"    • {repo}")
    else:
        console.print("  ❌ No repositories configured")
    
    console.print()
    
    # Check database
    console.print("💾 Database Check:")
    try:
        database = Database()
        console.print("  ✅ Database connection successful")
        
        # Check tables
        import sqlite3
        with sqlite3.connect(database.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
        expected_tables = ['commits', 'streaks', 'rewards']
        for table in expected_tables:
            if table in tables:
                console.print(f"  ✅ Table '{table}' exists")
            else:
                console.print(f"  ❌ Table '{table}' missing")
    
    except Exception as e:
        console.print(f"  ❌ Database error: {e}")
    
    console.print()
    
    # Check GitHub connectivity
    console.print("🌐 GitHub API Check:")
    try:
        tracker = GitHubTracker(config, database)
        if tracker.test_connection():
            console.print("  ✅ GitHub API connection successful")
            
            # Check rate limit
            user_info = tracker.get_user_info()
            console.print(f"  ✅ Authenticated as: {user_info.get('login', 'Unknown')}")
        else:
            console.print("  ❌ GitHub API connection failed")
    except Exception as e:
        console.print(f"  ❌ GitHub API error: {e}")
    
    console.print()
    
    # Overall status
    if config.is_configured():
        console.print("✅ BigFoot is properly configured and ready to use!")
    else:
        console.print("❌ BigFoot needs configuration. Run 'bigfoot init' to set up.")


if __name__ == '__main__':
    cli()
