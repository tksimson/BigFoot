# BigFoot - Personal Progress Tracker

A lightweight Python CLI tool that motivates developers to code daily by tracking GitHub activity and providing instant motivational feedback.

## Quick Start

```bash
# Install
pip install -e .

# Setup
bigfoot init

# Track daily progress
bigfoot track
```

## Features

- 🎯 Track daily GitHub commits across multiple repositories
- 🔥 Calculate and display coding streaks
- 📈 Show progress toward daily goals with visual indicators
- 🏆 Provide motivational messages and achievements
- 💾 Store data locally in SQLite (no cloud dependencies)

## Commands

- `bigfoot track` - Collect today's data and show progress
- `bigfoot status` - Quick overview of current state
- `bigfoot init` - First-time setup

## Requirements

- Python 3.8+
- GitHub Personal Access Token
- Internet connection for GitHub API access

## License

MIT License
