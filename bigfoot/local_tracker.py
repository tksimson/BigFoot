"""Local git-based commit tracking for BigFoot."""

import os
import subprocess
import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console
from .database import Database
from .utils import generate_date_range, format_date_range


class LocalGitTracker:
    """Local git repository tracker that scans filesystem for git repos."""
    
    def __init__(self, database: Database, search_paths: List[str] = None):
        """Initialize local git tracker.
        
        Args:
            database: Database instance
            search_paths: Paths to search for git repositories (defaults to common paths)
        """
        self.database = database
        if search_paths is None:
            # Default search paths - user can customize these
            home = Path.home()
            self.search_paths = [
                str(home / "dev"),
                str(home / "projects"),
                str(home / "code"),
                str(home / "workspace"),
                str(home / "Documents"),
                str(home / "Desktop"),
                str(home)  # Home directory itself
            ]
        else:
            self.search_paths = search_paths
    
    def find_git_repositories(self) -> List[str]:
        """Find all git repositories in search paths.
        
        Returns:
            List of paths to git repositories
        """
        git_repos = []
        
        for search_path in self.search_paths:
            if not os.path.exists(search_path):
                continue
                
            try:
                # Use git to find all repositories
                result = subprocess.run([
                    'find', search_path, '-type', 'd', '-name', '.git'
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    for git_dir in result.stdout.strip().split('\n'):
                        if git_dir:  # Skip empty lines
                            repo_path = os.path.dirname(git_dir)
                            git_repos.append(repo_path)
                            
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                continue
        
        return git_repos
    
    def get_git_user_emails(self, repo_path: str) -> Set[str]:
        """Get all email addresses used by the current user in a repository.
        
        Args:
            repo_path: Path to git repository
            
        Returns:
            Set of email addresses
        """
        emails = set()
        
        try:
            # Get global git user email
            result = subprocess.run([
                'git', 'config', '--global', 'user.email'
            ], capture_output=True, text=True, cwd=repo_path)
            
            if result.returncode == 0 and result.stdout.strip():
                emails.add(result.stdout.strip())
            
            # Get local repo user email
            result = subprocess.run([
                'git', 'config', 'user.email'
            ], capture_output=True, text=True, cwd=repo_path)
            
            if result.returncode == 0 and result.stdout.strip():
                emails.add(result.stdout.strip())
            
            # Get all author emails from recent commits (last 100)
            result = subprocess.run([
                'git', 'log', '--format=%ae', '-n', '100'
            ], capture_output=True, text=True, cwd=repo_path)
            
            if result.returncode == 0:
                for email in result.stdout.strip().split('\n'):
                    if email and '@' in email:
                        emails.add(email.strip())
                        
        except subprocess.SubprocessError:
            pass
            
        return emails
    
    def get_commits_for_date(self, repo_path: str, target_date: str, user_emails: Set[str] = None) -> List[Dict]:
        """Get commits for a specific date in a repository.
        
        Args:
            repo_path: Path to git repository
            target_date: Date in YYYY-MM-DD format
            user_emails: Set of user email addresses to filter by
            
        Returns:
            List of commit dictionaries
        """
        commits = []
        
        try:
            # Git log for specific date
            git_cmd = [
                'git', 'log',
                f'--since={target_date} 00:00:00',
                f'--until={target_date} 23:59:59',
                '--format=%H|%ae|%an|%s|%ad',
                '--date=iso'
            ]
            
            result = subprocess.run(git_cmd, capture_output=True, text=True, cwd=repo_path)
            
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if '|' in line:
                        parts = line.split('|', 4)
                        if len(parts) == 5:
                            sha, author_email, author_name, message, commit_date = parts
                            
                            # Filter by user emails if provided
                            if user_emails and author_email not in user_emails:
                                continue
                            
                            commits.append({
                                'sha': sha,
                                'author_email': author_email,
                                'author_name': author_name,
                                'message': message.strip(),
                                'date': target_date,
                                'repo_path': repo_path,
                                'repo_name': os.path.basename(repo_path)
                            })
                            
        except subprocess.SubprocessError:
            pass
            
        return commits
    
    def get_commit_stats(self, repo_path: str, sha: str) -> Dict:
        """Get detailed statistics for a specific commit.
        
        Args:
            repo_path: Path to git repository
            sha: Commit SHA
            
        Returns:
            Dictionary with commit statistics
        """
        try:
            result = subprocess.run([
                'git', 'show', '--numstat', '--format=', sha
            ], capture_output=True, text=True, cwd=repo_path)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                total_added = 0
                total_deleted = 0
                files_changed = 0
                
                for line in lines:
                    if line and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            added = parts[0]
                            deleted = parts[1]
                            
                            # Handle binary files (marked with -)
                            if added.isdigit():
                                total_added += int(added)
                            if deleted.isdigit():
                                total_deleted += int(deleted)
                            files_changed += 1
                
                return {
                    'lines_added': total_added,
                    'lines_deleted': total_deleted,
                    'files_changed': files_changed
                }
                
        except subprocess.SubprocessError:
            pass
            
        return {'lines_added': 0, 'lines_deleted': 0, 'files_changed': 0}
    
    def track_date(self, target_date: str) -> Dict:
        """Track commits for a specific date across all found repositories.
        
        Args:
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary with tracking results
        """
        print(f"🔍 Scanning for git repositories...")
        repos = self.find_git_repositories()
        
        if not repos:
            return {
                'date': target_date,
                'total_commits': 0,
                'repositories': [],
                'user_emails': set()
            }
        
        print(f"📁 Found {len(repos)} git repositories")
        
        all_commits = []
        repo_stats = []
        all_user_emails = set()
        
        for repo_path in repos:
            try:
                # Get user emails for this repo
                user_emails = self.get_git_user_emails(repo_path)
                all_user_emails.update(user_emails)
                
                # Get commits for the date
                commits = self.get_commits_for_date(repo_path, target_date, user_emails)
                
                if commits:
                    total_lines_added = 0
                    total_lines_deleted = 0
                    total_files_changed = 0
                    
                    # Get detailed stats for each commit
                    for commit in commits:
                        stats = self.get_commit_stats(repo_path, commit['sha'])
                        total_lines_added += stats['lines_added']
                        total_lines_deleted += stats['lines_deleted']
                        total_files_changed += stats['files_changed']
                    
                    repo_stat = {
                        'repo': os.path.basename(repo_path),
                        'repo_path': repo_path,
                        'count': len(commits),
                        'lines_added': total_lines_added,
                        'lines_deleted': total_lines_deleted,
                        'files_changed': total_files_changed
                    }
                    
                    repo_stats.append(repo_stat)
                    all_commits.extend(commits)
                    
                    # Save to database
                    self.database.save_commits([{
                        'repo': repo_stat['repo'],
                        'date': target_date,
                        'count': repo_stat['count'],
                        'lines_added': repo_stat['lines_added'],
                        'lines_deleted': repo_stat['lines_deleted']
                    }])
                    
            except Exception as e:
                print(f"⚠️  Warning: Could not process {repo_path}: {e}")
                continue
        
        # Deduplicate and aggregate repositories with the same name
        aggregated_repos = {}
        for stat in repo_stats:
            repo_name = stat['repo']
            if repo_name in aggregated_repos:
                # Aggregate statistics for duplicate repository names
                aggregated_repos[repo_name]['count'] += stat['count']
                aggregated_repos[repo_name]['lines_added'] += stat['lines_added']
                aggregated_repos[repo_name]['lines_deleted'] += stat['lines_deleted']
                aggregated_repos[repo_name]['files_changed'] += stat['files_changed']
            else:
                # First occurrence of this repository name
                aggregated_repos[repo_name] = {
                    'repo': repo_name,
                    'count': stat['count'],
                    'lines_added': stat['lines_added'],
                    'lines_deleted': stat['lines_deleted'],
                    'files_changed': stat['files_changed']
                }
        
        # Convert back to list format
        deduplicated_repo_stats = list(aggregated_repos.values())
        
        return {
            'date': target_date,
            'total_commits': len(all_commits),
            'repositories': deduplicated_repo_stats,
            'user_emails': all_user_emails,
            'commits': all_commits
        }
    
    def backfill_history(self, days: int, search_paths: List[str] = None, 
                        dry_run: bool = False, force: bool = False,
                        batch_size: int = 10, quiet: bool = False) -> Dict:
        """Backfill historical git commit data.
        
        Args:
            days: Number of days to go back from today
            search_paths: Custom repository search paths
            dry_run: Preview mode without database writes
            force: Overwrite existing data
            batch_size: Number of repos to process simultaneously  
            quiet: Suppress progress output
            
        Returns:
            Dictionary with backfill results and statistics
        """
        start_time = time.time()
        console = Console() if not quiet else None
        
        # Generate date range (oldest first)
        date_range = generate_date_range(days, reverse=True)
        start_date = date_range[0] if date_range else None
        end_date = date_range[-1] if date_range else None
        
        if not quiet and console:
            console.print("📊 Configuration:")
            console.print(f"  • Date range: {format_date_range(start_date, end_date, days)}")
            console.print(f"  • Mode: {'Dry Run' if dry_run else 'Normal'}")
            if force:
                console.print("  • Force mode: Overwriting existing data")
            console.print()
        
        # Find repositories
        if not quiet and console:
            console.print("🔍 Discovering git repositories...")
        
        repos = self.find_git_repositories()
        
        if not repos:
            return {
                'processed_days': len(date_range),
                'processed_repos': 0,
                'total_commits': 0,
                'database_entries': 0,
                'duration_seconds': time.time() - start_time,
                'errors': ['No git repositories found'],
                'warnings': []
            }
        
        if not quiet and console:
            console.print(f"  • Repositories: {len(repos)} found")
            console.print()
        
        # Initialize statistics
        total_commits_found = 0
        total_database_entries = 0
        processed_repos = 0
        errors = []
        warnings = []
        
        # Setup progress tracking
        if not quiet and console:
            console.print("🔍 Processing historical commits...")
            console.print()
        
        # Process each date in the range
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console if not quiet else None,
            disable=quiet
        ) as progress:
            
            # Create progress tasks
            date_task = progress.add_task("Processing dates", total=len(date_range))
            repo_task = progress.add_task("Processing repositories", total=len(repos))
            
            for current_date in date_range:
                progress.update(date_task, description=f"Day: {current_date}")
                
                # Reset repo progress for each date
                progress.update(repo_task, completed=0, description="Scanning repositories")
                
                date_commits = 0
                date_entries = 0
                
                # Process repositories in batches
                for i in range(0, len(repos), batch_size):
                    batch_repos = repos[i:i + batch_size]
                    
                    for repo_path in batch_repos:
                        try:
                            # Check if we should skip this repo/date combination
                            repo_name = os.path.basename(repo_path)
                            
                            if not force and not dry_run:
                                # Check if data already exists
                                existing = self._check_existing_data(repo_name, current_date)
                                if existing:
                                    progress.update(repo_task, advance=1)
                                    continue
                            
                            # Get user emails for this repo
                            user_emails = self.get_git_user_emails(repo_path)
                            
                            # Get commits for the date
                            commits = self.get_commits_for_date(repo_path, current_date, user_emails)
                            
                            if commits:
                                # Calculate statistics
                                total_lines_added = 0
                                total_lines_deleted = 0
                                total_files_changed = 0
                                
                                for commit in commits:
                                    stats = self.get_commit_stats(repo_path, commit['sha'])
                                    total_lines_added += stats['lines_added']
                                    total_lines_deleted += stats['lines_deleted']
                                    total_files_changed += stats['files_changed']
                                
                                commit_data = {
                                    'repo': repo_name,
                                    'date': current_date,
                                    'count': len(commits),
                                    'lines_added': total_lines_added,
                                    'lines_deleted': total_lines_deleted
                                }
                                
                                # Save to database (unless dry run)
                                if not dry_run:
                                    if force:
                                        # Force mode: delete existing and insert new
                                        self.database.delete_commit_data(repo_name, current_date)
                                    
                                    self.database.save_commits([commit_data])
                                    date_entries += 1
                                else:
                                    # Dry run: just count what would be saved
                                    date_entries += 1
                                
                                date_commits += len(commits)
                                processed_repos = len(set([r for r in repos if os.path.exists(r)]))
                            
                        except subprocess.SubprocessError as e:
                            error_msg = f"Repository {repo_path}: Git error - {str(e)[:100]}"
                            errors.append(error_msg)
                        except Exception as e:
                            error_msg = f"Repository {repo_path}: {str(e)[:100]}"
                            errors.append(error_msg)
                        
                        progress.update(repo_task, advance=1)
                
                total_commits_found += date_commits
                total_database_entries += date_entries
                
                # Update date progress
                progress.advance(date_task)
        
        # Calculate final statistics
        duration = time.time() - start_time
        
        return {
            'processed_days': len(date_range),
            'processed_repos': processed_repos,
            'total_commits': total_commits_found,
            'database_entries': total_database_entries,
            'duration_seconds': duration,
            'errors': errors,
            'warnings': warnings,
            'date_range': {
                'start': start_date,
                'end': end_date,
                'days': days
            }
        }
    
    def _check_existing_data(self, repo_name: str, date: str) -> bool:
        """Check if data already exists for repo/date combination.
        
        Args:
            repo_name: Repository name
            date: Date in YYYY-MM-DD format
            
        Returns:
            True if data exists, False otherwise
        """
        try:
            import sqlite3
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM commits WHERE repo = ? AND date = ?",
                    (repo_name, date)
                )
                count = cursor.fetchone()[0]
                return count > 0
        except Exception:
            return False
    
    def track_today(self) -> Dict:
        """Track commits for today.
        
        Returns:
            Dictionary with today's tracking results
        """
        today = date.today().isoformat()
        return self.track_date(today)
    
    def track_date_range(self, start_date: str, end_date: str) -> Dict:
        """Track commits for a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with tracking results
        """
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        all_results = []
        total_commits = 0
        
        current = start
        while current <= end:
            date_str = current.isoformat()
            result = self.track_date(date_str)
            all_results.append(result)
            total_commits += result['total_commits']
            current += timedelta(days=1)
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_commits': total_commits,
            'daily_results': all_results
        }
