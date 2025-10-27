"""First-run configuration helper.

Detects if this is the first run and helps users create a .env file.
"""

from pathlib import Path
import os
import subprocess
import platform


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
    return Path(".env").exists()


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
        if response in ("", "y", "yes"):
            return True
        elif response in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'")


def open_file_in_editor(file_path: Path) -> bool:
    """Open file in the system's default text editor.

    Args:
        file_path: Path to file to open

    Returns:
        True if successful, False otherwise
    """
    try:
        system = platform.system()
        file_str = str(file_path.absolute())

        if system == "Windows":
            # Try os.startfile first (uses default association)
            try:
                os.startfile(file_str)
            except OSError:
                # Fallback to notepad if no default association
                subprocess.run(["notepad.exe", file_str], check=True)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", file_str], check=True)
        else:  # Linux and others
            subprocess.run(["xdg-open", file_str], check=True)

        return True
    except Exception as e:
        print(f"Warning: Could not open file in editor: {e}")
        return False


def create_env_file(open_in_editor: bool = False) -> bool:
    """Create .env template file.

    Args:
        open_in_editor: If True, open the file in default editor after creation

    Returns:
        True if successful, False otherwise
    """
    try:
        env_path = Path(".env")
        if env_path.exists():
            print("Warning: .env file already exists. Not overwriting.")
            return False

        env_path.write_text(get_env_template(), encoding="utf-8")
        print(f"\n✓ Created .env template at: {env_path.absolute()}")
        print("\nNext steps:")
        print("  1. Open .env in a text editor")
        print("  2. Replace 'your_spotify_client_id_here' with your actual Client ID")
        print("  3. Update PSM__LIBRARY__PATHS with your music folder paths")
        print("  4. Adjust other settings as needed")
        print("  5. Run this application again")
        print("\nFor detailed configuration help, see: docs/configuration.md")

        if open_in_editor:
            if open_file_in_editor(env_path):
                print(f"\n✓ Opened {env_path.name} in your default text editor")

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
        if create_env_file():
            # Ask if they want to open it now
            response = input("\nOpen .env in your default text editor now? [Y/n]: ").strip().lower()
            if response in ("", "y", "yes"):
                open_file_in_editor(Path(".env"))

        print("\nPlease configure your .env file and run the application again.")
        return False  # Exit so user can configure
    else:
        print("\nYou can create .env manually or run with environment variables.")
        print("Example environment variable:")
        print("  PSM__PROVIDERS__SPOTIFY__CLIENT_ID=your_client_id")
        print("\nFor more information, see: docs/configuration.md")

        # Ask if they want to continue anyway (might use env vars)
        response = input("\nContinue without .env file? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            return True
        return False


class FirstRunDialog:
    """Stateful dialog for first-run .env creation workflow.

    States:
        PROMPT: Initial state - offer to create .env template
        POST_CREATE: After successful creation - offer to open file
    """

    def __init__(self, parent=None):
        """Initialize the dialog.

        Args:
            parent: Parent widget for the dialog
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle("First Run - Configuration Needed")
        self.dialog.setMinimumWidth(500)

        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Message area (will be updated based on state)
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.title_label.setFont(font)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()

        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.error_label)

        # Button area
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.create_btn = QPushButton("Create Template")
        self.create_btn.clicked.connect(self._on_create_clicked)

        self.open_btn = QPushButton("Open File")
        self.open_btn.clicked.connect(self._on_open_file_clicked)
        self.open_btn.hide()  # Hidden in initial state

        self.continue_btn = QPushButton("Continue Anyway")
        self.continue_btn.clicked.connect(self._on_continue_clicked)

        self.exit_btn = QPushButton("Exit")
        self.exit_btn.clicked.connect(self._on_exit_clicked)

        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.continue_btn)
        button_layout.addWidget(self.exit_btn)

        layout.addLayout(button_layout)
        self.dialog.setLayout(layout)

        # Initialize to prompt state
        self._init_prompt_state()

        # Track whether file was created
        self.env_path = None

    def _init_prompt_state(self):
        """Configure dialog for initial prompt state."""
        self.title_label.setText("Welcome to Playlist Sync Matcher!")
        self.info_label.setText(
            "No .env configuration file found.\n\n"
            "You need to:\n"
            "  1. Get a Spotify Client ID from developer.spotify.com/dashboard\n"
            "  2. Configure your music library paths\n"
            "  3. Set other preferences (export format, matching settings, etc.)\n\n"
            "Would you like to create a template .env file now?"
        )
        self.error_label.hide()
        self.create_btn.show()
        self.create_btn.setEnabled(True)
        self.open_btn.hide()
        self.create_btn.setDefault(True)

    def _init_post_create_state(self):
        """Configure dialog for post-creation state."""
        self.title_label.setText("Configuration Template Created!")
        self.info_label.setText(
            f"Location: {self.env_path.absolute()}\n\n"
            "Please edit this file with:\n"
            "  • Your Spotify Client ID\n"
            "  • Your music library paths\n"
            "  • Other preferences as needed\n\n"
            "Then restart the application.\n\n"
            "For detailed configuration help, see: docs/configuration.md"
        )
        self.error_label.hide()
        self.create_btn.hide()
        self.open_btn.show()
        self.open_btn.setDefault(True)

    def _on_create_clicked(self):
        """Handle Create Template button click."""
        # Disable button to prevent double-clicks
        self.create_btn.setEnabled(False)
        self.error_label.hide()

        try:
            self.env_path = Path(".env")

            # Check if file already exists
            if self.env_path.exists():
                # Treat as success - file exists, user can now open it
                self._init_post_create_state()
                return

            # Create the file
            self.env_path.write_text(get_env_template(), encoding="utf-8")

            # Success - transition to post-create state
            self._init_post_create_state()

        except Exception as e:
            # Show error inline and remain in prompt state
            self.error_label.setText(f"Failed to create .env file: {e}")
            self.error_label.show()
            self.create_btn.setEnabled(True)

    def _on_open_file_clicked(self):
        """Handle Open File button click."""
        if self.env_path:
            open_file_in_editor(self.env_path)
        # Keep dialog open so user can click Continue or Exit

    def _on_continue_clicked(self):
        """Handle Continue Anyway button click."""
        self.dialog.accept()

    def _on_exit_clicked(self):
        """Handle Exit button click."""
        self.dialog.reject()

    def exec(self) -> bool:
        """Execute the dialog and return result.

        Returns:
            True if app should continue, False if it should exit
        """
        from PySide6.QtWidgets import QDialog

        result = self.dialog.exec()
        return result == QDialog.Accepted


def check_first_run_gui(parent_widget=None) -> bool:
    """Check if this is first run and handle .env creation (GUI mode).

    Args:
        parent_widget: Parent widget for dialog (if using Qt)

    Returns:
        True if app should continue, False if it should exit (needs config)
    """
    if check_env_exists():
        return True  # Config exists, continue normally

    # No .env found - show stateful dialog
    try:
        dialog = FirstRunDialog(parent_widget)
        return dialog.exec()
    except ImportError:
        # Fallback to CLI mode if Qt not available
        return check_first_run_cli()
