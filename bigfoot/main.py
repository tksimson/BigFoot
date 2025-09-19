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
from .local_tracker import LocalGitTracker
from .rewards import RewardsEngine
from .utils import (
    get_console, format_progress_bar, format_streak_display, 
    format_commit_count, get_motivational_message, show_error_panel,
    show_success_panel, show_info_panel, format_repo_list, create_progress_table
)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """BigFoot - Personal Progress Tracker
    
    A lightweight CLI tool that motivates developers to code daily by tracking 
    local git activity and providing instant motivational feedback.
    """
    pass








@cli.command()
def doctor():
    """Run diagnostics to check BigFoot configuration and database."""
    console = get_console()
    
    console.print("🔧 BigFoot Diagnostics")
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
    
    # Check git availability
    console.print("🔧 Git Check:")
    try:
        import subprocess
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"  ✅ Git available: {result.stdout.strip()}")
        else:
            console.print("  ❌ Git not found or not working")
    except Exception as e:
        console.print(f"  ❌ Git error: {e}")
    
    console.print()
    console.print("✅ BigFoot is ready for local git tracking!")


@cli.command()
@click.option('--date', help='Track commits for specific date (YYYY-MM-DD)')
@click.option('--search-paths', help='Comma-separated paths to search for repositories')
def track(date: str = None, search_paths: str = None):
    """Track commits from local git repositories."""
    console = get_console()
    
    try:
        # Initialize components
        database = Database()
        
        # Parse search paths if provided
        if search_paths:
            paths = [path.strip() for path in search_paths.split(',') if path.strip()]
        else:
            paths = None
        
        local_tracker = LocalGitTracker(database, paths)
        
        # Determine target date
        if date:
            target_date = date
        else:
            from datetime import date as date_module
            target_date = date_module.today().isoformat()
        
        console.print(f"🔍 Scanning local git repositories for {target_date}...")
        console.print()
        
        # Track commits
        results = local_tracker.track_date(target_date)
        
        # Display results
        console.print()
        
        # Progress header
        commits = results['total_commits']
        
        console.print(f"🎯 {format_commit_count(commits)}")
        console.print()
        
        # User emails found
        if results.get('user_emails'):
            console.print(f"👤 Tracking commits from: {', '.join(sorted(results['user_emails']))}")
            console.print()
        
        # Repository breakdown
        if results.get('repositories'):
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Repository", style="cyan")
            table.add_column("Commits", justify="right", style="green")
            table.add_column("Lines Added", justify="right", style="yellow")
            table.add_column("Lines Deleted", justify="right", style="red")
            table.add_column("Files Changed", justify="right", style="blue")
            
            for repo_stat in results['repositories']:
                table.add_row(
                    repo_stat['repo'],
                    str(repo_stat['count']),
                    str(repo_stat['lines_added']),
                    str(repo_stat['lines_deleted']),
                    str(repo_stat['files_changed'])
                )
            
            console.print(table)
            console.print()
        
        # Individual commits
        if results.get('commits'):
            console.print("📝 Recent commits:")
            for commit in results['commits'][-5:]:  # Show last 5 commits
                console.print(f"  • {commit['repo_name']}: {commit['message'][:60]}...")
            console.print()
        
        # Motivational message
        console.print(f"💬 Great job! You made {commits} commits today across {len(results.get('repositories', []))} repositories!")
        
    except Exception as e:
        show_error_panel(f"Local tracking failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
