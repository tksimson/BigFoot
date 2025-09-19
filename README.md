# BigFoot - Personal Progress Tracker

A lightweight Python CLI tool that motivates developers to code daily by tracking local git activity and providing instant motivational feedback.

## Quick Start

Track commits across ALL your local repositories - no tokens or setup needed!

```bash
# Ready to use! Run from anywhere in your terminal:
bigfoot track                    # Track today's commits
bigfoot track --date 2025-09-18 # Track specific date
bigfoot track --search-paths "/home/user/projects,/home/user/work"
```

## Features

- 🎯 **Local Git Tracking**: Scans ALL your local repositories automatically
- 🔥 **Detailed Statistics**: Lines added/deleted, files changed, commit messages  
- 📈 **Multiple Email Support**: Tracks all your git email addresses
- 🚀 **No API Limits**: Works offline, no tokens or configuration required
- 🏆 **Motivational Feedback**: Progress bars and achievement messages
- 💾 **Local Storage**: SQLite database, no cloud dependencies
- ⚡ **Zero Setup**: Just install and run - works immediately

## Usage Examples

```bash
# Most common usage - track today's commits
bigfoot track

# Track any specific date
bigfoot track --date 2025-09-15

# Focus on specific directories
bigfoot track --search-paths "/home/user/work,/home/user/personal"

# Check app status and database
bigfoot doctor

# See all available commands
bigfoot --help
```

## Commands

- `bigfoot track` - Track commits from local git repositories
- `bigfoot doctor` - Run diagnostics and check system status

## Requirements

- Python 3.8+
- Git installed

## License

MIT License
