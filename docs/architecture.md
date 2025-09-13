# BigFoot - Technical Architecture

## System Overview

BigFoot is a Python CLI application that tracks GitHub activity and provides motivational feedback through a terminal interface.

## Architecture

```
bigfoot/
├── main.py              # CLI entry point & command routing
├── config.yaml          # GitHub repos + settings
├── tracker.py           # Core tracking logic & GitHub API
├── database.py          # SQLite operations & schema management
├── rewards.py           # Motivation engine & achievements
├── utils.py             # Common utilities & helpers
├── data/
│   └── bigfoot.db       # SQLite database
└── tests/
    ├── test_tracker.py
    ├── test_database.py
    └── test_rewards.py
```

## Tech Stack

- **Language**: Python 3.8+
- **CLI Framework**: Click
- **Terminal UI**: Rich
- **Database**: SQLite3
- **HTTP Client**: Requests
- **Config**: PyYAML
- **Date Handling**: python-dateutil

## Database Schema

```sql
-- Core tables with proper constraints and indexing
CREATE TABLE commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    date DATE NOT NULL,
    count INTEGER DEFAULT 0,
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo, date)
);

CREATE TABLE streaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date DATE NOT NULL,
    end_date DATE,
    length INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('daily', 'weekly')),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    date DATE NOT NULL,
    triggered_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_commits_date ON commits(date);
CREATE INDEX idx_commits_repo_date ON commits(repo, date);
CREATE INDEX idx_streaks_active ON streaks(is_active);
```

## Configuration Schema

```yaml
# config.yaml - Minimal, sensible defaults
github:
  token: "ghp_xxx"  # Personal access token
  repos:
    - "username/repo1"
    - "username/repo2"
  rate_limit: 5000   # API calls per hour
settings:
  timezone: "UTC"
  daily_goal: 10     # Commits per day (customizable)
  show_progress: true
  color_output: true  # Terminal color support
  compact_mode: false # Detailed vs summary view
```

## Environment Variables

```bash
BIGFOOT_CONFIG_PATH=/path/to/config.yaml
BIGFOOT_DATA_PATH=/path/to/data/
BIGFOOT_LOG_LEVEL=INFO
```

## Dependencies

```python
# requirements.txt
click>=8.0.0          # CLI framework
requests>=2.25.0      # HTTP client
pyyaml>=6.0           # Configuration parsing
rich>=13.0.0          # Terminal formatting & colors
python-dateutil>=2.8.0 # Date handling
sqlite3               # Built-in database
```

## Design Principles

- **Single Responsibility**: Each module has one clear purpose
- **Fail Fast**: Validate inputs early, clear error messages
- **Graceful Degradation**: Works offline, handles API failures
- **Testable**: Pure functions where possible, dependency injection

## Error Handling Strategy

- **API Failures**: Graceful degradation, retry with backoff
- **Network Issues**: Offline mode, queue for later sync
- **Configuration Errors**: Clear messages with fix suggestions
- **Database Issues**: Automatic recovery, backup creation

## Performance Requirements

- **Fast startup**: Commands complete in <2 seconds
- **Low memory**: <50MB RAM usage
- **Minimal disk**: <10MB installation size
- **Offline capable**: Works without internet (cached data)

## Private Repository Support (Phase 2)

### Token Permissions Required
```yaml
# Required GitHub token scopes
github:
  token_scopes:
    - "repo"           # Full access to private repositories
    - "public_repo"    # Access to public repositories
    - "read:user"      # Read user profile information
```

### Repository Validation Flow
1. **Token Validation**: Check token permissions and validity
2. **Repository Access Check**: Verify user can access each repo
3. **Permission Categorization**: Classify repos as public/private/restricted
4. **Graceful Degradation**: Continue with accessible repos only

### Enhanced Configuration Schema
```yaml
# config.yaml - Enhanced for private repos
github:
  token: "ghp_xxx"
  token_scopes: ["repo", "public_repo", "read:user"]
  repos:
    - "username/public-repo"     # ✅ Public repo
    - "username/private-repo"    # ✅ Private repo (if token has 'repo' scope)
    - "org/restricted-repo"      # ❌ Access denied (insufficient permissions)
  rate_limit: 5000
  private_repo_support: true
```

### Error Handling for Private Repos
```bash
$ bigfoot init
🔧 Setting up BigFoot...

🔑 Step 1: GitHub Authentication
? GitHub token: [paste token]
  ✅ Token validated (scopes: repo, public_repo, read:user)

📁 Step 2: Repository Configuration  
? Add repositories: username/private-repo, org/restricted-repo
  🔍 Validating repository access...
  ✅ username/private-repo (private, accessible)
  ❌ org/restricted-repo (access denied - insufficient permissions)
  
  ⚠️  Some repositories are inaccessible
  💡 Quick fixes:
     • For private repos: Regenerate token with 'repo' scope
     • For org repos: Check organization access permissions
  
  ? Continue with accessible repositories? [Y/n] Y
  ✅ Configuration saved! 1 repository added.
```

## Security Considerations

- **Token Security**: Encrypted storage of GitHub tokens
- **Input Validation**: Sanitize all user inputs
- **SQL Injection**: Use parameterized queries
- **Permission Validation**: Verify token scopes before API calls
- **Access Control**: Respect repository visibility and permissions

## Testing Strategy

- **Unit Tests**: 80%+ code coverage for core functionality
- **Integration Tests**: End-to-end workflow testing
- **Mock Testing**: GitHub API mocking for reliable tests

## Implementation Phases

### Phase 1: Core MVP (Week 1-2)
- [ ] **CLI Foundation**: Click-based CLI with track/status commands
- [ ] **Database Layer**: SQLite with proper schema and migrations
- [ ] **GitHub Integration**: API client with rate limiting and error handling
- [ ] **Basic Tracking**: Commit collection and storage
- [ ] **Simple Streaks**: Basic streak calculation logic
- [ ] **Unit Tests**: Core functionality test coverage

### Phase 2: Polish & Private Repos (Week 3)
- [ ] **Rich Terminal Output**: Colors, progress bars, emojis using Rich
- [ ] **Visual Hierarchy**: Consistent spacing, alignment, and typography
- [ ] **Interactive Setup**: Guided onboarding with validation and feedback
- [ ] **Smart Error Messages**: Context-aware error handling with recovery hints
- [ ] **Command Help**: Contextual help with examples and quick reference
- [ ] **Installation**: pip package and setup script
- [ ] **Private Repository Support**: Smart validation and permission management
- [ ] **Repository Access Validation**: Check repo permissions during setup
- [ ] **Enhanced Error Handling**: Clear messages for permission issues

### Phase 3: Motivation Engine (Week 4)
- [ ] **Achievement System**: Milestone detection and rewards
- [ ] **Progress Visualization**: ASCII charts and progress indicators
- [ ] **Smart Notifications**: Context-aware motivational messages
- [ ] **Pace Projections**: Future commit predictions
- [ ] **Integration Tests**: End-to-end workflow testing

### Phase 4: Production Ready (Week 5)
- [ ] **Performance Optimization**: Database queries and API calls
- [ ] **Documentation**: README, user guide, API docs
- [ ] **Packaging**: PyPI distribution and installation
- [ ] **Monitoring**: Basic health checks and diagnostics
