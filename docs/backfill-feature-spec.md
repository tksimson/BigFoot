# BigFoot Historical Backfill Feature Specification

## 🎯 **Feature Overview**

Add a new command `bigfoot backfill` that scans historical git commits and populates the database with past activity data, enabling users to see complete historical progress and streaks.

---

## 🖥️ **Command Interface**

### **Primary Command**
```bash
bigfoot backfill --days <number>
```

### **Full Command Options**
```bash
bigfoot backfill [OPTIONS]

Options:
  --days INTEGER          Number of days to go back (required)
  --search-paths TEXT     Comma-separated paths to search for repositories
  --dry-run              Show what would be processed without saving to database
  --force                Force overwrite existing data (default: skip duplicates)
  --batch-size INTEGER   Process repositories in batches (default: 10)
  --quiet                Suppress progress output
  --help                 Show this message and exit
```

### **Usage Examples**
```bash
# Backfill last 30 days
bigfoot backfill --days 30

# Backfill with custom search paths
bigfoot backfill --days 60 --search-paths "/home/user/work,/home/user/personal"

# Dry run to see what would be processed
bigfoot backfill --days 7 --dry-run

# Force overwrite existing data
bigfoot backfill --days 14 --force

# Quiet mode for scripting
bigfoot backfill --days 30 --quiet
```

---

## 🔧 **Technical Implementation Specification**

### **Core Algorithm**
1. **Date Range Calculation**: Generate list of dates from today backwards for N days
2. **Repository Discovery**: Use existing `find_git_repositories()` method
3. **Sequential Processing**: Process each date sequentially (oldest to newest)
4. **Batch Processing**: Process repositories in configurable batches
5. **Duplicate Handling**: Leverage existing `UNIQUE(repo, date)` constraint
6. **Progress Reporting**: Real-time progress updates with Rich

### **New Method: `LocalGitTracker.backfill_history()`**
```python
def backfill_history(self, days: int, search_paths: List[str] = None, 
                    dry_run: bool = False, force: bool = False,
                    batch_size: int = 10, quiet: bool = False) -> Dict:
    """
    Backfill historical git commit data.
    
    Args:
        days: Number of days to go back from today
        search_paths: Custom repository search paths
        dry_run: Preview mode without database writes
        force: Overwrite existing data
        batch_size: Number of repos to process simultaneously  
        quiet: Suppress progress output
        
    Returns:
        Dictionary with backfill results and statistics
    """
```

---

## 🛡️ **Duplicate Prevention Strategy**

### **Database Level Protection**
- ✅ **Existing**: `UNIQUE(repo, date)` constraint prevents DB-level duplicates
- ✅ **Existing**: `INSERT OR REPLACE INTO` handles conflicts gracefully
- ✅ **Default Behavior**: Skip existing entries unless `--force` specified

### **Application Level Logic**
```python
# Check existing data before processing (optional optimization)
existing_dates = database.get_existing_dates_for_repo(repo_name)
dates_to_process = [d for d in date_range if d not in existing_dates or force]
```

### **Force Mode Behavior**
- `--force` flag recalculates and overwrites existing entries
- Useful for correcting historical data or after repository changes
- Warns user about potential data overwrite

---

## ⚠️ **Error Handling & Edge Cases**

### **Repository Access Errors**
```python
# Handle repositories that may have been moved/deleted
try:
    commits = self.get_commits_for_date(repo_path, date, user_emails)
except subprocess.SubprocessError as e:
    if not quiet:
        console.print(f"⚠️  {repo_path}: {e}")
    continue  # Skip this repo, don't fail entire operation
```

### **Git History Issues**
- **Shallow Clones**: Warn if repository has limited history
- **Missing History**: Handle repos with commits older than request range
- **Corrupted History**: Skip individual problematic dates/repos
- **Empty Repositories**: Handle repos with no commits gracefully

### **Performance & Resource Management**
- **Large Repositories**: Progress tracking for repos with many commits
- **Memory Management**: Process in batches to avoid memory issues
- **Network Dependencies**: Pure local operation, no network required
- **Disk Space**: Monitor database growth, warn on large operations

### **Date Range Validation**
```python
def validate_date_range(days: int) -> Tuple[bool, str]:
    """Validate backfill date range parameters."""
    if days < 1:
        return False, "Days must be positive"
    if days > 365:
        return False, "Maximum 365 days supported (use multiple runs for more)"
    return True, ""
```

### **Database Integrity**
- **Transaction Management**: Use database transactions for batch operations
- **Rollback Capability**: Ability to rollback failed operations
- **Backup Recommendation**: Suggest database backup for large operations
- **Corruption Detection**: Verify database integrity after large operations

---

## 🎨 **User Experience Design**

### **Progress Display**
```bash
🔄 BigFoot Historical Backfill

📊 Configuration:
  • Date range: 2025-08-20 to 2025-09-19 (30 days)
  • Repositories: 14 found
  • Mode: Normal (use --dry-run to preview)

🔍 Processing historical commits...

┌─ Progress ──────────────────────────────────────────┐
│ Day 15/30: 2025-09-04                               │
│ Repos: ████████████████████░░░░░░ 12/14 (86%)      │
│ ├─ BigFoot: ✅ 3 commits found                      │
│ ├─ FireSoul: ✅ 1 commit found                      │
│ └─ OldProject: ⚠️  Repository moved or deleted      │
└─────────────────────────────────────────────────────┘

📈 Results Summary:
  • 450 commits processed across 30 days
  • 12 repositories with activity found
  • 2 repositories skipped (access issues)
  • 45 database entries created
  • 5 existing entries skipped
```

