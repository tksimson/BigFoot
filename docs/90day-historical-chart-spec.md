# 90-Day Historical Chart Specification

## 🎯 **Overview**
Replace the current "This Week vs Last Week" comparison with a comprehensive 90-day historical visualization that shows coding patterns across different time granularities (days, weeks, months).

## 🎨 **Visual Design**

### **Chart Options**
Users can toggle between three views:
- **Daily View**: 90 individual days with commit counts
- **Weekly View**: 13 weeks of aggregated commits  
- **Monthly View**: 3 months of aggregated commits

### **ASCII Chart Specifications**

#### **Daily View (90 Days)**
```
📈 LAST 90 DAYS (Daily commits)
   8 ██    ██              ██                    ██    
   6 ██ ██ ██       ██  ██ ██          ██    ██ ██ ██ 
   4 ██ ██ ██ ██ ██ ██  ██ ██ ██    ██ ██ ██ ██ ██ ██
   2 ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
   0 └──────────────────────────────────────────────┘
     Sep    Oct    Nov    Dec    Jan    Feb    Mar
     
📊 Trend: ↗️ +45% growth over 90 days | Peak: 8 commits | Avg: 3.2/day
```

#### **Weekly View (13 Weeks)**
```
📈 LAST 13 WEEKS (Weekly totals)  
  35 ████                    ████              ████
  25 ████ ████          ████ ████        ████ ████
  15 ████ ████ ████ ████ ████ ████ ████ ████ ████
   5 ████ ████ ████ ████ ████ ████ ████ ████ ████
   0 └─────────────────────────────────────────────┘
     W1   W3   W5   W7   W9   W11  W13
     
📊 Trend: ↗️ +23% growth | Best week: 35 commits | Avg: 18.5/week
```

#### **Monthly View (3 Months)**
```
📈 LAST 3 MONTHS (Monthly totals)
 120 ████████████          
  80 ████████████ ████████████ 
  40 ████████████ ████████████ ████████████
   0 └─────────────────────────────────────┘
     January      February     March
     
📊 Trend: ↗️ +67% month-over-month | Best: March (120) | Total: 285
```

### **Visual Elements**

#### **Chart Components**
- **Bars**: Unicode block characters (█, ▌, ▐, etc.)
- **Axis**: Clean lines with appropriate labels
- **Scale**: Dynamic scaling based on data range
- **Trend Line**: Optional ASCII trend overlay for patterns
- **Colors**: Rich color coding (green for growth, red for decline)

#### **Summary Stats**
Each chart shows:
- **Trend Direction**: ↗️ ↘️ ➡️ with percentage change
- **Peak Performance**: Highest single period
- **Average**: Mean commits per time unit
- **Total**: Sum for the entire period (monthly view)

## 🎮 **User Interaction**

### **Command Interface**
```bash
# Default dashboard shows daily view
bigfoot                           # 90-day daily chart

# Specific time granularity
bigfoot dashboard --view daily    # 90 individual days
bigfoot dashboard --view weekly   # 13 weeks aggregated  
bigfoot dashboard --view monthly  # 3 months aggregated

# Custom date ranges
bigfoot dashboard --days 60       # Last 60 days
bigfoot dashboard --weeks 26      # Last 26 weeks (6 months)
bigfoot dashboard --months 6      # Last 6 months
```

### **Smart Defaults**
- **First-time users**: Start with daily view for immediate feedback
- **< 30 days data**: Force daily view
- **30-90 days data**: Default to daily, allow weekly
- **90+ days data**: Default to weekly, allow all views

## 🔧 **Technical Implementation**

### **Data Aggregation Strategy**

#### **Daily Aggregation**
```python
def get_daily_commits(self, days: int = 90) -> Dict[str, int]:
    """Get commits for each of the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    return self.database.get_commits_by_date_range(
        start_date.isoformat(), 
        end_date.isoformat()
    )
```

#### **Weekly Aggregation**  
```python
def get_weekly_commits(self, weeks: int = 13) -> List[Dict]:
    """Get commits aggregated by week for last N weeks."""
    weekly_data = []
    
    for week_offset in range(weeks):
        week_end = date.today() - timedelta(days=week_offset*7)
        week_start = week_end - timedelta(days=6)
        
        total_commits = self.database.get_weekly_commits(
            week_start.isoformat(), 
            week_end.isoformat()
        )
        
        weekly_data.append({
            'week_start': week_start,
            'week_end': week_end, 
            'commits': total_commits,
            'week_number': f"W{weeks - week_offset}"
        })
    
    return list(reversed(weekly_data))
```

