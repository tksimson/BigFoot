"""Configuration management for BigFoot."""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class Config:
    """Configuration manager for BigFoot."""
    
    def __init__(self, config_path: str = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to config file. Defaults to config.yaml in current directory
        """
        if config_path is None:
            config_path = os.getenv('BIGFOOT_CONFIG_PATH', 'config.yaml')
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except (yaml.YAMLError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'settings': {
                'timezone': 'UTC',
                'daily_goal': 10,
                'show_progress': True,
                'color_output': True,
                'compact_mode': False
            }
        }
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
        except IOError as e:
            raise Exception(f"Could not save config file: {e}")
    
    
    def get_daily_goal(self) -> int:
        """Get daily commit goal."""
        return self.config.get('settings', {}).get('daily_goal', 10)
    
    def set_daily_goal(self, goal: int) -> None:
        """Set daily commit goal."""
        if 'settings' not in self.config:
            self.config['settings'] = {}
        self.config['settings']['daily_goal'] = goal
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.config.get('settings', {}).get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value."""
        if 'settings' not in self.config:
            self.config['settings'] = {}
        self.config['settings'][key] = value
    
    def is_configured(self) -> bool:
        """Check if BigFoot is properly configured."""
        # BigFoot is always configured for local tracking - no setup needed
        return True