### **Dry Run Output**
```bash
🔍 DRY RUN: Historical Backfill Preview

📊 Would process:
  • Date range: 30 days (2025-08-20 to 2025-09-19)  
  • Repositories: 14 found
  • Expected commits: ~450 (estimated)
  • New database entries: ~45 (estimated)
  • Existing entries to skip: 5

⚡ Run with --force to overwrite existing entries
🚀 Remove --dry-run to execute backfill
```

### **Error Reporting**
```bash
⚠️  Warning Summary:
  • 2 repositories could not be accessed
  • 1 repository has shallow clone (limited history)
  • 3 days had no commits found

❌ Critical Errors: None
✅ Backfill completed successfully
```

---

## 🚀 **Performance Considerations**

### **Optimization Strategies**
- **Batch Processing**: Configurable batch sizes for large repository sets
- **Date Ordering**: Process oldest dates first for logical consistency
- **Early Termination**: Option to stop on first error vs. continue
- **Memory Efficient**: Stream processing instead of loading all data

### **Expected Performance**
- **Small Operations** (7 days, 5 repos): ~5-10 seconds
- **Medium Operations** (30 days, 15 repos): ~30-60 seconds  
- **Large Operations** (90 days, 50 repos): ~2-5 minutes

### **Performance Monitoring**
```python
# Add timing and statistics to backfill results
return {
    'processed_days': len(date_range),
    'processed_repos': len(successful_repos),
    'total_commits': total_commits,
    'database_entries': entries_created,
    'duration_seconds': time.time() - start_time,
    'errors': error_list,
    'warnings': warning_list
}
```

---

## 🧪 **Testing Strategy**

### **Unit Tests**
- Date range generation and validation
- Repository filtering and deduplication
- Error handling for missing/corrupted repos
- Database transaction and rollback behavior

### **Integration Tests**  
- Full backfill workflow with test repositories
- Dry-run vs. actual execution consistency
- Force mode behavior and data overwriting
- Progress reporting accuracy

### **Edge Case Tests**
- Empty repositories and date ranges
- Maximum day limits and validation
- Database corruption recovery
- Batch size edge cases (1, very large numbers)

---

## 📝 **Configuration & Defaults**

### **Default Values**
```python
DEFAULT_BATCH_SIZE = 10
MAX_DAYS_ALLOWED = 365
DEFAULT_SEARCH_PATHS = None  # Use standard search paths
PROGRESS_UPDATE_INTERVAL = 1  # Update progress every N repos
```

### **User Configuration**
```yaml
# config.yaml additions
backfill:
  default_batch_size: 10
  max_days_limit: 365
  show_progress: true
  auto_backup: false  # Future: auto-backup before large operations
```

---

## 🔮 **Future Enhancements**

### **Phase 2 Features**
- **Smart Date Detection**: Auto-detect optimal backfill range based on existing data gaps
- **Incremental Updates**: Only backfill missing dates between existing entries
- **Repository Filtering**: Include/exclude specific repositories
- **Export Functionality**: Export backfilled data to CSV/JSON
- **Undo Capability**: Reverse backfill operations

### **Advanced Options**
```bash
# Future command extensions
bigfoot backfill --auto-detect     # Smart date range detection
bigfoot backfill --fill-gaps       # Only fill missing dates
bigfoot backfill --repos="repo1,repo2"  # Specific repositories
bigfoot backfill --export-csv      # Export results to CSV
```

---

## ✅ **Implementation Checklist**

### **Core Implementation**
- [ ] Add `backfill` command to CLI in `main.py`
- [ ] Implement `backfill_history()` method in `LocalGitTracker`
- [ ] Add date range generation utility functions
- [ ] Implement batch processing logic
- [ ] Add progress reporting with Rich

### **Error Handling**
- [ ] Repository access error handling
- [ ] Git history validation and warnings
- [ ] Database transaction management
- [ ] Input validation and sanitization

### **User Experience**
- [ ] Progress bars and real-time updates
- [ ] Dry-run functionality
- [ ] Comprehensive error/warning reporting
- [ ] Help documentation and examples

### **Testing & Documentation**
- [ ] Unit tests for core logic
- [ ] Integration tests for full workflow
- [ ] Update README with backfill examples
- [ ] Add command documentation

---

## 📋 **Implementation Notes**

### **Database Considerations**
- The existing `commits` table has `UNIQUE(repo, date)` constraint which perfectly supports our duplicate prevention needs
- `INSERT OR REPLACE INTO` will handle conflicts automatically
- The `collected_at` timestamp will track when data was backfilled vs. originally tracked

### **Code Integration Points**
- **Main CLI**: Add new `@cli.command()` in `bigfoot/main.py`
- **Core Logic**: Extend `LocalGitTracker` class in `bigfoot/local_tracker.py`
- **Database**: May need helper methods in `Database` class for optimization
- **Utils**: Date range utilities in `bigfoot/utils.py`

### **Dependencies**
- No new external dependencies required
- Leverages existing Rich, Click, and sqlite3 libraries
- Uses existing git subprocess calls

---

**This specification provides a comprehensive roadmap for implementing the historical backfill feature with proper error handling, performance optimization, and excellent user experience.** 🎯