#### **Monthly Aggregation**
```python
def get_monthly_commits(self, months: int = 3) -> List[Dict]:
    """Get commits aggregated by month for last N months."""
    monthly_data = []
    
    current_date = date.today()
    
    for month_offset in range(months):
        # Get first and last day of target month
        target_date = current_date - relativedelta(months=month_offset)
        month_start = target_date.replace(day=1)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        
        total_commits = self.database.get_commits_by_date_range(
            month_start.isoformat(),
            month_end.isoformat()
        )
        
        monthly_data.append({
            'month': target_date.strftime('%B %Y'),
            'month_start': month_start,
            'month_end': month_end,
            'commits': total_commits
        })
    
    return list(reversed(monthly_data))
```

### **Chart Rendering Engine**

#### **Dynamic Scaling Algorithm**
```python
class HistoricalChartRenderer:
    def __init__(self, max_width: int = 70, max_height: int = 8):
        self.max_width = max_width
        self.max_height = max_height
    
    def render_chart(self, data: List[int], labels: List[str], 
                    chart_type: str) -> str:
        """Render ASCII chart with dynamic scaling."""
        
        # Calculate scaling
        max_value = max(data) if data else 1
        scale_factor = self.max_height / max_value
        
        # Build chart from top to bottom
        chart_lines = []
        for level in range(self.max_height, 0, -1):
            line = f"{level * max_value // self.max_height:3d} "
            
            for value in data:
                scaled_height = int(value * scale_factor)
                if scaled_height >= level:
                    line += "██"
                else:
                    line += "  "
            
            chart_lines.append(line)
        
        # Add bottom axis
        axis_line = "  0 └" + "─" * (len(data) * 2) + "┘"
        chart_lines.append(axis_line)
        
        # Add labels
        label_line = "    " + "".join(f"{label:>4}" for label in labels)
        chart_lines.append(label_line)
        
        return "\n".join(chart_lines)
```

### **Performance Optimizations**

#### **Caching Strategy**
- **Daily cache**: Cache daily aggregations for 1 hour
- **Weekly cache**: Cache weekly aggregations for 6 hours  
- **Monthly cache**: Cache monthly aggregations for 24 hours
- **Incremental updates**: Only recalculate when new commits added

#### **Database Queries**
```sql
-- Optimized daily query with single scan
SELECT date, SUM(count) as total_commits
FROM commits 
WHERE date >= ? AND date <= ?
GROUP BY date
ORDER BY date ASC;

-- Weekly aggregation with date math
SELECT 
    strftime('%Y-%W', date) as week,
    SUM(count) as total_commits,
    MIN(date) as week_start,
    MAX(date) as week_end
FROM commits 
WHERE date >= ? 
GROUP BY strftime('%Y-%W', date)
ORDER BY week ASC;
```

## 🎯 **UX/UI Enhancements**

### **Smart Chart Selection**
```python
def auto_select_chart_type(self, total_days_with_data: int) -> str:
    """Automatically select best chart type based on data."""
    if total_days_with_data < 14:
        return 'daily'  # Not enough for meaningful weekly view
    elif total_days_with_data < 60:
        return 'weekly'  # Good weekly patterns visible
    else:
        return 'monthly'  # Long-term trends matter most
```

### **Progressive Disclosure**
- **Minimal first load**: Show most relevant chart only
- **Hints for more data**: "Run `--view weekly` to see broader patterns"
- **Contextual help**: Different help text based on data amount

### **Error Handling**
```python
# Graceful fallbacks
if insufficient_data_for_weekly:
    console.print("📊 [yellow]Note:[/yellow] Less than 2 weeks of data. Showing daily view.")
    return render_daily_chart()

if no_data_in_period:
    return Panel(
        "📈 No commits found in the last 90 days.\n"
        "Run [cyan]bigfoot track[/cyan] to start building your history!",
        title="📊 HISTORICAL TRENDS"
    )
```

## 🎨 **Visual Examples**

### **Progression Views**

#### **New User (5 days of data)**
```
📈 LAST 5 DAYS (Daily commits)
  3 ██       ██
  2 ██    ██ ██
  1 ██ ██ ██ ██ ██
  0 └─────────────┘
    Mo Tu We Th Fr
    
📊 Trend: Just getting started! | Peak: 3 commits | Avg: 1.8/day
💡 Tip: Run bigfoot track daily to build your streak!
```

