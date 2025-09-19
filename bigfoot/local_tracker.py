"""Local git-based commit tracking for BigFoot."""

import os
import subprocess
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set
from .database import Database


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
