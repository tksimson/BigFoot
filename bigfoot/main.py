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
from .dashboard import DashboardAnalytics
from .dashboard_visuals import DashboardRenderer
from .utils import (
    get_console, format_progress_bar, format_streak_display, 
    format_commit_count, get_motivational_message, show_error_panel,
    show_success_panel, show_info_panel, format_repo_list, create_progress_table,
    validate_backfill_days, format_date_range
)


def _run_dashboard(days: int = 210, goals: str = None):
    """Execute the dashboard functionality with provided options."""
    console = get_console()
    
    try:
        # Initialize components
        database = Database()
        analytics = DashboardAnalytics(database)
        renderer = DashboardRenderer(console)
        
        # Parse custom goals if provided
        daily_goal, weekly_goal, monthly_goal = 5, 28, 82  # defaults (moderate)
        if goals:
            try:
                # Check for presets first
                goals_lower = goals.lower().strip()
                if goals_lower == 'easy':
                    daily_goal, weekly_goal, monthly_goal = 5, 20, 60
                elif goals_lower == 'moderate':
                    daily_goal, weekly_goal, monthly_goal = 5, 28, 82
                elif goals_lower == 'challenging':
                    daily_goal, weekly_goal, monthly_goal = 10, 56, 180
                else:
                    # Parse as comma-separated numbers
                    goal_parts = [int(g.strip()) for g in goals.split(',')]
                    if len(goal_parts) >= 1:
                        daily_goal = goal_parts[0]
                    if len(goal_parts) >= 2:
                        weekly_goal = goal_parts[1] 
                    if len(goal_parts) >= 3:
                        monthly_goal = goal_parts[2]
            except (ValueError, IndexError):
                show_error_panel("Invalid goals format. Use: 'easy'/'moderate'/'challenging' or 'daily,weekly,monthly' (e.g. '5,28,82')")
                sys.exit(1)
        
        # Get analytics data
        streak_data = analytics.get_streak_data()
        momentum = analytics.calculate_momentum()
        goal_progress = analytics.get_goal_progress(daily_goal, weekly_goal, monthly_goal)
        hall_of_fame = analytics.get_hall_of_fame()
        heatmap_data = analytics.generate_heatmap_data(days)  # Use user-specified days for heatmap
        
        # Check if there's any data to display
        total_commits = sum(heatmap_data.values()) if heatmap_data else 0
        if total_commits == 0:
            # First time user experience
            console.print()
            console.print("🌟 [bright_yellow bold]Welcome to BigFoot![/bright_yellow bold] 🌟")
            console.print()
            console.print("It looks like you haven't tracked any commits yet. Let's get you started!")
            console.print()
            console.print("📋 [bright_cyan]Quick Start:[/bright_cyan]")
            console.print("  1. Track today's commits:    [bright_green]bigfoot track[/bright_green]")
            console.print("  2. Backfill recent history:  [bright_green]bigfoot backfill --days 7[/bright_green]")
            console.print("  3. See your progress:        [bright_green]bigfoot[/bright_green] (this dashboard)")
            console.print()
            console.print("🚀 Your coding journey starts with the first commit you track!")
            console.print("   Run [bright_green bold]bigfoot track[/bright_green bold] to begin building your streak!")
            console.print()
            return
        
        # Render dashboard sections (compact style with thick borders)
        console.print()
        
        # 1. Streak Header (always visible)
        streak_panel = renderer.render_streak_header(streak_data)
        console.print(streak_panel)
        
        # 2. Hall of Fame (if user has significant history and is making progress toward records)
        # Only show when within 50% of record to avoid discouragement
        today_commits = analytics.database.get_total_commits_by_date(date.today().isoformat())
        show_hall_of_fame = (
            total_commits > 10 and  # Has some history
            hall_of_fame.best_single_day_commits.value > 0 and  # Has records
            (today_commits >= hall_of_fame.best_single_day_commits.value * 0.5 or  # Within 50% of commit record
             today_commits >= 3)  # Or has made reasonable progress today
        )
        if show_hall_of_fame:
            hall_of_fame_panel = renderer.render_hall_of_fame(hall_of_fame)
            console.print(hall_of_fame_panel)
        
        # 3. Goals Progress
        goals_panel = renderer.render_goals_progress(goal_progress, today_commits)  
        console.print(goals_panel)
        
        # 4. Activity Heatmap (show heatmap for users with some history)
        if total_commits > 5:  # Show for any user with minimal activity
            heatmap_panel = renderer.render_heatmap(heatmap_data, days=days)  # Use user-specified days
            console.print(heatmap_panel)
        
        # 5. Motivational Message (always show)
        motivational_panel = renderer.render_motivational_message(
            momentum.performance_level, streak_data, momentum
        )
        console.print(motivational_panel)
        
        # Quick actions hint
        console.print()
        console.print("⚡ [dim]Quick Actions:[/dim] [bright_green]bigfoot track[/bright_green] • [bright_cyan]bigfoot backfill --days 7[/bright_cyan] • [bright_yellow]bigfoot doctor[/bright_yellow]")
        console.print()
        
    except Exception as e:
        show_error_panel(f"Dashboard error: {str(e)}")
        sys.exit(1)


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0")
@click.option('--days', default=210, type=int, help='🗓️  Days to include in activity heatmap (default: 210)')
@click.option('--goals', help='🎯 Goals: "easy"/"moderate"/"challenging" or "daily,weekly,monthly" (e.g. "5,28,82")')
@click.pass_context
def cli(ctx, days: int = 210, goals: str = None):
    """🔥 BigFoot - Personal Progress Tracker
    
    A lightweight CLI tool that motivates developers to code daily by tracking 
    local git activity and providing revolutionary 210-day historical insights.
    
    🚀 FEATURES:
    • 🔥 Dynamic streak tracking with fire animations
    • 🏆 Hall of Fame with personal records tracking
    • 🎯 Smart goal monitoring with visual progress bars
    • 📈 Activity heatmaps (30-365+ days)
    • 💬 AI-powered motivational messaging with 177k+ variations
    
    📋 COMMAND EXAMPLES:
    
    \b
    bigfoot                              # Default dashboard (210-day heatmap)
    bigfoot --days 30                    # 30-day heatmap
    bigfoot --days 365                   # Full year view
    bigfoot --goals easy                 # Easy goals (5,20,60)
    bigfoot --goals challenging          # Challenging goals (10,56,180)
    bigfoot --goals "10,56,180"          # Custom numeric goals
    \b
    
    \b
    bigfoot track                        # Track today's commits
    bigfoot track --date 2024-01-15     # Track specific date
    bigfoot track --search-paths "~/work"  # Custom repo paths
    \b
    
    \b
    bigfoot backfill --days 7            # Backfill 7 days
    bigfoot backfill --days 30 --dry-run # Preview mode
    bigfoot backfill --days 90 --force   # Force overwrite
    \b
    
    \b
    bigfoot doctor                       # System diagnostics
    \b
    
    ⚡ QUICK START:
    Just run 'bigfoot' to see your motivational dashboard with historical trends!
    """
    if ctx.invoked_subcommand is None:
        # Show dashboard when no command is provided
        _run_dashboard(days, goals)








