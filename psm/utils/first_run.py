"""First-run configuration helper.

Detects if this is the first run and helps users create a .env file.
"""
from pathlib import Path
import sys


def get_env_template() -> str:
    """Return a template .env file with comments."""
    return """# Playlist Sync Matcher Configuration
# See docs/configuration.md for full reference

# === REQUIRED: Spotify API Credentials ===
# Get your Client ID from: https://developer.spotify.com/dashboard
PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_spotify_client_id_here

# === Library Settings ===
# Paths to your music library (JSON array format)
# Windows example: PSM__LIBRARY__PATHS=["C:/Music", "D:/Archive"]
# Linux example: PSM__LIBRARY__PATHS=["/home/user/Music"]
PSM__LIBRARY__PATHS=["music"]

# File extensions to scan
PSM__LIBRARY__EXTENSIONS=[".mp3", ".flac", ".m4a", ".ogg"]

# === Export Settings ===
# Where to save M3U playlists
PSM__EXPORT__DIRECTORY=data/export/playlists

# Export mode: strict (matched only) | mirrored (all) | placeholders (with .missing files)
PSM__EXPORT__MODE=strict

# Path format in M3U files: absolute or relative
PSM__EXPORT__PATH_FORMAT=absolute

# Organize playlists by owner username
PSM__EXPORT__ORGANIZE_BY_OWNER=false

# Include "Liked Songs" as a virtual playlist
PSM__EXPORT__INCLUDE_LIKED_SONGS=true

# === Matching Settings ===
# Fuzzy match threshold (0.0 to 1.0, higher = stricter)
PSM__MATCHING__FUZZY_THRESHOLD=0.78

# Duration tolerance in seconds
PSM__MATCHING__DURATION_TOLERANCE=5.0

# === Database Settings ===
PSM__DATABASE__PATH=data/db/spotify_sync.db

# === Logging ===
PSM__LOG_LEVEL=INFO
"""


def check_env_exists() -> bool:
    """Check if .env file exists in current directory."""
    return Path('.env').exists()


def prompt_create_env() -> bool:
    """Prompt user to create .env file (CLI mode).
    
    Returns:
        True if user wants to create .env, False otherwise
    """
    print("\n" + "=" * 70)
    print("  Welcome to Playlist Sync Matcher!")
    print("=" * 70)
    print("\nNo .env configuration file found in the current directory.")
    print("\nTo use this application, you need to:")
    print("  1. Get a Spotify Client ID from https://developer.spotify.com/dashboard")
    print("  2. Configure your music library paths")
    print("  3. Set other preferences (export format, matching settings, etc.)")
    print("\nWould you like to create a template .env file now?")
    print("(You'll need to edit it with your Spotify credentials)")
    print()
    
    while True:
        response = input("Create .env template? [Y/n]: ").strip().lower()
        if response in ('', 'y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'")


def create_env_file() -> bool:
    """Create .env template file.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        env_path = Path('.env')
        if env_path.exists():
            print("Warning: .env file already exists. Not overwriting.")
            return False
        
        env_path.write_text(get_env_template(), encoding='utf-8')
        print(f"\n✓ Created .env template at: {env_path.absolute()}")
        print("\nNext steps:")
        print("  1. Open .env in a text editor")
        print("  2. Replace 'your_spotify_client_id_here' with your actual Client ID")
        print("  3. Update PSM__LIBRARY__PATHS with your music folder paths")
        print("  4. Adjust other settings as needed")
        print("  5. Run this application again")
        print("\nFor detailed configuration help, see: docs/configuration.md")
        return True
    except Exception as e:
        print(f"\n✗ Failed to create .env file: {e}")
        return False


def check_first_run_cli() -> bool:
    """Check if this is first run and handle .env creation (CLI mode).
    
    Returns:
        True if app should continue, False if it should exit (needs config)
    """
    if check_env_exists():
        return True  # Config exists, continue normally
    
    # No .env found - offer to create one
    if prompt_create_env():
        create_env_file()
        print("\nPlease configure your .env file and run the application again.")
        return False  # Exit so user can configure
    else:
        print("\nYou can create .env manually or run with environment variables.")
        print("Example environment variable:")
        print("  PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id")
        print("\nFor more information, see: docs/configuration.md")
        
        # Ask if they want to continue anyway (might use env vars)
        response = input("\nContinue without .env file? [y/N]: ").strip().lower()
        if response in ('y', 'yes'):
            return True
        return False


def check_first_run_gui(parent_widget=None) -> bool:
    """Check if this is first run and handle .env creation (GUI mode).
    
    Args:
        parent_widget: Parent widget for dialog (if using Qt)
    
    Returns:
        True if app should continue, False if it should exit (needs config)
    """
    if check_env_exists():
        return True  # Config exists, continue normally
    
    # No .env found - show dialog
    try:
        from PySide6.QtWidgets import QMessageBox, QPushButton
        
        msg = QMessageBox(parent_widget)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("First Run - Configuration Needed")
        msg.setText("Welcome to Playlist Sync Matcher!")
        msg.setInformativeText(
            "No .env configuration file found.\n\n"
            "You need to:\n"
            "1. Get a Spotify Client ID from developer.spotify.com\n"
            "2. Configure your music library paths\n\n"
            "Would you like to create a template .env file now?"
        )
        
        create_btn = msg.addButton("Create Template", QMessageBox.AcceptRole)
        continue_btn = msg.addButton("Continue Anyway", QMessageBox.RejectRole)
        exit_btn = msg.addButton("Exit", QMessageBox.RejectRole)
        msg.setDefaultButton(create_btn)
        
        msg.exec()
        clicked = msg.clickedButton()
        
        if clicked == create_btn:
            if create_env_file():
                info = QMessageBox(parent_widget)
                info.setIcon(QMessageBox.Information)
                info.setWindowTitle("Configuration Template Created")
                info.setText("Template .env file created successfully!")
                info.setInformativeText(
                    f"Location: {Path('.env').absolute()}\n\n"
                    "Please edit this file with:\n"
                    "- Your Spotify Client ID\n"
                    "- Your music library paths\n\n"
                    "Then restart the application."
                )
                info.exec()
            return False  # Exit so user can configure
        elif clicked == continue_btn:
            return True  # User wants to try with env vars
        else:  # exit_btn
            return False
    except ImportError:
        # Fallback to CLI mode if Qt not available
        return check_first_run_cli()
