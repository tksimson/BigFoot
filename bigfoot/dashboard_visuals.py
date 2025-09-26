"""Visual components and rendering for the BigFoot motivational dashboard."""

import math
import random
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn
from rich.align import Align
from rich import box

from .dashboard import (
    StreakData, MomentumMetrics, Achievement, GoalProgress, 
    PerformanceLevel, DashboardAnalytics, HistoricalData, HistoricalPeriod
)


class MotivationalEngine:
    """Dynamic motivational message generator with synonym randomization."""
    
    def __init__(self):
        """Initialize with synonym dictionaries and message templates."""
        # Synonym dictionaries for randomization
        self.synonyms = {
            'amazing': ['amazing', 'incredible', 'outstanding', 'fantastic', 'excellent', 'superb'],
            'building': ['building', 'developing', 'creating', 'growing', 'forging', 'crafting'],
            'streak': ['streak', 'run', 'chain', 'momentum', 'flow', 'rhythm'],
            'progress': ['progress', 'growth', 'momentum', 'improvement', 'advancement', 'evolution'],
            'keep': ['keep', 'maintain', 'continue', 'sustain', 'push', 'drive'],
            'crushing': ['crushing', 'dominating', 'smashing', 'destroying', 'owning', 'killing'],
            'going': ['going', 'moving', 'pushing', 'flowing', 'rolling', 'charging'],
            'legendary': ['legendary', 'epic', 'unstoppable', 'godlike', 'mythical', 'insane'],
            'power': ['power', 'strength', 'force', 'energy', 'drive', 'fire'],
            'strong': ['strong', 'solid', 'powerful', 'robust', 'fierce', 'unstoppable'],
            'next': ['next', 'upcoming', 'approaching', 'incoming', 'future', 'coming']
        }
        
        # Message templates for each performance level
        self.templates = {
            PerformanceLevel.LEGENDARY: [
                "🏆 {streak} days {strong}! You're operating on a different level now.",
                "👑 That {commits} commits this week? Pure {legendary} performance.",
                
                "🔥 {streak}-day {streak} with {commits} commits? You're in beast mode!",
                "⚡ This consistency is what separates legends from everyone else.",
                
                "💎 {commits} commits this week - that's {legendary} territory!",
                "🚀 Your {power} is undeniable. {keep} this momentum {going}!",
                
                "🌟 {streak} days straight? You've transcended normal coding habits.",
                "🎯 Challenge: Can you maintain this {legendary} status? I know you can!",
                
                "👹 {commits} commits with {consistency} active days? Monster performance!",
                "⭐ You're not just coding - you're {building} mastery daily."
            ],
            PerformanceLevel.CRUSHING: [
                "🔥 {streak} days and {commits} commits? You're absolutely {crushing} it!",
                "💪 That {change}% growth shows your momentum is {strong}.",
                
                "⚡ {consistency} active days this week - your rhythm is {amazing}!",
                "🎯 {milestone_days} days to your {next} milestone. You've got this!",
                
                "🚀 {commits} commits shows real commitment. {keep} that fire burning!",
                "📈 Your {progress} is accelerating. Can you feel that {power}?",
                
                "💎 This {streak}-day run proves you show up when it counts.",
                "🌟 {consistency}/7 days active? That's champion-level consistency!",
                
                "🔥 Week-over-week growth: {change}%! Your momentum is {building}.",
                "⚡ You're {building} something {strong}. {next} level incoming!"
            ],
            PerformanceLevel.BUILDING: [
                "⚡ {consistency} active days this week - you're finding your rhythm!",
                "🎯 {milestone_days} days to {milestone} milestone. {progress} is happening!",
                
                "🌱 Your {streak}-day {streak} shows real potential. {keep} {building}!",
                "💪 Every commit proves you're someone who follows through.",
                
                "📊 {commits} commits this week? Solid {progress} happening here.",
                "🔥 You're {building} the habit of showing up daily. That's {power}!",
                
                "⚡ {consistency}/7 active days - momentum is clearly {building}!",
                "🚀 This is where champions separate from average. Which are you?",
                
                "💎 Your consistency this week is {amazing}. {keep} it {going}!",
                "🎯 {milestone_days} more days to level up. You're almost there!"
            ],
            PerformanceLevel.STARTING: [
                "🌟 Every {legendary} coder started exactly where you are now.",
                "🚀 You've taken the first step - that puts you ahead of most!",
                
                "💎 Small wins lead to big victories. Just focus on today.",
                "⚡ The journey of a thousand commits begins with one. You're {building}!",
                
                "🔥 Tracking your {progress} shows you're serious about growth.",
                "🎯 Champions aren't born - they're forged one commit at a time.",
                
                "🌱 Your coding journey starts now. Every expert was once a beginner.",
                "💪 Just {keep} showing up. Consistency beats perfection every time.",
                
                "⭐ You're {building} something {amazing}. One day at a time wins.",
                "🚀 Today's commit is tomorrow's momentum. Start your {streak}!"
            ]
        }
    
    def get_random_synonym(self, word: str) -> str:
        """Get random synonym for a word, fallback to original if not found."""
        return random.choice(self.synonyms.get(word, [word]))
    
    def format_message(self, template: str, streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Format message template with data and random synonyms."""
        # Calculate dynamic values
        change = abs(momentum.week_over_week_change)
        
        # Create formatting dictionary with synonym randomization
        format_dict = {
            'streak': streak_data.current_streak,
            'commits': momentum.this_week_commits,
            'consistency': momentum.consistency_score,
            'milestone': streak_data.next_milestone,
            'milestone_days': streak_data.days_to_milestone,
            'change': int(change),
            
            # Randomized synonyms
            'amazing': self.get_random_synonym('amazing'),
            'building': self.get_random_synonym('building'),
            'progress': self.get_random_synonym('progress'),
            'keep': self.get_random_synonym('keep'),
            'crushing': self.get_random_synonym('crushing'),
            'going': self.get_random_synonym('going'),
            'legendary': self.get_random_synonym('legendary'),
            'power': self.get_random_synonym('power'),
            'strong': self.get_random_synonym('strong'),
            'next': self.get_random_synonym('next')
        }
        
        return template.format(**format_dict)
    
    def generate_message(self, performance_level: PerformanceLevel, 
                        streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Generate dynamic motivational message."""
        templates = self.templates.get(performance_level, self.templates[PerformanceLevel.STARTING])
        
        # Randomly select 2 lines (each template is a 2-line pair)
        selected_pair = random.choice(list(zip(templates[::2], templates[1::2])))
        
        # Format both lines with data and random synonyms
        line1 = self.format_message(selected_pair[0], streak_data, momentum)
        line2 = self.format_message(selected_pair[1], streak_data, momentum)
        
        return f"{line1}\n{line2}"


class HistoricalChartRenderer:
    """Renders ASCII historical charts for commit data visualization."""
    
    def __init__(self, max_width: int = 60, max_height: int = 8):
        """Initialize chart renderer.
        
        Args:
            max_width: Maximum chart width in characters
            max_height: Maximum chart height in bars
        """
        self.max_width = max_width
        self.max_height = max_height
    
    def render_historical_chart(self, historical_data: HistoricalData) -> Panel:
        """Render complete historical chart with analysis.
        
        Args:
            historical_data: Historical data to visualize
            
        Returns:
            Rich Panel with ASCII chart and trend analysis
        """
        if not historical_data.periods:
            return Panel(
                "📈 No commit data available for historical chart.\n"
                "Run [cyan]bigfoot track[/cyan] to start building your history!",
                title="📊 HISTORICAL TRENDS",
                border_style="bright_blue",
                box=box.HEAVY
            )
        
        # Generate ASCII chart
        chart_ascii = self._generate_ascii_chart(historical_data)
        
        # Generate trend summary
        trend_summary = self._generate_trend_summary(historical_data)
        
        # Combine chart and summary
        content = f"{chart_ascii}\n\n{trend_summary}"
        
        # Dynamic title based on chart type
        title_map = {
            'daily': '📈 DAILY COMMIT HISTORY',
            'weekly': '📊 WEEKLY COMMIT TRENDS', 
            'monthly': '📈 MONTHLY COMMIT OVERVIEW'
        }
        
        title = title_map.get(historical_data.chart_type, '📊 COMMIT HISTORY')
        
        return Panel(
            content,
            title=f"[bright_blue bold]{title}[/bright_blue bold]",
            border_style="bright_blue",
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def _generate_ascii_chart(self, historical_data: HistoricalData) -> str:
        """Generate ASCII bar chart from historical data."""
        periods = historical_data.periods
        if not periods:
            return "No data available"
        
        # Extract commit counts
        commit_counts = [p.commits for p in periods]
        max_commits = max(commit_counts) if commit_counts else 1
        
        # Handle edge case where all commits are 0
        if max_commits == 0:
            max_commits = 1
        
        # Calculate scaling
        scale_factor = self.max_height / max_commits
        
        # Build chart from top to bottom
        chart_lines = []
        
        for level in range(self.max_height, 0, -1):
            # Create Y-axis label
            y_value = int((level / self.max_height) * max_commits)
            line = f"{y_value:3d} "
            
            # Add bars for each period
            for commits in commit_counts:
                scaled_height = commits * scale_factor
                if scaled_height >= level:
                    line += "██"
                else:
                    line += "  "
                line += " "  # Spacing between bars
            
            chart_lines.append(line)
        
        # Add bottom axis
        axis_line = "  0 └" + "─" * (len(commit_counts) * 3) + "┘"
        chart_lines.append(axis_line)
        
        # Add period labels (smart sampling for readability)
        label_line = self._generate_label_line(periods)
        chart_lines.append(label_line)
        
        return "\n".join(chart_lines)
    
    def _generate_label_line(self, periods: List[HistoricalPeriod]) -> str:
        """Generate smart period labels that fit the chart width."""
        if not periods:
            return ""
        
        total_periods = len(periods)
        
        # Smart label sampling based on number of periods
        if total_periods <= 10:
            # Show all labels for small datasets
            step = 1
        elif total_periods <= 30:
            # Show every 3rd label for medium datasets
            step = 3
        elif total_periods <= 90:
            # Show every 7th label for large datasets (roughly weekly)
            step = 7
        else:
            # Show every 15th label for very large datasets
            step = 15
        
        label_line = "    "  # Indent to align with chart
        
        for i, period in enumerate(periods):
            if i % step == 0 or i == total_periods - 1:
                # Show this label
                label = period.label
                if len(label) > 6:  # Truncate long labels
                    label = label[:6]
                label_line += f"{label:>6}"
            else:
                # Skip this label
                label_line += "      "  # Empty space
            
            if i < total_periods - 1:
                label_line += " "
        
        return label_line
    
    def _generate_trend_summary(self, historical_data: HistoricalData) -> str:
        """Generate trend analysis summary."""
        # Trend direction emoji and text
        trend_map = {
            'up': ('↗️', 'growth'),
            'down': ('↘️', 'decline'), 
            'stable': ('➡️', 'stable')
        }
        
        trend_emoji, trend_text = trend_map.get(
            historical_data.trend_direction, ('📊', 'analysis')
        )
        
        # Build summary
        summary_parts = []
        
        # Primary trend info
        if historical_data.trend_direction == 'up':
            summary_parts.append(
                f"📊 Trend: {trend_emoji} +{historical_data.trend_percentage:.0f}% {trend_text}"
            )
        elif historical_data.trend_direction == 'down':
            summary_parts.append(
                f"📊 Trend: {trend_emoji} -{historical_data.trend_percentage:.0f}% {trend_text}"
            )
        else:
            summary_parts.append(
                f"📊 Trend: {trend_emoji} {trend_text} performance"
            )
        
        # Key metrics
        if historical_data.chart_type == 'daily':
            summary_parts.append(f"Peak: {historical_data.peak_commits} commits")
            summary_parts.append(f"Avg: {historical_data.average_commits:.1f}/day")
        elif historical_data.chart_type == 'weekly':
            summary_parts.append(f"Best week: {historical_data.peak_commits} commits")
            summary_parts.append(f"Avg: {historical_data.average_commits:.1f}/week")
        else:  # monthly
            summary_parts.append(f"Best month: {historical_data.peak_commits} commits")
            summary_parts.append(f"Total: {historical_data.total_commits} commits")
        
        return " | ".join(summary_parts)


class DashboardRenderer:
    """Renders dashboard components using Rich library."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize renderer with console and motivational engine.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.motivational_engine = MotivationalEngine()
        self.chart_renderer = HistoricalChartRenderer()
    
    def render_streak_header(self, streak_data: StreakData) -> Panel:
        """Render the main streak header with fire animation.
        
        Args:
            streak_data: Current streak information
            
        Returns:
            Rich Panel with streak visualization
        """
        streak = streak_data.current_streak
        
        # Dynamic title based on streak length
        if streak == 0:
            title = "🌱 START YOUR JOURNEY"
            color = "yellow"
        elif streak < 3:
            title = "🔥 BUILDING MOMENTUM"
            color = "orange3"
        elif streak < 7:
            title = "⚡ ON FIRE"
            color = "red"
        elif streak < 21:
            title = "🚀 ABSOLUTELY CRUSHING IT"
            color = "bright_red"
        else:
            title = "👑 LEGENDARY STATUS"
            color = "gold1"
        
        # Create progress bar for streak
        if streak_data.next_milestone > 0:
            bar_width = 50
            filled = int((streak_data.goal_progress * bar_width))
            empty = bar_width - filled
            
            progress_bar = "█" * filled + "░" * empty
            progress_text = f"{streak} / {streak_data.next_milestone} ({streak_data.goal_progress*100:.0f}%)"
        else:
            progress_bar = "█" * 50
            progress_text = f"{streak} DAYS - UNSTOPPABLE!"
        
        # Build content
        content = Text()
        content.append(f"\n{progress_bar}\n", style="bright_red bold")
        content.append(f"     {streak} DAY STREAK     \n", style="white bold")
        content.append(f"{progress_text}\n", style="bright_white")
        
        if streak_data.days_to_milestone > 0:
            content.append(f"\n🎯 Next Milestone: {streak_data.next_milestone} days ", style="cyan")
            content.append(f"({streak_data.days_to_milestone} to go!)", style="bright_cyan bold")
        else:
            content.append(f"\n🏆 MILESTONE ACHIEVED! ", style="gold1 bold")
            content.append(f"You're at {streak} days!", style="bright_white")
        
        return Panel(
            Align.center(content),
            title=f"[{color} bold]{title}[/{color} bold]",
            border_style=color,
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def render_momentum_section(self, momentum: MomentumMetrics) -> Panel:
        """Render momentum analysis with trend chart.
        
        Args:
            momentum: Momentum metrics and trends
            
        Returns:
            Rich Panel with momentum visualization
        """
        # Week over week comparison
        if momentum.week_over_week_change > 0:
            change_emoji = "📈"
            change_color = "green"
            change_text = f"↗️ +{momentum.week_over_week_change:.0f}%"
            mood_text = "(Accelerating!)" if momentum.week_over_week_change > 20 else "(Growing!)"
        elif momentum.week_over_week_change < 0:
            change_emoji = "📉"
            change_color = "red"
            change_text = f"↘️ {momentum.week_over_week_change:.0f}%"
            mood_text = "(Let's bounce back!)"
        else:
            change_emoji = "➡️"
            change_color = "blue"
            change_text = "→ Same"
            mood_text = "(Steady progress!)"
        
        # Create mini ASCII chart
        max_commits = max(momentum.daily_trend) if momentum.daily_trend else 1
        chart_height = 8
        chart_lines = []
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        for level in range(chart_height, 0, -1):
            line = f"{level*2:2d} "
            for commits in momentum.daily_trend:
                if max_commits > 0:
                    bar_height = (commits / max_commits) * chart_height
                    if bar_height >= level:
                        line += "██"
                    else:
                        line += "  "
                else:
                    line += "  "
                line += " "
            chart_lines.append(line)
        
        # Days labels
        day_line = " 0 " + "".join(f"{day[:2]} " for day in days[:len(momentum.daily_trend)])
        chart_lines.append(day_line)
        
        chart = "\n".join(chart_lines)
        
        # Build content
        content = []
        content.append(f"📊 This Week vs Last Week:")
        content.append(f"  Commits: {momentum.this_week_commits} {change_text} {mood_text}")
        content.append(f"  Consistency: {momentum.consistency_score}/7 days active")
        content.append(f"  Daily Average: {momentum.average_daily:.1f} commits")
        content.append("")
        content.append("📈 7-Day Trend:")
        content.append(chart)
        
        # Performance level indicator
        level_text = {
            PerformanceLevel.LEGENDARY: "🏆 LEGENDARY PERFORMANCE!",
            PerformanceLevel.CRUSHING: "🔥 CRUSHING IT!",
            PerformanceLevel.BUILDING: "⚡ BUILDING MOMENTUM!",
            PerformanceLevel.STARTING: "🌱 BUILDING FOUNDATION!"
        }.get(momentum.performance_level, "📊 ANALYZING PERFORMANCE")
        
        content.append("")
        content.append(f"🚀 Status: {level_text}")
        
        return Panel(
            "\n".join(content),
            title="[bright_blue bold]📊 MOMENTUM ANALYSIS[/bright_blue bold]",
            border_style="bright_blue",
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def render_achievements(self, achievements: List[Achievement]) -> Panel:
        """Render achievement system with unlocked badges.
        
        Args:
            achievements: List of achievements to display
            
        Returns:
            Rich Panel with achievements
        """
        # Separate unlocked and locked achievements
        unlocked = [a for a in achievements if a.unlocked_date is not None]
        in_progress = [a for a in achievements if a.unlocked_date is None and a.progress and a.progress > 0]
        
        content = []
        
        if unlocked:
            content.append("🎉 [bright_green bold]Recently Unlocked:[/bright_green bold]")
            
            # Create table for unlocked achievements
            table = Table.grid(padding=1)
            table.add_column(style="bright_yellow", width=3)
            table.add_column(style="bright_white", width=20)
            table.add_column(style="dim white")
            
            for achievement in unlocked[-3:]:  # Show last 3
                table.add_row(
                    achievement.emoji,
                    achievement.name,
                    achievement.description
                )
            
            content.append(table)
            content.append("")
        
        if in_progress:
            content.append("🎯 [bright_cyan bold]In Progress:[/bright_cyan bold]")
            
            for achievement in in_progress[:3]:  # Show top 3
                progress_pct = int(achievement.progress * 100)
                bar_length = 20
                filled = int((achievement.progress or 0) * bar_length)
                empty = bar_length - filled
                
                progress_bar = "█" * filled + "░" * empty
                content.append(f"  {achievement.emoji} {achievement.name}")
                content.append(f"    {progress_bar} {progress_pct}%")
                content.append(f"    {achievement.description}")
                content.append("")
        
        if not unlocked and not in_progress:
            content.append("🌟 Start coding to unlock your first achievements!")
            content.append("   Your coding journey begins with a single commit!")
        
        # Create a renderable group from the content
        from rich.console import Group
        renderable_content = [item for item in content if item]
        
        return Panel(
            Group(*renderable_content),
            title="[bright_magenta bold]🏆 ACHIEVEMENTS[/bright_magenta bold]",
            border_style="bright_magenta",
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def render_goals_progress(self, goals: GoalProgress) -> Panel:
        """Render goal progress with visual progress bars.
        
        Args:
            goals: Goal progress data
            
        Returns:
            Rich Panel with goal visualization
        """
        content = []
        
        # Helper function to create progress bar
        def create_progress_bar(current: int, target: int, width: int = 30) -> str:
            if target == 0:
                return "░" * width + " (No goal set)"
            
            progress = min(1.0, current / target)
            filled = int(progress * width)
            empty = width - filled
            
            if progress >= 1.0:
                bar_color = "bright_green"
                status = "CRUSHED!"
            elif progress >= 0.8:
                bar_color = "yellow"
                status = "Almost there!"
            elif progress >= 0.5:
                bar_color = "blue"
                status = "Good progress!"
            else:
                bar_color = "red"
                status = "Keep going!"
            
            bar = "█" * filled + "░" * empty
            percentage = int(progress * 100)
            
            return f"[{bar_color}]{bar}[/{bar_color}] {current}/{target} ({percentage}%) {status}"
        
        content.append("🎯 [bright_cyan bold]CURRENT GOALS[/bright_cyan bold]")
        content.append("")
        content.append(f"Daily:   {create_progress_bar(goals.daily_current, goals.daily_goal)}")
        content.append(f"Weekly:  {create_progress_bar(goals.weekly_current, goals.weekly_goal)}")
        content.append(f"Monthly: {create_progress_bar(goals.monthly_current, goals.monthly_goal)}")
        
        # Show which goals are exceeded
        exceeded = []
        if goals.daily_current > goals.daily_goal:
            exceeded.append(f"Daily goal exceeded by {goals.daily_current - goals.daily_goal}!")
        if goals.weekly_current > goals.weekly_goal:
            exceeded.append(f"Weekly goal exceeded by {goals.weekly_current - goals.weekly_goal}!")
        if goals.monthly_current > goals.monthly_goal:
            exceeded.append(f"Monthly goal exceeded by {goals.monthly_current - goals.monthly_goal}!")
        
        if exceeded:
            content.append("")
            content.append("🚀 [bright_green bold]GOAL CRUSHER ALERT![/bright_green bold]")
            for exceed in exceeded:
                content.append(f"  • {exceed}")
        
        return Panel(
            "\n".join(content),
            title="[bright_yellow bold]🎯 GOALS & PROGRESS[/bright_yellow bold]",
            border_style="bright_yellow",
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def render_heatmap(self, heatmap_data: Dict[str, int], days: int = 30) -> Panel:
        """Render activity heatmap for the last N days.
        
        Args:
            heatmap_data: Dictionary mapping dates to commit counts
            days: Number of days to display
            
        Returns:
            Rich Panel with heatmap visualization
        """
        def get_heat_emoji(commits: int) -> str:
            """Get emoji based on commit count."""
            if commits == 0:
                return "⚫"  # No activity
            elif commits <= 2:
                return "🟡"  # Light activity
            elif commits <= 7:
                return "🟢"  # Good activity  
            else:
                return "🔥"  # High activity
        
        # Organize data by weeks
        dates = sorted(heatmap_data.keys())
        if not dates:
            return Panel("No data available for heatmap", title="📈 ACTIVITY HEATMAP", box=box.HEAVY)
        
        content = []
        content.append("📈 [bright_white bold]CODING ACTIVITY HEATMAP (Last 30 Days)[/bright_white bold]")
        content.append("")
        
        # Create heatmap grid
        start_date = datetime.strptime(dates[0], '%Y-%m-%d').date()
        end_date = datetime.strptime(dates[-1], '%Y-%m-%d').date()
        
        # Build week by week
        content.append("    Mon Tue Wed Thu Fri Sat Sun")
        
        current = start_date
        week_num = 1
        week_line = f"W{week_num}  "
        day_count = 0
        
        # Pad to start on Monday
        weekday = current.weekday()
        for _ in range(weekday):
            week_line += "    "
            day_count += 1
        
        while current <= end_date:
            commits = heatmap_data.get(current.isoformat(), 0)
            emoji = get_heat_emoji(commits)
            week_line += f"{emoji}  "
            day_count += 1
            
            # End of week
            if day_count % 7 == 0:
                content.append(week_line)
                week_num += 1
                week_line = f"W{week_num}  " if current < end_date else ""
                day_count = 0
            
            current += timedelta(days=1)
        
        # Add final partial week
        if day_count > 0:
            content.append(week_line)
        
        content.append("")
        content.append("Legend: 🔥 High (8+) 🟢 Good (3-7) 🟡 Light (1-2) ⚫ Rest")
        
        # Summary stats
        total_commits = sum(heatmap_data.values())
        active_days = sum(1 for count in heatmap_data.values() if count > 0)
        consistency = int((active_days / len(heatmap_data)) * 100) if heatmap_data else 0
        
        content.append("")
        content.append(f"📊 [bright_cyan]Summary:[/bright_cyan]")
        content.append(f"  • Total Commits: {total_commits}")
        content.append(f"  • Active Days: {active_days}/{len(heatmap_data)} ({consistency}%)")
        
        if total_commits > 0:
            avg_daily = total_commits / len(heatmap_data)
            content.append(f"  • Daily Average: {avg_daily:.1f} commits")
        
        return Panel(
            "\n".join(content),
            title="[bright_green bold]📈 ACTIVITY HEATMAP[/bright_green bold]",
            border_style="bright_green",
            padding=(1, 2),
            box=box.HEAVY
        )
    
    def render_motivational_message(self, performance_level: PerformanceLevel, 
                                  streak_data: StreakData, momentum: MomentumMetrics) -> Panel:
        """Render concise, dynamic motivational message.
        
        Args:
            performance_level: Current performance categorization
            streak_data: Streak information  
            momentum: Momentum metrics
            
        Returns:
            Rich Panel with 2-line motivational message
        """
        message = self.motivational_engine.generate_message(
            performance_level, streak_data, momentum
        )
        
        return Panel(
            message,
            title="[gold1 bold]💬 MOTIVATIONAL BOOST[/gold1 bold]",
            border_style="gold1",
            padding=(0, 1),  # Reduced padding for more compact display
            box=box.HEAVY
        )
    
    def render_historical_chart(self, historical_data: HistoricalData) -> Panel:
        """Render historical chart using the chart renderer.
        
        Args:
            historical_data: Historical data to visualize
            
        Returns:
            Rich Panel with historical chart
        """
        return self.chart_renderer.render_historical_chart(historical_data)
