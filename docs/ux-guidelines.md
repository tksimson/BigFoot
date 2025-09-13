# BigFoot - UX Guidelines

## Design Philosophy

**Terminal-first**: Optimized for developer workflow with instant feedback and minimal friction.

## Core UX Principles

- **Progressive Disclosure**: Show essential info first, details on demand
- **Cognitive Load**: Minimize mental overhead with clear, scannable output
- **Consistent Patterns**: All commands follow the same interaction model
- **Immediate Gratification**: Every command provides instant, meaningful feedback
- **Error Prevention**: Guide users away from mistakes with smart defaults

## Visual Design System

### Color Psychology
- **Green**: Success, completed goals, positive progress
- **Yellow**: Progress, warnings, attention needed
- **Red**: Errors, missed goals, urgent attention
- **Blue**: Information, neutral status
- **Cyan**: Highlights, important data

### Iconography
- **🎯**: Goals and targets
- **🔥**: Streaks and momentum
- **📈**: Trends and progress
- **📊**: Statistics and overviews
- **🏆**: Achievements and rewards
- **❌**: Errors and failures
- **💡**: Tips and suggestions

### Typography & Layout
- **Hierarchy**: Most important info at top, details below
- **Whitespace**: Generous spacing for terminal readability
- **Alignment**: Consistent left alignment with proper indentation
- **Contrast**: High contrast for terminal visibility

## Command Design Principles

### Primary Path (90% of usage)
- `bigfoot track` → `bigfoot status` covers daily workflow
- Commands complete in <2 seconds with progress indicators
- Show scannable output with whitespace, colors, and symbols

### Progressive Disclosure
- Basic info first, details with flags
- Essential data always visible
- Advanced features accessible but not overwhelming

## Output Design Examples

### Daily Progress
```
🎯 Today's Progress: 8 commits
   ┌─────────────────────────────────────┐
   │ ████████████░░░░░░░░░░░░░░░░░░░░░░░ │ 40% (8/20 goal)
   └─────────────────────────────────────┘
   
🔥 Current Streak: 5 days
📈 This week: 32 commits (+5 from yesterday)
```

### Weekly Overview
```
📊 Weekly Overview
   Mon ████████ 12 commits
   Tue ████████████ 18 commits  
   Wed ██████ 8 commits
   Thu ████████████ 16 commits
   Fri ████████ 10 commits
   
🏆 Achievements this week: 3 new milestones!
```

### Error Messages
```
❌ GitHub API Error
   Rate limit exceeded. Retry in 15 minutes.
   
   💡 Quick fixes:
   • Wait 15 minutes and try again
   • Check your token permissions
   • Run `bigfoot doctor` for diagnostics
```

### Repository Access Errors
```
❌ Repository Access Issues
   🔒 username/private-repo: Token lacks 'repo' scope
   🚫 org/restricted-repo: Insufficient organization permissions  
   ❓ unknown/repo: Repository not found or misspelled
   
   💡 Quick fixes:
   • For private repos: Regenerate token with 'repo' scope
   • For org repos: Check organization access permissions
   • For unknown repos: Verify spelling and repository existence
```

## User Journey Design

### Onboarding (2 minutes)
1. **Welcome message** with clear value proposition
2. **Step-by-step setup** with validation and feedback
3. **Repository access validation** with clear error categorization
4. **Immediate success** - first progress report
5. **Next steps** guidance

### Daily Usage (30 seconds)
1. **Single command** to track and view progress
2. **Instant feedback** with visual progress indicators
3. **Motivational elements** - streaks, achievements, comparisons
4. **Clear next actions** - what to do to improve

### Error Recovery
1. **Smart diagnostics** - identify the specific issue
2. **Clear messaging** - explain what went wrong
3. **Actionable guidance** - specific steps to resolve
4. **Recovery hints** - alternative approaches

## Motivation Engine Design

### Achievement System
- **Streak Milestones**: 3, 7, 14, 30 days (with visual progress)
- **Daily Volume**: 5, 10, 20+ commits (contextual celebration)
- **Consistency**: 7-day, 30-day patterns (momentum indicators)
- **Comeback**: Return after break (encouraging, not judgmental)

### Progress Visualization
- **Progress Bars**: ASCII art for goal completion
- **Trend Indicators**: Arrows and symbols for direction
- **Comparisons**: vs yesterday, vs last week, vs personal best
- **Context**: Show relevant benchmarks and milestones

### Motivational Messaging
- **Positive Reinforcement**: Celebrate wins, no matter how small
- **Encouragement**: Support during low periods
- **Challenge**: Gentle nudges to improve
- **Achievement**: Recognition of milestones and streaks

## Terminal-Specific Considerations

### Scannable Output
- Use consistent spacing and alignment
- Group related information together
- Use symbols and colors for quick parsing
- Avoid dense walls of text

### Responsive Design
- Adapt to different terminal sizes
- Graceful degradation for limited color support
- Clear output even in monochrome terminals
- Proper handling of terminal width

### Performance
- Fast command execution (<2 seconds)
- Progress indicators for longer operations
- Clear feedback during data collection
- Responsive interface even during API calls

## Accessibility

### Color Blindness
- Don't rely solely on color for information
- Use symbols and text alongside colors
- Provide alternative indicators

### Screen Readers
- Clear text descriptions
- Logical reading order
- Descriptive error messages

### Low Vision
- High contrast output
- Clear, readable fonts
- Adequate spacing between elements

## Consistency Guidelines

### Command Structure
- All commands follow same pattern: `bigfoot <action> [options]`
- Consistent help text format
- Standardized error message structure

### Output Format
- Consistent header styles
- Standardized progress bar format
- Uniform spacing and alignment
- Predictable information hierarchy

### Error Handling
- Consistent error message format
- Standardized recovery suggestions
- Uniform diagnostic output
- Clear action items for resolution
