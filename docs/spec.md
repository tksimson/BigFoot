# BigFoot MVP - Personal Progress Tracker

## Product Vision

A lightweight Python CLI tool that motivates developers to code daily by tracking GitHub activity and providing instant motivational feedback.

**Core Value Proposition**: Get developers coding daily through positive reinforcement and progress visualization.

## MVP Goals

- **Primary**: Increase daily coding consistency through motivation
- **Secondary**: Provide simple, fast progress tracking without friction
- **Success Metric**: Users maintain 7+ day coding streaks

## Target User

- **Primary**: Solo developers who want to build consistent coding habits
- **Pain Point**: Lack of motivation and progress visibility in daily coding
- **Solution**: Terminal-based progress tracking with instant feedback

## Core Features (MVP)

### Essential Commands
```bash
bigfoot track    # Collect today's data + show progress (90% of usage)
bigfoot status   # Quick overview of current state
bigfoot init     # First-time setup
```

### Key Capabilities
- Track daily GitHub commits across multiple repositories
- Calculate and display coding streaks
- Show progress toward daily goals with visual indicators
- Provide motivational messages and achievements
- Store data locally in SQLite (no cloud dependencies)

## User Journey

### Day 1: Setup (2 minutes)
```bash
$ pip install bigfoot
$ bigfoot init
# Enter GitHub token, add repositories
$ bigfoot track
# See first progress report
```

### Daily Usage (30 seconds)
```bash
$ bigfoot track
🎯 Today's Progress: 8 commits
   ┌─────────────────────────────────────┐
   │ ████████████░░░░░░░░░░░░░░░░░░░░░░░ │ 40% (8/20 goal)
   └─────────────────────────────────────┘
   
🔥 Current Streak: 5 days
📈 This week: 32 commits (+5 from yesterday)
```

## Success Metrics

- **Primary**: Daily active usage of `bigfoot track`
- **Secondary**: Average streak length > 7 days
- **Tertiary**: User retention > 80% weekly

## MVP Constraints

- **Terminal only** - No web interface
- **GitHub only** - No other Git providers
- **Public repos only** - Private repo support in Phase 2
- **Commits only** - No PRs, issues, or other activity
- **Local storage** - No cloud sync
- **Single user** - No multi-user support

## Technical Requirements

- **Language**: Python 3.8+
- **Database**: SQLite (local)
- **API**: GitHub API only
- **Performance**: Commands complete in <2 seconds
- **Dependencies**: Minimal (Click, Rich, Requests, PyYAML)

## Implementation Phases

### Phase 1: Core MVP (Week 1-2)
- Basic CLI with track/status commands
- GitHub API integration
- SQLite database with commits/streaks
- Simple progress visualization

### Phase 2: Polish & Private Repos (Week 3)
- Rich terminal output with colors/emojis
- Interactive setup wizard with step-by-step validation
- **Private repository support** with smart validation
- **Enhanced error handling** with categorized messages and actionable guidance
- **Graceful degradation** - continue with accessible repos when some are restricted

### Phase 3: Motivation (Week 4)
- Achievement system
- Enhanced progress indicators
- Motivational messaging

## Out of Scope (Post-MVP)

- Web dashboard
- Multi-provider support (GitLab, Bitbucket)
- Advanced analytics
- Cloud sync
- Multi-user features
- Health/lifestyle tracking

---

*For detailed technical specifications, see [architecture.md](architecture.md)*  
*For UX guidelines and design principles, see [ux-guidelines.md](ux-guidelines.md)*