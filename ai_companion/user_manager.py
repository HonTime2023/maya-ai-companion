"""
User Manager: Handles user profiles, conversation history, and user-specific data.
Each user gets their own isolated state and conversation context.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

USERS_DIR = "users"
DEFAULT_USER = "default_user"


class UserProfile:
    """Represents a single user's profile and session state."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_dir = Path(USERS_DIR) / user_id
        self.user_dir.mkdir(parents=True, exist_ok=True)

        self.profile_file = self.user_dir / "profile.json"
        self.history_file = self.user_dir / "conversation_history.json"
        self.reminders_file = self.user_dir / "reminders.json"
        self.alarms_file = self.user_dir / "alarms.json"
        self.health_file = self.user_dir / "health_profile.json"

        self.data = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        """Load user profile from disk, create if not exists."""
        if self.profile_file.exists():
            with open(self.profile_file, "r") as f:
                return json.load(f)
        else:
            return self._create_default_profile()

    def _create_default_profile(self) -> Dict[str, Any]:
        """Create default profile for new user."""
        profile = {
            "user_id": self.user_id,
            "name": "User",  # Default name until they tell us
            "is_new_user": True,  # Track if user hasn't set their name yet
            "location": "Not set",  # User's location for weather, etc.
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "preferences": {
                "tts_voice": "nova",
                "tts_speed": 1.0,
                "use_wake_words": False,  # Make wake words optional
                "natural_mode": True,  # Default to natural conversation
            },
            "health": {
                "conditions": [],
                "medications": [],
                "stress_level": "normal",
                "sleep_hours_avg": 7,
                "allergies": [],
            },
        }
        # Write to disk directly without calling save_profile()
        with open(self.profile_file, "w") as f:
            json.dump(profile, f, indent=2)
        return profile

    def save_profile(self):
        """Save profile to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.profile_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def update_name(self, name: str):
        """Update user's display name and mark as no longer new."""
        self.data["name"] = name
        self.data["is_new_user"] = False  # Mark as having introduced themselves
        self.save_profile()

    def get_name(self) -> str:
        """Get user's display name."""
        return self.data.get("name", self.user_id)

    def update_preferences(self, prefs: Dict):
        """Update user preferences."""
        self.data["preferences"].update(prefs)
        self.save_profile()

    def set_location(self, location: str):
        """Set user's location (for weather, etc.)."""
        self.data["location"] = location
        self.save_profile()

    def get_conversation_history(self) -> List[Dict]:
        """Load conversation history for this user."""
        if self.history_file.exists():
            with open(self.history_file, "r") as f:
                return json.load(f)
        return []

    def save_conversation_history(self, history: List[Dict]):
        """Save conversation history for this user."""
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def get_reminders(self) -> List[Dict]:
        """Get user's reminders."""
        if self.reminders_file.exists():
            with open(self.reminders_file, "r") as f:
                return json.load(f)
        return []

    def add_reminder(self, reminder: Dict):
        """Add a new reminder."""
        reminders = self.get_reminders()
        reminders.append(reminder)
        self.save_reminders(reminders)

    def save_reminders(self, reminders: List[Dict]):
        """Save user's reminders."""
        with open(self.reminders_file, "w") as f:
            json.dump(reminders, f, indent=2)

    def get_alarms(self) -> List[Dict]:
        """Get user's alarms."""
        if self.alarms_file.exists():
            with open(self.alarms_file, "r") as f:
                return json.load(f)
        return []

    def add_alarm(self, alarm: Dict):
        """Add a new alarm."""
        alarms = self.get_alarms()
        alarms.append(alarm)
        self.save_alarms(alarms)

    def save_alarms(self, alarms: List[Dict]):
        """Save user's alarms."""
        with open(self.alarms_file, "w") as f:
            json.dump(alarms, f, indent=2)

    def get_health_profile(self) -> Dict:
        """Get user's health profile."""
        if self.health_file.exists():
            with open(self.health_file, "r") as f:
                return json.load(f)
        return self.data.get("health", {})

    def save_health_profile(self, health: Dict):
        """Save user's health profile."""
        with open(self.health_file, "w") as f:
            json.dump(health, f, indent=2)


class UserManager:
    """Global user management - handles current user session and user switching."""

    def __init__(self):
        Path(USERS_DIR).mkdir(exist_ok=True)
        self.current_user: Optional[UserProfile] = None
        self._load_or_create_default_user()

    def _load_or_create_default_user(self):
        """Load default user or create if not exists."""
        if not (Path(USERS_DIR) / DEFAULT_USER).exists():
            self.current_user = UserProfile(DEFAULT_USER)
            # Will prompt for name on first run
        else:
            self.current_user = UserProfile(DEFAULT_USER)

    def set_current_user(self, user_id: str):
        """Switch to a different user."""
        self.current_user = UserProfile(user_id)

    def get_current_user(self) -> UserProfile:
        """Get currently active user profile."""
        if self.current_user is None:
            self._load_or_create_default_user()
        return self.current_user

    def list_users(self) -> List[str]:
        """List all existing users."""
        if not Path(USERS_DIR).exists():
            return []
        return [d.name for d in Path(USERS_DIR).iterdir() if d.is_dir()]

    def create_user(self, user_id: str, name: Optional[str] = None) -> UserProfile:
        """Create a new user."""
        user = UserProfile(user_id)
        if name:
            user.update_name(name)
        return user


# Global instance
user_manager = UserManager()


def get_current_user() -> UserProfile:
    """Convenience function to get current user."""
    return user_manager.get_current_user()


def get_current_user_name() -> str:
    """Get current user's name."""
    return user_manager.get_current_user().get_name()
