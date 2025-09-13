"""GitHub API integration and commit tracking for BigFoot."""

import requests
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from .config import Config
from .database import Database


class GitHubTracker:
    """GitHub API client for tracking commits."""
    
    def __init__(self, config: Config, database: Database):
        """Initialize GitHub tracker.
        
        Args:
            config: Configuration instance
            database: Database instance
        """
        self.config = config
        self.database = database
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {config.get_github_token()}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'BigFoot/0.1.0'
        })
        self.base_url = 'https://api.github.com'
        self.rate_limit_remaining = config.get_rate_limit()
        self.rate_limit_reset = 0
    
    def _check_rate_limit(self) -> None:
        """Check and handle GitHub API rate limiting."""
        if self.rate_limit_remaining <= 10:  # Leave some buffer
            if time.time() < self.rate_limit_reset:
                wait_time = self.rate_limit_reset - time.time()
                raise Exception(f"Rate limit exceeded. Wait {wait_time:.0f} seconds before retrying.")
        
        # Update rate limit info
        try:
            response = self.session.get(f"{self.base_url}/rate_limit")
            if response.status_code == 200:
                data = response.json()
                self.rate_limit_remaining = data['rate']['remaining']
                self.rate_limit_reset = data['rate']['reset']
        except Exception:
            pass  # Continue if rate limit check fails
    
    def _make_request(self, url: str, params: Dict = None) -> Dict:
        """Make authenticated request to GitHub API.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            Exception: If request fails or rate limited
        """
        self._check_rate_limit()
        
        try:
            response = self.session.get(url, params=params)
            
            if response.status_code == 401:
                raise Exception("Invalid GitHub token. Please run 'bigfoot init' to reconfigure.")
            elif response.status_code == 403:
                if 'rate limit' in response.text.lower():
                    raise Exception("GitHub API rate limit exceeded. Please wait before retrying.")
                else:
                    raise Exception("GitHub API access forbidden. Check your token permissions.")
            elif response.status_code == 404:
                raise Exception("Repository not found or access denied.")
            elif response.status_code != 200:
                raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {e}")
    
    def get_commits_for_repo(self, repo: str, since: str, until: str = None) -> List[Dict]:
        """Get commits for a repository within a date range.
        
        Args:
            repo: Repository name (owner/repo)
            since: Start date in YYYY-MM-DD format
            until: End date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            List of commit data dictionaries
        """
        if until is None:
            until = date.today().isoformat()
        
        url = f"{self.base_url}/repos/{repo}/commits"
        params = {
            'since': f"{since}T00:00:00Z",
            'until': f"{until}T23:59:59Z",
            'per_page': 100
        }
        
        all_commits = []
        page = 1
        
        while True:
            params['page'] = page
            data = self._make_request(url, params)
            
            if not data:  # No more commits
                break
            
            for commit in data:
                commit_date = commit['commit']['author']['date'][:10]  # YYYY-MM-DD
                all_commits.append({
                    'sha': commit['sha'],
                    'date': commit_date,
                    'message': commit['commit']['message'],
                    'author': commit['commit']['author']['name'],
                    'repo': repo
                })
            
            if len(data) < 100:  # Last page
                break
            
            page += 1
        
        return all_commits
    
    def get_commit_stats_for_repo(self, repo: str, since: str, until: str = None) -> Dict:
        """Get commit statistics for a repository.
        
        Args:
            repo: Repository name (owner/repo)
            since: Start date in YYYY-MM-DD format
            until: End date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Dictionary with commit statistics
        """
        commits = self.get_commits_for_repo(repo, since, until)
        
        # Group commits by date
        commits_by_date = {}
        for commit in commits:
            commit_date = commit['date']
            if commit_date not in commits_by_date:
                commits_by_date[commit_date] = []
            commits_by_date[commit_date].append(commit)
        
        # Calculate statistics
        total_commits = len(commits)
        unique_dates = len(commits_by_date)
        
        # Calculate lines added/deleted (simplified - just count commits)
        lines_added = total_commits * 10  # Rough estimate
        lines_deleted = total_commits * 2  # Rough estimate
        
        return {
            'repo': repo,
            'total_commits': total_commits,
            'unique_dates': unique_dates,
            'lines_added': lines_added,
            'lines_deleted': lines_deleted,
            'commits_by_date': commits_by_date
        }
    
    def track_today(self) -> Dict:
        """Track commits for today across all configured repositories.
        
        Returns:
            Dictionary with today's tracking results
        """
        today = date.today().isoformat()
        repositories = self.config.get_repositories()
        
        if not repositories:
            raise Exception("No repositories configured. Run 'bigfoot init' to add repositories.")
        
        total_commits = 0
        repo_stats = []
        
        for repo in repositories:
            try:
                stats = self.get_commit_stats_for_repo(repo, today, today)
                repo_stats.append(stats)
                total_commits += stats['total_commits']
                
                # Save to database
                self.database.save_commits([{
                    'repo': repo,
                    'date': today,
                    'count': stats['total_commits'],
                    'lines_added': stats['lines_added'],
                    'lines_deleted': stats['lines_deleted']
                }])
                
            except Exception as e:
                print(f"Warning: Could not track {repo}: {e}")
                continue
        
        # Calculate streak
        current_streak = self.database.calculate_streak(today)
        
        return {
            'date': today,
            'total_commits': total_commits,
            'repositories': repo_stats,
            'streak': current_streak,
            'daily_goal': self.config.get_daily_goal()
        }
    
    def track_date_range(self, start_date: str, end_date: str) -> Dict:
        """Track commits for a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with tracking results
        """
        repositories = self.config.get_repositories()
        
        if not repositories:
            raise Exception("No repositories configured. Run 'bigfoot init' to add repositories.")
        
        all_commits = []
        
        for repo in repositories:
            try:
                stats = self.get_commit_stats_for_repo(repo, start_date, end_date)
                
                # Save daily data to database
                for commit_date, commits in stats['commits_by_date'].items():
                    self.database.save_commits([{
                        'repo': repo,
                        'date': commit_date,
                        'count': len(commits),
                        'lines_added': len(commits) * 10,  # Rough estimate
                        'lines_deleted': len(commits) * 2  # Rough estimate
                    }])
                
                all_commits.extend(stats['commits_by_date'])
                
            except Exception as e:
                print(f"Warning: Could not track {repo}: {e}")
                continue
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_commits': sum(len(commits) for commits in all_commits.values()),
            'repositories': repositories
        }
    
    def validate_repository_access(self, repo: str) -> Tuple[bool, str]:
        """Validate access to a repository.
        
        Args:
            repo: Repository name (owner/repo)
            
        Returns:
            Tuple of (is_accessible, error_message)
        """
        try:
            url = f"{self.base_url}/repos/{repo}"
            self._make_request(url)
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def get_user_info(self) -> Dict:
        """Get authenticated user information.
        
        Returns:
            User information dictionary
        """
        try:
            url = f"{self.base_url}/user"
            return self._make_request(url)
        except Exception as e:
            raise Exception(f"Could not get user info: {e}")
    
    def test_connection(self) -> bool:
        """Test GitHub API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.get_user_info()
            return True
        except Exception:
            return False
