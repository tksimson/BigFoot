# BigFoot - Personal Progress Tracker

A lightweight Python CLI tool that motivates developers to code daily by tracking GitHub activity and providing instant motivational feedback.

## Quick Start

### Option 1: Local Git Tracking (Recommended) ⭐
Track commits across ALL your local repositories - no tokens needed!

```bash
# Ready to use! Run from anywhere in your terminal:
bigfoot local                    # Track today's commits
bigfoot local --date 2025-09-18 # Track specific date
bigfoot local --search-paths "/home/user/projects,/home/user/work"
```

### Option 2: GitHub API Tracking
Track specific GitHub repositories using the API:

```bash
# First-time setup with GitHub token
bigfoot init

# Track daily progress
bigfoot track

# Check status
bigfoot status
```

## Features

- 🎯 **Local Git Tracking**: Scans ALL your local repositories automatically
- 🔥 **Detailed Statistics**: Lines added/deleted, files changed, commit messages  
- 📈 **Multiple Email Support**: Tracks all your git email addresses
- 🚀 **No API Limits**: Works offline, no tokens required for local tracking
- 🏆 **Motivational Feedback**: Progress bars and achievement messages
- 💾 **Local Storage**: SQLite database, no cloud dependencies

## Usage Examples

```bash
# Most common usage - track today's commits
bigfoot local

# Track any specific date
bigfoot local --date 2025-09-15

# Focus on specific directories
bigfoot local --search-paths "/home/user/work,/home/user/personal"

# Check app status and settings
bigfoot doctor

# See all available commands
bigfoot --help
```

## Commands

- `bigfoot local` - **Recommended**: Track commits from local git repositories
- `bigfoot track` - Track via GitHub API (requires setup)
- `bigfoot status` - Show current status and recent progress  
- `bigfoot init` - Configure GitHub API access
- `bigfoot doctor` - Run diagnostics

## Requirements

- Python 3.8+
- Git installed (for local tracking)
- Optional: GitHub Personal Access Token (only for API tracking)

## License

MIT License
