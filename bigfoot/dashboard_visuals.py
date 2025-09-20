"""Visual components and rendering for the BigFoot motivational dashboard."""

import math
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn
from rich.align import Align

from .dashboard import (
    StreakData, MomentumMetrics, Achievement, GoalProgress, 
    PerformanceLevel, DashboardAnalytics
)


class DashboardRenderer:
    """Renders dashboard components using Rich library."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize renderer with console.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
    
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
            padding=(1, 2)
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
            padding=(1, 2)
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
        
        return Panel(
            content[0] if isinstance(content[0], str) else Columns(content) if len(content) > 1 else content[0],
            title="[bright_magenta bold]🏆 ACHIEVEMENTS[/bright_magenta bold]",
            border_style="bright_magenta",
            padding=(1, 2)
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
            padding=(1, 2)
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
            return Panel("No data available for heatmap", title="📈 ACTIVITY HEATMAP")
        
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
            padding=(1, 2)
        )
    
    def render_motivational_message(self, performance_level: PerformanceLevel, 
                                  streak_data: StreakData, momentum: MomentumMetrics) -> Panel:
        """Render Tony Robbins-style motivational message.
        
        Args:
            performance_level: Current performance categorization
            streak_data: Streak information  
            momentum: Momentum metrics
            
        Returns:
            Rich Panel with motivational message
        """
        messages = {
            PerformanceLevel.LEGENDARY: self._get_legendary_message(streak_data, momentum),
            PerformanceLevel.CRUSHING: self._get_crushing_message(streak_data, momentum),
            PerformanceLevel.BUILDING: self._get_building_message(streak_data, momentum),
            PerformanceLevel.STARTING: self._get_starting_message(streak_data, momentum)
        }
        
        message = messages.get(performance_level, "Keep coding, keep growing! 🚀")
        
        return Panel(
            message,
            title="[gold1 bold]💬 MOTIVATIONAL BOOST[/gold1 bold]",
            border_style="gold1",
            padding=(1, 2)
        )
    
    def _get_legendary_message(self, streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Generate message for legendary performance."""
        return f"""[bright_magenta bold]YOU ARE ABSOLUTELY LEGENDARY![/bright_magenta bold]

🏆 A {streak_data.current_streak}-day streak with {momentum.this_week_commits} commits this week? 
That's not just coding - that's [gold1 bold]MASTERY IN ACTION![/gold1 bold]

You've transcended from learning to code to [bright_cyan]BEING A CODER[/bright_cyan]. This consistency 
is what separates the legends from everyone else. You don't code because you have to - 
you code because it's WHO YOU ARE.

🚀 [bright_red bold]CHALLENGE:[/bright_red bold] Can you maintain this legendary status? The question isn't 
if you CAN - it's if you WILL. I know you will! 👑"""

    def _get_crushing_message(self, streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Generate message for crushing performance."""  
        change_msg = ""
        if momentum.week_over_week_change > 0:
            change_msg = f" That {momentum.week_over_week_change:.0f}% increase this week? ELECTRIC!"
        
        return f"""[bright_red bold]YOU ARE ABSOLUTELY CRUSHING IT![/bright_red bold]

🔥 This {streak_data.current_streak}-day streak isn't just about code - it's about 
[bright_yellow]WHO YOU'RE BECOMING[/bright_yellow]. You're building the identity of someone who 
SHOWS UP every single day. That consistency? That's the foundation of GREATNESS!

{momentum.this_week_commits} commits this week!{change_msg} Can you feel that momentum? 
That's the [bright_green]compound effect of excellence[/bright_green] in action.

🎯 [bright_cyan bold]BREAKTHROUGH MOMENT:[/bright_cyan bold] You're {streak_data.days_to_milestone} days from your next milestone. 
This is where champions are made. Keep that fire burning! 🚀"""

    def _get_building_message(self, streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Generate message for building momentum."""
        return f"""[bright_blue bold]MOMENTUM IS BUILDING![/bright_blue bold]

⚡ I can see it happening - you're finding your rhythm! {momentum.consistency_score} active days 
this week is [bright_green]FANTASTIC progress[/bright_green]. Every commit is proof that you're 
someone who follows through.

Your {streak_data.current_streak}-day streak shows you have what it takes. Remember: Champions 
aren't made in the comfort zone. You're building something [bright_yellow]POWERFUL[/bright_yellow] here.

💪 [bright_red bold]POWER MOMENT:[/bright_red bold] This is where average people quit and CHAMPIONS level up. 
You're {streak_data.days_to_milestone} days from your {streak_data.next_milestone}-day milestone. Which one are you? 🎯"""

    def _get_starting_message(self, streak_data: StreakData, momentum: MomentumMetrics) -> str:
        """Generate message for starting out."""
        return f"""[bright_cyan bold]THE JOURNEY OF A THOUSAND COMMITS BEGINS WITH ONE![/bright_cyan bold]

🌟 Every expert was once a beginner. Every champion was once a contender. 
Every success story started with someone who decided [bright_yellow]TODAY[/bright_yellow] was the day to begin.

You've taken the FIRST STEP by tracking your progress. That puts you ahead of 
90% of developers who just hope things improve magically.

🚀 [bright_green bold]SMALL WINS LEAD TO BIG VICTORIES:[/bright_green bold] Just commit to ONE more day. 
Then another. Before you know it, you'll have a streak that amazes you. 
Every coding legend started exactly where you are right now! 💎"""