@cli.command()
def doctor():
    """🔧 Run comprehensive system diagnostics and health checks
    
    Performs thorough diagnostics of BigFoot's configuration, database integrity,
    git availability, and repository scanning capabilities. Perfect for troubleshooting
    or verifying your setup is ready for optimal progress tracking.
    """
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
@click.option('--date', help='📅 Track commits for specific date (YYYY-MM-DD format)')
@click.option('--search-paths', help='🔍 Custom paths to scan: comma-separated directories')
def track(date: str = None, search_paths: str = None):
    """📊 Track today's commits and build your coding streak
    
    Scans local git repositories for commits, automatically detects your coding
    activity, and updates your progress database. This is your daily ritual for
    building momentum and maintaining streak consistency.
    
    🎯 FEATURES:
    • Automatic git repository discovery across your system
    • Multi-repository commit aggregation with deduplication  
    • Real-time statistics (commits, lines added/deleted, files changed)
    • Streak calculation and progress tracking
    • Beautiful terminal output with progress visualization
    
    🔥 EXAMPLES:
      bigfoot track                    # Track commits for today
      bigfoot track --date 2024-01-15 # Track specific date
      bigfoot track --search-paths "~/projects,~/work"  # Custom paths
    """
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
        repos_with_commits = len(results.get('repositories', []))
        console.print(f"💬 Great job! You made {commits} commits today across {repos_with_commits} repositories!")
        
    except Exception as e:
        show_error_panel(f"Local tracking failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--days', required=True, type=int, help='⏰ Days to backfill (required): how far back to scan')
@click.option('--search-paths', help='🔍 Custom repository paths: comma-separated directories')
@click.option('--dry-run', is_flag=True, help='🔬 Preview mode: show what would be processed (no database changes)')
@click.option('--force', is_flag=True, help='⚡ Force mode: overwrite existing data (default: skip duplicates)')
@click.option('--batch-size', default=10, type=int, help='📦 Batch processing: repositories per batch (default: 10)')
@click.option('--quiet', is_flag=True, help='🤫 Silent mode: suppress progress output')
def backfill(days: int, search_paths: str = None, dry_run: bool = False, 
            force: bool = False, batch_size: int = 10, quiet: bool = False):
    """🔄 Backfill historical git commits for comprehensive progress analysis
    
    Retroactively processes git commit history to populate your BigFoot database
    with historical data. Perfect for new users who want to see their complete
    coding journey or fill gaps in their tracking history.
    
    🎯 FEATURES:
    • Intelligent date range processing from present backwards
    • Smart duplicate detection and prevention (unless --force used)
    • Batch processing for optimal performance with large repositories
    • Progress bars and detailed reporting throughout the process
    • Dry-run mode for safe preview before committing changes
    • Comprehensive error handling and recovery
    
    🔥 EXAMPLES:
      bigfoot backfill --days 7           # Backfill last 7 days
      bigfoot backfill --days 30 --dry-run    # Preview 30-day backfill
      bigfoot backfill --days 90 --force      # Force overwrite 90 days
      bigfoot backfill --days 14 --search-paths "~/work"  # Custom paths
      
    ⚠️  IMPORTANT:
    This command processes historical data chronologically and may take time
    for large date ranges. Use --dry-run first to estimate processing scope.
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