#### **Building User (30 days of data)**  
```
📈 LAST 30 DAYS (Daily commits)
  8 ██              ██    
  6 ██    ██     ██ ██ ██ 
  4 ██ ██ ██  ██ ██ ██ ██
  2 ██ ██ ██ ██ ██ ██ ██
  0 └─────────────────────┘
    Week1  Week2  Week3  Week4
    
📊 Trend: ↗️ +127% growth | Peak: 8 commits | Avg: 3.4/day
🎯 Switch to weekly view: bigfoot dashboard --view weekly
```

#### **Power User (90+ days of data)**
```
📈 LAST 13 WEEKS (Weekly totals)
  45 ████              ████ ████
  30 ████ ████    ████ ████ ████ ████
  15 ████ ████ ████ ████ ████ ████ ████
   0 └─────────────────────────────────┘
     W1   W4   W7   W10  W13
     
📊 Trend: ↗️ +89% growth | Best week: 45 commits | Avg: 28.3/week  
🎯 See monthly trends: bigfoot dashboard --view monthly
```

### **Trend Indicators**

#### **Growth Patterns**
- **📈 Accelerating**: Exponential growth curve
- **📊 Linear**: Steady upward trend
- **🎯 Consistent**: Flat but stable performance
- **📉 Declining**: Downward trend (with encouragement)

#### **Special Markers**
- **🔥 Streak markers**: Highlight consecutive active periods
- **⭐ Personal records**: Mark highest single day/week/month
- **💎 Milestones**: Show significant achievements
- **⚡ Recent surge**: Highlight recent improvements

## 🚀 **Implementation Plan**

### **Phase 1: Core Chart Engine**
1. Build `HistoricalChartRenderer` class
2. Implement daily/weekly/monthly aggregation methods
3. Create ASCII chart generation with dynamic scaling
4. Add basic trend calculation

### **Phase 2: UI Integration**
1. Replace current momentum section with historical chart
2. Add command-line options for chart selection
3. Implement smart defaults based on data availability
4. Add contextual hints and tips

### **Phase 3: Advanced Features**
1. Add trend line overlays  
2. Implement performance markers (streaks, records)
3. Add interactive chart switching hints
4. Performance optimization with caching

### **Phase 4: Polish & Testing**
1. Comprehensive error handling
2. Edge case testing (no data, sparse data, etc.)
3. Performance testing with large datasets
4. User experience refinement

## 🎯 **Success Metrics**

### **User Engagement**
- **Increased daily usage**: Users check dashboard more frequently
- **Longer viewing time**: Users spend more time analyzing trends
- **Better retention**: Historical context increases motivation

### **Motivational Impact**
- **Improved streak consistency**: Visual progress encourages daily coding
- **Goal achievement**: Users hit targets more frequently
- **Long-term engagement**: 90-day view encourages sustained effort

### **Technical Performance**
- **Fast rendering**: Charts render in <100ms
- **Memory efficient**: Handle 90+ days of data smoothly
- **Cache effectiveness**: 90%+ cache hit rate for repeated views

## 🔄 **Future Enhancements**

### **Advanced Visualizations**
- **Heatmap overlay**: Combine bar chart with color intensity
- **Multiple metrics**: Show commits, lines of code, files changed
- **Comparative analysis**: Compare different time periods
- **Goal tracking overlay**: Show progress toward targets

### **Interactive Features**
- **Drill-down capability**: Click periods for detailed breakdown
- **Export functionality**: Save charts as images or data
- **Custom date ranges**: User-defined start/end dates
- **Annotation system**: Add notes to significant periods

### **Smart Insights**
- **Pattern recognition**: "You code most on Tuesdays"
- **Productivity predictions**: "Based on trends, you'll hit 1000 commits by..."
- **Habit analysis**: "Your longest productive streak was..."
- **Performance coaching**: "Try coding in the morning for better consistency"

---

## 🎯 **Why This Will Be Game-Changing**

1. **Context Over Comparison**: 90 days tells the REAL story vs 2 weeks
2. **Pattern Recognition**: Users see their natural rhythms and trends  
3. **Motivation Amplification**: Visual progress is incredibly powerful
4. **Flexible Perspective**: Days/weeks/months suit different user needs
5. **Long-term Thinking**: Encourages sustainable coding habits

This transforms BigFoot from a streak tracker to a **COMPREHENSIVE CODING BEHAVIOR ANALYTICS PLATFORM**! 🚀
