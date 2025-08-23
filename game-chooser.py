#!/usr/bin/env python3
"""
Game Chooser - A desktop application for organizing and launching games
Built with wxPython for cross-platform compatibility
"""

import wx
import wx.lib.mixins.listctrl as listmix
import json
import os
import sys
import subprocess
import platform
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import stat

class Game:
    """Represents a game in the library"""
    def __init__(self, title="", genre="", developer="", year="unknown", 
                 platforms=None, launch_path=""):
        self.title = title
        self.genre = genre
        self.developer = developer
        self.year = year
        self.platforms = platforms or []
        self.launch_path = launch_path
    
    def to_dict(self):
        return {
            "title": self.title,
            "genre": self.genre,
            "developer": self.developer,
            "year": self.year,
            "platforms": self.platforms,
            "launch_path": self.launch_path
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            title=data.get("title", ""),
            genre=data.get("genre", ""),
            developer=data.get("developer", ""),
            year=data.get("year", "unknown"),
            platforms=data.get("platforms", []),
            launch_path=data.get("launch_path", "")
        )

class GameLibraryManager:
    """Handles all game library operations and data management"""
    
    def __init__(self):
        self.games = []
        self.config = {}
        self.app_dir = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
        self.games_file = self.app_dir / "games.json"
        self.config_file = self.get_config_path()
        self.load_config()
        self.load_games()
    
    def get_config_path(self):
        """Get platform-specific config path"""
        system = platform.system()
        if system == "Windows":
            app_data = Path(os.environ.get('APPDATA', ''))
            config_dir = app_data / "GameChooser"
        elif system == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "GameChooser"
        else:  # Linux/Unix
            config_dir = Path.home() / ".config" / "GameChooser"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"
    
    def load_config(self):
        """Load configuration from JSON file"""
        default_config = {
            "libraries": [],
            "exceptions": [],
            "SavedState": {
                "window_size": None,
                "window_position": None,
                "splitter_position": None,
                "sort_column": 0,
                "sort_ascending": True,
                "last_selected": None,
                "last_search": "",
                "column_widths": None,
                "tree_expansion": {}
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for key in default_config:
                        if key not in loaded:
                            loaded[key] = default_config[key]
                    if "SavedState" in loaded:
                        for state_key in default_config["SavedState"]:
                            if state_key not in loaded["SavedState"]:
                                loaded["SavedState"][state_key] = default_config["SavedState"][state_key]
                    self.config = loaded
            except:
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def load_games(self):
        """Load games from JSON file"""
        if self.games_file.exists():
            try:
                with open(self.games_file, 'r') as f:
                    data = json.load(f)
                    self.games = [Game.from_dict(g) for g in data]
            except:
                self.games = []
        else:
            self.games = []
    
    def save_games(self):
        """Save games to JSON file"""
        with open(self.games_file, 'w') as f:
            json.dump([g.to_dict() for g in self.games], f, indent=2)
    
    def get_library_by_name(self, name):
        """Get library path by name"""
        for lib in self.config["libraries"]:
            if lib["name"] == name:
                return lib["path"]
        return None
    
    def get_full_path(self, game):
        """Construct full path from relative path and library"""
        if game.launch_path.startswith("http"):
            return game.launch_path
        
        parts = Path(game.launch_path).parts
        if not parts:
            return None
        
        lib_name = parts[0]
        for lib in self.config["libraries"]:
            if lib["name"] == lib_name:
                full_path = Path(lib["path"]) / Path(*parts[1:])
                return str(full_path)
        
        return None
    
    def is_executable(self, path):
        """Check if file is an executable based on platform and extension"""
        path_obj = Path(path)
        system = platform.system()
        
        if system == "Windows":
            return path_obj.suffix.lower() in ['.exe', '.bat']
        elif system == "Darwin":  # macOS
            # Check if it's executable
            try:
                return os.access(path, os.X_OK) and path_obj.is_file()
            except:
                return False
        
        return False
    
    def is_valid_game_executable(self, path):
        """Check if executable matches valid game patterns"""
        name = Path(path).stem.lower()
        parent_name = Path(path).parent.name.lower()
        
        valid_names = ["game", "launch", "play", parent_name]
        return name in valid_names
    
    def scan_library(self, library_path, library_name, max_depth=10):
        """Recursively scan a library path for games"""
        found_games = []
        new_exceptions = []
        
        def scan_recursive(path, depth=0):
            if depth > max_depth:
                return
            
            try:
                for item in Path(path).iterdir():
                    # Skip hidden/system files and symlinks
                    if item.name.startswith('.'):
                        continue
                    if item.is_symlink():
                        continue
                    
                    if item.is_file() and self.is_executable(str(item)):
                        # Build relative path
                        rel_path = item.relative_to(Path(library_path).parent)
                        rel_str = str(rel_path).replace(os.sep, '\\')
                        
                        # Check if in exceptions
                        if rel_str in self.config["exceptions"]:
                            continue
                        
                        # Check if valid game executable
                        if not self.is_valid_game_executable(str(item)):
                            new_exceptions.append(rel_str)
                            continue
                        
                        # Create game entry
                        title = item.parent.name
                        system = platform.system()
                        plat = "Windows" if system == "Windows" else "macOS"
                        
                        # Check if game already exists
                        existing = None
                        for g in found_games:
                            if g.launch_path == rel_str:
                                existing = g
                                break
                        
                        if existing:
                            if plat not in existing.platforms:
                                existing.platforms.append(plat)
                        else:
                            game = Game(
                                title=title,
                                platforms=[plat],
                                launch_path=rel_str
                            )
                            found_games.append(game)
                    
                    elif item.is_dir():
                        scan_recursive(item, depth + 1)
            
            except PermissionError:
                # Handle permission errors
                raise PermissionError(f"Permission denied: {path}")
        
        scan_recursive(library_path)
        return found_games, new_exceptions
    
    def validate_and_scan_all(self):
        """Validate existing games and scan for new ones"""
        validated_games = []
        all_new_exceptions = []
        
        # First, validate existing games
        for game in self.games:
            if game.launch_path.startswith("http"):
                validated_games.append(game)
                continue
            
            full_path = self.get_full_path(game)
            if full_path and Path(full_path).exists():
                validated_games.append(game)
        
        # Then scan all libraries for new games
        for lib in self.config["libraries"]:
            try:
                new_games, new_exceptions = self.scan_library(
                    lib["path"], lib["name"]
                )
                
                # Add new exceptions
                for exc in new_exceptions:
                    if exc not in self.config["exceptions"]:
                        self.config["exceptions"].append(exc)
                        all_new_exceptions.append(exc)
                
                # Merge new games
                for new_game in new_games:
                    existing = None
                    for val_game in validated_games:
                        if val_game.launch_path == new_game.launch_path:
                            existing = val_game
                            break
                    
                    if existing:
                        # Update platforms if needed
                        for plat in new_game.platforms:
                            if plat not in existing.platforms:
                                existing.platforms.append(plat)
                    else:
                        validated_games.append(new_game)
            
            except PermissionError as e:
                # Will be handled by caller
                raise e
        
        self.games = validated_games
        self.save_games()
        self.save_config()
        
        return len(all_new_exceptions)

class EditGameDialog(wx.Dialog):
    """Dialog for editing game information"""
    
    def __init__(self, parent, game, library_manager, is_web=False):
        title = "Edit Web Game" if is_web else "Edit Game"
        super().__init__(parent, title=title, size=(400, 300))
        
        self.game = game
        self.library_manager = library_manager
        self.is_web = is_web
        
        # Get existing genres and developers for combo boxes
        genres = sorted(set(g.genre for g in library_manager.games if g.genre))
        developers = sorted(set(g.developer for g in library_manager.games if g.developer))
        
        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(5, 5)
        
        # Title
        sizer.Add(wx.StaticText(panel, label="Title:"), 
                 pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.title_ctrl = wx.TextCtrl(panel, value=game.title)
        sizer.Add(self.title_ctrl, pos=(0, 1), flag=wx.EXPAND)
        
        # URL or Platform (read-only)
        if is_web:
            sizer.Add(wx.StaticText(panel, label="URL:"), 
                     pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL)
            self.url_ctrl = wx.TextCtrl(panel, value=game.launch_path)
            sizer.Add(self.url_ctrl, pos=(1, 1), flag=wx.EXPAND)
        
        sizer.Add(wx.StaticText(panel, label="Platform:"), 
                 pos=(2, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        platform_text = "Web" if is_web else ", ".join(game.platforms)
        self.platform_ctrl = wx.TextCtrl(panel, value=platform_text, 
                                        style=wx.TE_READONLY)
        sizer.Add(self.platform_ctrl, pos=(2, 1), flag=wx.EXPAND)
        
        # Genre
        sizer.Add(wx.StaticText(panel, label="Genre:"), 
                 pos=(3, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.genre_ctrl = wx.ComboBox(panel, value=game.genre, choices=genres)
        sizer.Add(self.genre_ctrl, pos=(3, 1), flag=wx.EXPAND)
        
        # Developer
        sizer.Add(wx.StaticText(panel, label="Developer:"), 
                 pos=(4, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.developer_ctrl = wx.ComboBox(panel, value=game.developer, 
                                         choices=developers)
        sizer.Add(self.developer_ctrl, pos=(4, 1), flag=wx.EXPAND)
        
        # Year
        sizer.Add(wx.StaticText(panel, label="Year:"), 
                 pos=(5, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        year_val = 2000 if game.year == "unknown" else int(game.year)
        self.year_ctrl = wx.SpinCtrl(panel, value=str(year_val), 
                                    min=1000, max=9999, initial=year_val)
        sizer.Add(self.year_ctrl, pos=(5, 1), flag=wx.EXPAND)
        
        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        
        sizer.Add(btn_sizer, pos=(6, 0), span=(1, 2), 
                 flag=wx.ALIGN_CENTER | wx.TOP, border=10)
        
        sizer.AddGrowableCol(1)
        panel.SetSizer(sizer)
        
        # Validation
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
    
    def on_ok(self, event):
        """Validate and save changes"""
        if not self.title_ctrl.GetValue().strip():
            wx.MessageBox("Title is required", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if self.is_web:
            url = self.url_ctrl.GetValue().strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                wx.MessageBox("URL must start with http:// or https://", 
                            "Error", wx.OK | wx.ICON_ERROR)
                return
            self.game.launch_path = url
            self.game.platforms = ["Web"]
        
        self.game.title = self.title_ctrl.GetValue().strip()
        self.game.genre = self.genre_ctrl.GetValue().strip()
        self.game.developer = self.developer_ctrl.GetValue().strip()
        
        year_val = self.year_ctrl.GetValue()
        self.game.year = str(year_val) if year_val != 2000 else "unknown"
        
        self.EndModal(wx.ID_OK)

class PreferencesDialog(wx.Dialog):
    """Preferences dialog with dual-panel layout"""
    
    def __init__(self, parent, library_manager):
        super().__init__(parent, title="Preferences", size=(700, 500))
        
        self.library_manager = library_manager
        
        # Create main splitter
        splitter = wx.SplitterWindow(self)
        
        # Left panel - navigation
        left_panel = wx.Panel(splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.nav_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.nav_list.AppendColumn("Settings", width=150)
        self.nav_list.InsertItem(0, "Path Management")
        self.nav_list.Select(0)
        
        left_sizer.Add(self.nav_list, 1, wx.EXPAND | wx.ALL, 5)
        left_panel.SetSizer(left_sizer)
        
        # Right panel - content
        self.right_panel = wx.Panel(splitter)
        self.right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Path Management content
        self.create_path_management()
        
        self.right_panel.SetSizer(self.right_sizer)
        
        # Set up splitter
        splitter.SplitVertically(left_panel, self.right_panel, 200)
        splitter.SetMinimumPaneSize(150)
        
        # Main sizer with buttons
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(splitter, 1, wx.EXPAND)
        
        # Buttons
        btn_panel = wx.Panel(self)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        
        ok_btn = wx.Button(btn_panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(btn_panel, wx.ID_CANCEL, "Cancel")
        apply_btn = wx.Button(btn_panel, wx.ID_APPLY, "Apply")
        
        btn_sizer.Add(ok_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(cancel_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(apply_btn, 0, wx.RIGHT, 5)
        
        btn_panel.SetSizer(btn_sizer)
        main_sizer.Add(btn_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
        # Bind events
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        apply_btn.Bind(wx.EVT_BUTTON, self.on_apply)
        
        # Store original config for cancel
        self.original_config = json.loads(json.dumps(library_manager.config))
    
    def create_path_management(self):
        """Create path management panel"""
        # Library paths section
        lib_label = wx.StaticText(self.right_panel, label="Game Library Paths:")
        self.right_sizer.Add(lib_label, 0, wx.ALL, 5)
        
        lib_panel = wx.Panel(self.right_panel)
        lib_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.lib_list = wx.ListCtrl(lib_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.lib_list.AppendColumn("Name", width=100)
        self.lib_list.AppendColumn("Path", width=300)
        
        # Populate library list
        for lib in self.library_manager.config["libraries"]:
            index = self.lib_list.InsertItem(self.lib_list.GetItemCount(), lib["name"])
            self.lib_list.SetItem(index, 1, lib["path"])
        
        lib_sizer.Add(self.lib_list, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Library buttons
        lib_btn_panel = wx.Panel(lib_panel)
        lib_btn_sizer = wx.BoxSizer(wx.VERTICAL)
        
        add_lib_btn = wx.Button(lib_btn_panel, label="Add")
        remove_lib_btn = wx.Button(lib_btn_panel, label="Remove")
        
        lib_btn_sizer.Add(add_lib_btn, 0, wx.EXPAND | wx.BOTTOM, 5)
        lib_btn_sizer.Add(remove_lib_btn, 0, wx.EXPAND)
        
        lib_btn_panel.SetSizer(lib_btn_sizer)
        lib_sizer.Add(lib_btn_panel, 0, wx.ALIGN_TOP)
        
        lib_panel.SetSizer(lib_sizer)
        self.right_sizer.Add(lib_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Exceptions section
        exc_label = wx.StaticText(self.right_panel, label="Excluded Executables:")
        self.right_sizer.Add(exc_label, 0, wx.ALL, 5)
        
        exc_panel = wx.Panel(self.right_panel)
        exc_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.exc_list = wx.ListCtrl(exc_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.exc_list.AppendColumn("Path", width=400)
        
        # Populate exceptions list
        for exc in self.library_manager.config["exceptions"]:
            self.exc_list.InsertItem(self.exc_list.GetItemCount(), exc)
        
        exc_sizer.Add(self.exc_list, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Exception buttons
        exc_btn_panel = wx.Panel(exc_panel)
        exc_btn_sizer = wx.BoxSizer(wx.VERTICAL)
        
        add_exc_btn = wx.Button(exc_btn_panel, label="Add")
        remove_exc_btn = wx.Button(exc_btn_panel, label="Remove")
        
        exc_btn_sizer.Add(add_exc_btn, 0, wx.EXPAND | wx.BOTTOM, 5)
        exc_btn_sizer.Add(remove_exc_btn, 0, wx.EXPAND)
        
        exc_btn_panel.SetSizer(exc_btn_sizer)
        exc_sizer.Add(exc_btn_panel, 0, wx.ALIGN_TOP)
        
        exc_panel.SetSizer(exc_sizer)
        self.right_sizer.Add(exc_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Bind events
        add_lib_btn.Bind(wx.EVT_BUTTON, self.on_add_library)
        remove_lib_btn.Bind(wx.EVT_BUTTON, self.on_remove_library)
        add_exc_btn.Bind(wx.EVT_BUTTON, self.on_add_exception)
        remove_exc_btn.Bind(wx.EVT_BUTTON, self.on_remove_exception)
    
    def on_add_library(self, event):
        """Add a new library path"""
        dlg = wx.DirDialog(self, "Choose Game Library Directory")
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            name = os.path.basename(path)
            
            # Add to list control
            index = self.lib_list.InsertItem(self.lib_list.GetItemCount(), name)
            self.lib_list.SetItem(index, 1, path)
            
            # Add to config
            self.library_manager.config["libraries"].append({
                "name": name,
                "path": path
            })
        dlg.Destroy()
    
    def on_remove_library(self, event):
        """Remove selected library path"""
        selected = self.lib_list.GetFirstSelected()
        if selected >= 0:
            # Remove from config
            del self.library_manager.config["libraries"][selected]
            # Remove from list
            self.lib_list.DeleteItem(selected)
    
    def on_add_exception(self, event):
        """Add a new exception"""
        dlg = wx.TextEntryDialog(self, "Enter exception path (e.g., games\\tool\\updater.exe):", 
                                "Add Exception")
        if dlg.ShowModal() == wx.ID_OK:
            exc_path = dlg.GetValue()
            if exc_path:
                self.exc_list.InsertItem(self.exc_list.GetItemCount(), exc_path)
                self.library_manager.config["exceptions"].append(exc_path)
        dlg.Destroy()
    
    def on_remove_exception(self, event):
        """Remove selected exception"""
        selected = self.exc_list.GetFirstSelected()
        if selected >= 0:
            exc_path = self.exc_list.GetItemText(selected)
            self.library_manager.config["exceptions"].remove(exc_path)
            self.exc_list.DeleteItem(selected)
    
    def on_apply(self, event):
        """Apply changes and rescan if needed"""
        old_libs = self.original_config["libraries"]
        new_libs = self.library_manager.config["libraries"]
        
        # Check if libraries changed
        libs_changed = json.dumps(old_libs) != json.dumps(new_libs)
        
        self.library_manager.save_config()
        
        if libs_changed:
            # Rescan libraries
            try:
                exc_count = self.library_manager.validate_and_scan_all()
                if exc_count > 0:
                    if wx.MessageBox(f"Added {exc_count} executables to exceptions. Open preferences?",
                                    "Exceptions Added", 
                                    wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                        # Already in preferences, just refresh the exceptions list
                        self.exc_list.DeleteAllItems()
                        for exc in self.library_manager.config["exceptions"]:
                            self.exc_list.InsertItem(self.exc_list.GetItemCount(), exc)
            except PermissionError as e:
                wx.MessageBox(str(e), "Permission Denied", wx.OK | wx.ICON_ERROR)
        
        # Update original config
        self.original_config = json.loads(json.dumps(self.library_manager.config))
    
    def on_ok(self, event):
        """Save and close"""
        self.on_apply(event)
        self.EndModal(wx.ID_OK)

class GameListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """Custom ListCtrl for game display"""
    
    def __init__(self, parent, library_manager):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        
        self.library_manager = library_manager
        self.games_displayed = []
        
        # Add columns
        self.AppendColumn("Title", width=200)
        self.AppendColumn("Genre", width=150)
        self.AppendColumn("Developer", width=150)
        self.AppendColumn("Year", width=80)
        self.AppendColumn("Platform", width=150)
        
        # Load saved column widths
        if self.library_manager.config["SavedState"]["column_widths"]:
            widths = self.library_manager.config["SavedState"]["column_widths"]
            for i, width in enumerate(widths):
                if i < self.GetColumnCount():
                    self.SetColumnWidth(i, width)
        
        # Set up sorting
        self.sort_column = self.library_manager.config["SavedState"]["sort_column"]
        self.sort_ascending = self.library_manager.config["SavedState"]["sort_ascending"]
        
        # Bind events
        self.Bind(wx.EVT_LIST_COL_CLICK, self.on_column_click)
        self.Bind(wx.EVT_CHAR, self.on_char)
    
    def populate(self, games):
        """Populate list with games"""
        self.DeleteAllItems()
        self.games_displayed = games
        
        for game in games:
            index = self.InsertItem(self.GetItemCount(), game.title)
            self.SetItem(index, 1, game.genre)
            self.SetItem(index, 2, game.developer)
            self.SetItem(index, 3, game.year)
            self.SetItem(index, 4, ", ".join(game.platforms))
        
        self.sort_list()
    
    def sort_list(self):
        """Sort the list by current column and direction"""
        if not self.games_displayed:
            return
        
        # Sort games
        if self.sort_column == 0:  # Title
            self.games_displayed.sort(key=lambda g: g.title.lower(), 
                                     reverse=not self.sort_ascending)
        elif self.sort_column == 1:  # Genre
            self.games_displayed.sort(key=lambda g: g.genre.lower(), 
                                     reverse=not self.sort_ascending)
        elif self.sort_column == 2:  # Developer
            self.games_displayed.sort(key=lambda g: g.developer.lower(), 
                                     reverse=not self.sort_ascending)
        elif self.sort_column == 3:  # Year
            self.games_displayed.sort(key=lambda g: (g.year == "unknown", g.year), 
                                     reverse=not self.sort_ascending)
        elif self.sort_column == 4:  # Platform
            self.games_displayed.sort(key=lambda g: len(g.platforms), 
                                     reverse=not self.sort_ascending)
        
        # Repopulate
        self.DeleteAllItems()
        for game in self.games_displayed:
            index = self.InsertItem(self.GetItemCount(), game.title)
            self.SetItem(index, 1, game.genre)
            self.SetItem(index, 2, game.developer)
            self.SetItem(index, 3, game.year)
            self.SetItem(index, 4, ", ".join(game.platforms))
        
        # Update column headers with arrows
        for col in range(self.GetColumnCount()):
            info = self.GetColumn(col)
            text = info.GetText().rstrip(' ▲▼')
            if col == self.sort_column:
                text += ' ▲' if self.sort_ascending else ' ▼'
            info.SetText(text)
            self.SetColumn(col, info)
    
    def on_column_click(self, event):
        """Handle column header click for sorting"""
        col = event.GetColumn()
        if col == self.sort_column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = col
            self.sort_ascending = True
        
        self.sort_list()
        
        # Save state
        self.library_manager.config["SavedState"]["sort_column"] = self.sort_column
        self.library_manager.config["SavedState"]["sort_ascending"] = self.sort_ascending
        self.library_manager.save_config()
    
    def on_char(self, event):
        """Handle keyboard shortcuts for sorting"""
        key = event.GetKeyCode()
        if ord('1') <= key <= ord('5'):
            col = key - ord('1')
            if col < self.GetColumnCount():
                if col == self.sort_column:
                    self.sort_ascending = not self.sort_ascending
                else:
                    self.sort_column = col
                    self.sort_ascending = True
                self.sort_list()
                
                # Save state
                self.library_manager.config["SavedState"]["sort_column"] = self.sort_column
                self.library_manager.config["SavedState"]["sort_ascending"] = self.sort_ascending
                self.library_manager.save_config()
        else:
            event.Skip()
    
    def get_selected_game(self):
        """Get currently selected game"""
        selected = self.GetFirstSelected()
        if selected >= 0 and selected < len(self.games_displayed):
            return self.games_displayed[selected]
        return None
    
    def save_column_widths(self):
        """Save current column widths"""
        widths = []
        for i in range(self.GetColumnCount()):
            widths.append(self.GetColumnWidth(i))
        self.library_manager.config["SavedState"]["column_widths"] = widths
        self.library_manager.save_config()

class MainFrame(wx.Frame):
    """Main application window"""
    
    def __init__(self):
        super().__init__(None, title="Game Chooser (0)")
        
        self.library_manager = GameLibraryManager()
        self.filtered_games = []
        self.search_timer = None
        
        # Set up UI
        self.init_ui()
        
        # Load saved state
        self.load_saved_state()
        
        # Initial library check
        self.check_libraries()
        
        # Update title
        self.update_title()
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def init_ui(self):
        """Initialize the user interface"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Menu bar
        self.create_menu_bar()
        
        # Search combo box
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = wx.StaticText(panel, label="Search:")
        self.search_combo = wx.ComboBox(panel, style=wx.CB_DROPDOWN)
        self.search_combo.Bind(wx.EVT_TEXT, self.on_search_text)
        self.search_combo.Bind(wx.EVT_COMBOBOX, self.on_search_select)
        
        search_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        search_sizer.Add(self.search_combo, 1, wx.EXPAND)
        
        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Splitter for list and tree
        splitter = wx.SplitterWindow(panel)
        
        # Game list
        self.game_list = GameListCtrl(splitter, self.library_manager)
        self.game_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_game_selected)
        self.game_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_game_activated)
        self.game_list.Bind(wx.EVT_CONTEXT_MENU, self.on_list_context)
        self.game_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        
        # Tree control
        tree_panel = wx.Panel(splitter)
        tree_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.tree_ctrl = wx.TreeCtrl(tree_panel, 
                                    style=wx.TR_DEFAULT_STYLE | wx.TR_MULTIPLE)
        self.tree_ctrl.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_selection)
        self.tree_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_tree_key)
        
        # Filter tree button
        self.filter_btn = wx.Button(tree_panel, label="Filter Tree")
        self.filter_btn.Bind(wx.EVT_BUTTON, self.on_filter_tree)
        
        tree_sizer.Add(self.tree_ctrl, 1, wx.EXPAND)
        tree_sizer.Add(self.filter_btn, 0, wx.EXPAND | wx.TOP, 5)
        tree_panel.SetSizer(tree_sizer)
        
        # Set up splitter
        splitter.SplitVertically(self.game_list, tree_panel)
        splitter.SetSashGravity(0.5)
        
        main_sizer.Add(splitter, 1, wx.EXPAND)
        
        # Launch button
        self.launch_btn = wx.Button(panel, label="Launch")
        self.launch_btn.Bind(wx.EVT_BUTTON, self.on_launch)
        main_sizer.Add(self.launch_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Store splitter reference
        self.splitter = splitter
        
        # Set up keyboard shortcuts
        self.setup_accelerators()
        
        # Build initial tree
        self.build_tree()
        
        # Populate initial game list
        self.refresh_game_list()
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menu_bar = wx.MenuBar()
        
        # File menu
        file_menu = wx.Menu()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit\tAlt+F4")
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        menu_bar.Append(file_menu, "&File")
        
        # Edit menu
        edit_menu = wx.Menu()
        pref_item = edit_menu.Append(wx.ID_PREFERENCES, "&Preferences\tCtrl+,")
        self.Bind(wx.EVT_MENU, self.on_preferences, pref_item)
        menu_bar.Append(edit_menu, "&Edit")
        
        self.SetMenuBar(menu_bar)
    
    def setup_accelerators(self):
        """Set up keyboard accelerators"""
        accel_entries = []
        
        # Ctrl+F for search
        accel_entries.append((wx.ACCEL_CTRL, ord('F'), wx.NewId()))
        self.Bind(wx.EVT_MENU, lambda e: self.search_combo.SetFocus(), 
                 id=accel_entries[-1][2])
        
        # Ctrl+N for new web game
        accel_entries.append((wx.ACCEL_CTRL, ord('N'), wx.NewId()))
        self.Bind(wx.EVT_MENU, self.on_add_web_game, id=accel_entries[-1][2])
        
        # F5 for refresh
        accel_entries.append((wx.ACCEL_NORMAL, wx.WXK_F5, wx.NewId()))
        self.Bind(wx.EVT_MENU, self.on_refresh, id=accel_entries[-1][2])
        
        accel_table = wx.AcceleratorTable(accel_entries)
        self.SetAcceleratorTable(accel_table)
    
    def check_libraries(self):
        """Check for game libraries on startup"""
        if not self.library_manager.config["libraries"]:
            wx.MessageBox("No game libraries defined. Please select a game library folder.", 
                        "Setup Required", wx.OK | wx.ICON_INFORMATION)
            
            dlg = wx.DirDialog(self, "Choose Game Library Directory")
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                name = os.path.basename(path)
                self.library_manager.config["libraries"].append({
                    "name": name,
                    "path": path
                })
                self.library_manager.save_config()
            else:
                # User cancelled, exit
                self.Close()
                return
            dlg.Destroy()
        
        # Validate and scan
        try:
            exc_count = self.library_manager.validate_and_scan_all()
            
            if len(self.library_manager.games) == 0:
                if wx.MessageBox("No games found in currently added libraries. Open preferences?",
                                "No Games Found", 
                                wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    self.on_preferences(None)
            elif exc_count > 0:
                if wx.MessageBox(f"Added {exc_count} executables to exceptions. Open preferences?",
                                "Exceptions Added", 
                                wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    self.on_preferences(None)
        
        except PermissionError as e:
            if wx.MessageBox(f"{e}\nRemove this library?", 
                            "Permission Denied", 
                            wx.YES_NO | wx.ICON_ERROR) == wx.YES:
                # Remove the problematic library
                # (Would need to identify which one caused the error)
                pass
    
    def build_tree(self, filters=None):
        """Build the tree control hierarchy"""
        self.tree_ctrl.DeleteAllItems()
        
        if filters is None:
            filters = ["platform", "genre", "developer", "year"]
        
        # Build tree structure from games
        tree_data = {}
        
        for game in self.library_manager.games:
            for platform in game.platforms:
                if "platform" not in filters:
                    continue
                    
                if platform not in tree_data:
                    tree_data[platform] = {}
                
                genre = game.genre or "Unknown"
                if "genre" in filters:
                    if genre not in tree_data[platform]:
                        tree_data[platform][genre] = {}
                    
                    developer = game.developer or "Unknown"
                    if "developer" in filters:
                        if developer not in tree_data[platform][genre]:
                            tree_data[platform][genre][developer] = set()
                        
                        if "year" in filters:
                            tree_data[platform][genre][developer].add(game.year)
        
        # Build tree control
        root = self.tree_ctrl.AddRoot("Games")
        
        for platform in sorted(tree_data.keys()):
            plat_node = self.tree_ctrl.AppendItem(root, platform)
            
            if "genre" in filters:
                for genre in sorted(tree_data[platform].keys()):
                    genre_node = self.tree_ctrl.AppendItem(plat_node, genre)
                    
                    if "developer" in filters:
                        for developer in sorted(tree_data[platform][genre].keys()):
                            dev_node = self.tree_ctrl.AppendItem(genre_node, developer)
                            
                            if "year" in filters:
                                for year in sorted(tree_data[platform][genre][developer]):
                                    self.tree_ctrl.AppendItem(dev_node, year)
        
        self.tree_ctrl.ExpandAll()
    
    def on_tree_selection(self, event):
        """Handle tree selection changes"""
        self.apply_filters()
    
    def on_tree_key(self, event):
        """Handle tree keyboard events"""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            # Clear selection
            self.tree_ctrl.UnselectAll()
            self.apply_filters()
        elif event.GetKeyCode() == wx.WXK_DELETE:
            # Delete selected game if applicable
            # (Tree doesn't have games anymore, so this might not apply)
            pass
        else:
            event.Skip()
    
    def get_tree_selection_criteria(self):
        """Get filtering criteria from tree selection"""
        selections = self.tree_ctrl.GetSelections()
        if not selections:
            return None
        
        criteria = {
            "platforms": set(),
            "genres": set(),
            "developers": set(),
            "years": set()
        }
        
        for item in selections:
            path = []
            current = item
            while current and current != self.tree_ctrl.GetRootItem():
                path.insert(0, self.tree_ctrl.GetItemText(current))
                current = self.tree_ctrl.GetItemParent(current)
            
            if len(path) >= 1:
                criteria["platforms"].add(path[0])
            if len(path) >= 2:
                criteria["genres"].add(path[1])
            if len(path) >= 3:
                criteria["developers"].add(path[2])
            if len(path) >= 4:
                criteria["years"].add(path[3])
        
        return criteria
    
    def apply_filters(self):
        """Apply search and tree filters"""
        search_term = self.search_combo.GetValue().lower().strip()
        tree_criteria = self.get_tree_selection_criteria()
        
        filtered = []
        
        for game in self.library_manager.games:
            # Apply tree filter first
            if tree_criteria:
                platform_match = not tree_criteria["platforms"] or \
                                any(p in tree_criteria["platforms"] for p in game.platforms)
                genre_match = not tree_criteria["genres"] or \
                             game.genre in tree_criteria["genres"] or \
                             (game.genre == "" and "Unknown" in tree_criteria["genres"])
                dev_match = not tree_criteria["developers"] or \
                           game.developer in tree_criteria["developers"] or \
                           (game.developer == "" and "Unknown" in tree_criteria["developers"])
                year_match = not tree_criteria["years"] or \
                            game.year in tree_criteria["years"]
                
                if not (platform_match and genre_match and dev_match and year_match):
                    continue
            
            # Apply search filter
            if search_term:
                if not any(search_term in field.lower() for field in 
                          [game.title, game.genre, game.developer, game.year] + game.platforms):
                    continue
            
            filtered.append(game)
        
        self.filtered_games = filtered
        self.game_list.populate(filtered)
        
        # Select first item if any
        if filtered:
            self.game_list.Select(0)
    
    def refresh_game_list(self):
        """Refresh the game list display"""
        self.apply_filters()
        self.update_title()
    
    def on_search_text(self, event):
        """Handle search text changes with delay"""
        # Cancel previous timer
        if self.search_timer:
            self.search_timer.Stop()
        
        # Start new timer for 0.5 second delay
        self.search_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_search_timer)
        self.search_timer.Start(500, wx.TIMER_ONE_SHOT)
    
    def on_search_timer(self, event):
        """Execute search after delay"""
        search_term = self.search_combo.GetValue().lower().strip()
        
        # Find matching values for combo box
        matches = set()
        for game in self.library_manager.games:
            if search_term in game.title.lower():
                matches.add(game.title)
            if search_term in game.genre.lower():
                matches.add(game.genre)
            if search_term in game.developer.lower():
                matches.add(game.developer)
            if search_term in game.year.lower():
                matches.add(game.year)
            for platform in game.platforms:
                if search_term in platform.lower():
                    matches.add(platform)
        
        # Update combo box choices
        self.search_combo.SetItems(sorted(matches))
        
        # Apply filters
        self.apply_filters()
    
    def on_search_select(self, event):
        """Handle combo box selection"""
        self.apply_filters()
    
    def on_game_selected(self, event):
        """Handle game selection in list"""
        game = self.game_list.get_selected_game()
        if game:
            self.launch_btn.SetLabel(f"Launch {game.title}")
            
            # Save selected game
            self.library_manager.config["SavedState"]["last_selected"] = game.title
            self.library_manager.save_config()
    
    def on_game_activated(self, event):
        """Handle double-click on game"""
        self.on_launch(None)
    
    def on_list_context(self, event):
        """Show context menu for list"""
        menu = wx.Menu()
        
        game = self.game_list.get_selected_game()
        if game:
            launch_item = menu.Append(wx.ID_ANY, "Launch")
            self.Bind(wx.EVT_MENU, self.on_launch, launch_item)
            
            edit_item = menu.Append(wx.ID_ANY, "Edit")
            self.Bind(wx.EVT_MENU, self.on_edit_game, edit_item)
            
            delete_item = menu.Append(wx.ID_ANY, "Delete")
            self.Bind(wx.EVT_MENU, self.on_delete_game, delete_item)
            
            menu.AppendSeparator()
        
        add_web_item = menu.Append(wx.ID_ANY, "Add Web Game")
        self.Bind(wx.EVT_MENU, self.on_add_web_game, add_web_item)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_list_key(self, event):
        """Handle list keyboard events"""
        key = event.GetKeyCode()
        
        if key == ord('E'):
            self.on_edit_game(None)
        elif key == wx.WXK_DELETE:
            self.on_delete_game(None)
        elif key in [wx.WXK_RETURN, wx.WXK_SPACE]:
            self.on_launch(None)
        else:
            event.Skip()
    
    def on_launch(self, event):
        """Launch selected game"""
        game = self.game_list.get_selected_game()
        if not game:
            return
        
        if game.launch_path.startswith("http"):
            # Web game
            webbrowser.open(game.launch_path)
        else:
            # Regular game
            full_path = self.library_manager.get_full_path(game)
            if not full_path or not Path(full_path).exists():
                wx.MessageBox("Game executable not found. Please locate the game.",
                            "File Not Found", wx.OK | wx.ICON_ERROR)
                
                # File dialog to relocate
                dlg = wx.FileDialog(self, "Locate Game Executable")
                if dlg.ShowModal() == wx.ID_OK:
                    new_path = dlg.GetPath()
                    
                    # Validate path is in a library
                    valid = False
                    for lib in self.library_manager.config["libraries"]:
                        if new_path.startswith(lib["path"]):
                            # Update game path
                            rel_path = Path(new_path).relative_to(Path(lib["path"]).parent)
                            game.launch_path = str(rel_path).replace(os.sep, '\\')
                            self.library_manager.save_games()
                            valid = True
                            break
                    
                    if not valid:
                        wx.MessageBox("Selected file is not in a configured game library.",
                                    "Invalid Location", wx.OK | wx.ICON_ERROR)
                        return
                dlg.Destroy()
                return
            
            # Launch the game
            try:
                system = platform.system()
                if system == "Darwin" and full_path.endswith(".app"):
                    # macOS .app bundle
                    subprocess.Popen(["open", "-a", full_path])
                else:
                    # Regular executable
                    subprocess.Popen([full_path])
                
                # Minimize window
                self.Iconize(True)
            
            except Exception as e:
                wx.MessageBox(f"Failed to launch game: {e}",
                            "Launch Error", wx.OK | wx.ICON_ERROR)
    
    def on_edit_game(self, event):
        """Edit selected game"""
        game = self.game_list.get_selected_game()
        if not game:
            return
        
        is_web = game.launch_path.startswith("http")
        dlg = EditGameDialog(self, game, self.library_manager, is_web)
        if dlg.ShowModal() == wx.ID_OK:
            self.library_manager.save_games()
            self.refresh_game_list()
        dlg.Destroy()
    
    def on_delete_game(self, event):
        """Delete selected game"""
        game = self.game_list.get_selected_game()
        if not game:
            return
        
        if wx.MessageBox(f"Delete '{game.title}' from library?",
                        "Confirm Delete",
                        wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.library_manager.games.remove(game)
            self.library_manager.save_games()
            self.refresh_game_list()
    
    def on_add_web_game(self, event):
        """Add a new web game"""
        game = Game(title="", platforms=["Web"], launch_path="https://")
        dlg = EditGameDialog(self, game, self.library_manager, is_web=True)
        
        if dlg.ShowModal() == wx.ID_OK:
            self.library_manager.games.append(game)
            self.library_manager.save_games()
            self.refresh_game_list()
        dlg.Destroy()
    
    def on_filter_tree(self, event):
        """Show filter tree dialog"""
        dlg = wx.Dialog(self, title="Filter Tree Levels", size=(300, 200))
        
        panel = wx.Panel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Checkboxes for each level
        levels = ["Platform", "Genre", "Developer", "Year"]
        checkboxes = []
        
        for level in levels:
            cb = wx.CheckBox(panel, label=level)
            cb.SetValue(True)  # All checked by default
            checkboxes.append(cb)
            sizer.Add(cb, 0, wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 10)
        panel.SetSizer(sizer)
        
        if dlg.ShowModal() == wx.ID_OK:
            # Rebuild tree with selected levels
            filters = []
            if checkboxes[0].GetValue():
                filters.append("platform")
            if checkboxes[1].GetValue():
                filters.append("genre")
            if checkboxes[2].GetValue():
                filters.append("developer")
            if checkboxes[3].GetValue():
                filters.append("year")
            
            self.build_tree(filters)
        
        dlg.Destroy()
    
    def on_preferences(self, event):
        """Show preferences dialog"""
        dlg = PreferencesDialog(self, self.library_manager)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_game_list()
            self.build_tree()
        dlg.Destroy()
    
    def on_refresh(self, event):
        """Refresh/rescan libraries"""
        try:
            exc_count = self.library_manager.validate_and_scan_all()
            self.refresh_game_list()
            self.build_tree()
            
            if exc_count > 0:
                if wx.MessageBox(f"Added {exc_count} executables to exceptions. Open preferences?",
                                "Exceptions Added",
                                wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    self.on_preferences(None)
        
        except PermissionError as e:
            wx.MessageBox(str(e), "Permission Denied", wx.OK | wx.ICON_ERROR)
    
    def on_exit(self, event):
        """Exit application"""
        self.Close()
    
    def update_title(self):
        """Update window title with game count"""
        count = len(self.library_manager.games)
        self.SetTitle(f"Game Chooser ({count})")
    
    def load_saved_state(self):
        """Load saved window state"""
        state = self.library_manager.config["SavedState"]
        
        # Window size and position
        if state["window_size"]:
            self.SetSize(state["window_size"])
        else:
            # Default to 50% of screen
            display = wx.Display()
            rect = display.GetClientArea()
            self.SetSize(rect.width // 2, rect.height // 2)
        
        if state["window_position"]:
            self.SetPosition(state["window_position"])
        else:
            self.Centre()
        
        # Splitter position
        if state["splitter_position"]:
            self.splitter.SetSashPosition(state["splitter_position"])
        else:
            # Default 50/50 split
            width = self.GetSize()[0]
            self.splitter.SetSashPosition(width // 2)
        
        # Search term
        if state["last_search"]:
            self.search_combo.SetValue(state["last_search"])
    
    def save_state(self):
        """Save current window state"""
        state = self.library_manager.config["SavedState"]
        
        state["window_size"] = list(self.GetSize())
        state["window_position"] = list(self.GetPosition())
        state["splitter_position"] = self.splitter.GetSashPosition()
        state["last_search"] = self.search_combo.GetValue()
        
        # Save column widths
        self.game_list.save_column_widths()
        
        self.library_manager.save_config()
    
    def on_close(self, event):
        """Handle window close"""
        self.save_state()
        self.library_manager.save_games()
        self.library_manager.save_config()
        self.Destroy()

class GameChooserApp(wx.App):
    """Main application class"""
    
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True

if __name__ == "__main__":
    app = GameChooserApp()
    app.MainLoop()
