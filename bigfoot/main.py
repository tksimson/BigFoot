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
    show_success_panel, show_info_panel, format_repo_list, create_progress_table,
    validate_backfill_days, format_date_range
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


@cli.command()
@click.option('--days', required=True, type=int, help='Number of days to go back (required)')
@click.option('--search-paths', help='Comma-separated paths to search for repositories')
@click.option('--dry-run', is_flag=True, help='Show what would be processed without saving to database')
@click.option('--force', is_flag=True, help='Force overwrite existing data (default: skip duplicates)')
@click.option('--batch-size', default=10, type=int, help='Process repositories in batches (default: 10)')
@click.option('--quiet', is_flag=True, help='Suppress progress output')
def backfill(days: int, search_paths: str = None, dry_run: bool = False, 
            force: bool = False, batch_size: int = 10, quiet: bool = False):
    """Backfill historical git commits into the database.
    
    This command scans your git repositories for historical commits and adds them
    to BigFoot's database, enabling complete progress tracking and streak calculation.
    
    Examples:
      bigfoot backfill --days 30
      bigfoot backfill --days 7 --dry-run
      bigfoot backfill --days 60 --search-paths "/home/user/work,/home/user/personal"
    """
    console = get_console()
    
    try:
        # Validate input parameters
        valid, error_msg = validate_backfill_days(days)
        if not valid:
            show_error_panel(f"Invalid days parameter: {error_msg}")
            sys.exit(1)
        
        if not quiet:
            console.print("🔄 BigFoot Historical Backfill")
            console.print()
        
        # Initialize components
        database = Database()
        
        # Parse search paths if provided
        if search_paths:
            paths = [path.strip() for path in search_paths.split(',') if path.strip()]
        else:
            paths = None
        
        local_tracker = LocalGitTracker(database, paths)
        
        # Execute backfill
        results = local_tracker.backfill_history(
            days=days,
            search_paths=paths,
            dry_run=dry_run,
            force=force,
            batch_size=batch_size,
            quiet=quiet
        )
        
        if not quiet:
            # Display results summary
            console.print()
            console.print("📈 Backfill Results:")
            console.print(f"  • {results['processed_days']} days processed")
            console.print(f"  • {results['processed_repos']} repositories found")
            console.print(f"  • {results['total_commits']} commits discovered")
            console.print(f"  • {results['database_entries']} database entries {'created' if not dry_run else 'would be created'}")
            console.print(f"  • {results['duration_seconds']:.1f} seconds elapsed")
            
            if results.get('errors'):
                console.print()
                console.print(f"⚠️  {len(results['errors'])} warnings:")
                for error in results['errors']:
                    console.print(f"  • {error}")
            
            console.print()
            if dry_run:
                console.print("🔍 This was a dry run - no data was saved.")
                console.print("⚡ Run without --dry-run to execute backfill")
            else:
                show_success_panel("Backfill completed successfully!")
        
    except Exception as e:
        show_error_panel(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
