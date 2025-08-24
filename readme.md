# Game Chooser

A cross-platform desktop application for organizing and launching your video game library, built with Python and wxPython.

## Features

### Core Functionality
- **Auto-discovery** - Automatically scans configured folders to find and catalog games
- **Smart Detection** - Intelligently identifies game executables while filtering out updaters and tools
- **Multi-platform Support** - Works with Windows (.exe, .bat) and macOS (unix executables)
- **Web Games** - Add browser-based games with URL launching support
- **Portable Library** - Share your game database between computers with relative path storage

### Organization & Search
- **Hierarchical Filtering** - Browse games by Platform → Genre → Developer → Year
- **Instant Search** - Real-time filtering across all game metadata fields
- **Smart Sorting** - Click column headers to sort by any field
- **Multi-select Filtering** - Select multiple tree nodes to see games matching any criteria

### User Experience
- **Persistent State** - Remembers window size, position, sort preferences, and last selection
- **Keyboard-First Design** - Full keyboard navigation for accessibility
- **Context Menus** - Right-click access to all game management functions
- **Batch Management** - Scan multiple library folders and manage exceptions

## Installation

### Requirements
- Python 3.6 or higher
- wxPython

### Install Dependencies
```bash
# Windows/macOS
pip install wxPython

### Run the Application
```bash
python game_chooser.py
```

## Keyboard Shortcuts

### Global Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search box |
| `Ctrl+N` | Add new web game |
| `Ctrl+,` | Open preferences |
| `F5` | Refresh/rescan libraries |
| `Alt+F4` | Exit application |

### List Control Shortcuts
| Shortcut | Action |
|----------|--------|
| `E` | Edit selected game |
| `Delete` | Delete selected game |
| `Enter` / `Space` | Launch selected game |
| `1-5` | Sort by column (1=Title, 2=Genre, 3=Developer, 4=Year, 5=Platform) |
| `Right-click` | Open context menu |

### Tree Control Shortcuts
| Shortcut | Action |
|----------|--------|
| `Escape` | Clear tree selection (show all games) |
| `Delete` | Delete selected game (if applicable) |
| `Ctrl+Click` | Multi-select nodes for OR filtering |

### Search Box Behavior
- Type to search across all fields (title, genre, developer, year, platform)
- 0.5 second delay before search executes (prevents lag while typing)
- Dropdown shows all matching values from your library
- Select from dropdown to filter by that exact value

## File Structure

The application creates two JSON files:

### games.json (Portable)
- Stored in the application directory
- Contains your game library with relative paths
- Can be shared between users/computers

### config.json (User-specific)
- Stored in platform-specific app data folder:
  - Windows: `%APPDATA%\GameChooser\`
  - macOS: `~/Library/Application Support/GameChooser/`
  - Linux: `~/.config/GameChooser/`
- Contains library paths, exceptions, and UI preferences

## Game Detection

The scanner automatically identifies games by looking for executables named:
- `game.exe` / `game`
- `launch.exe` / `launch`
- `play.exe` / `play`
- Executable matching the parent folder name

If none of these are found, the first executable found in the directory is presumed to be the launch path. All others are added to the exceptions list, which can be managed in preferences.

## Usage Tips

1. **First Launch** - You'll be prompted to select a game library folder
2. **Multiple Libraries** - Add more folders via Edit → Preferences
3. **Web or manual Games** - Right-click in the game list to add web-based games or to add a game manually if you have a game outside of your dedicated games directory.
4. **Keyboard Navigation** - Press Tab to move between controls
5. **Quick Launch** - Double-click any game to launch immediately
6. **Filtering** - Combine tree selection and search for precise filtering

## Troubleshooting

### No games found
- Check that your game folders contain valid executables
- Verify folder permissions
- Review the exceptions list in Preferences

### Games won't launch
- The app will prompt you to relocate missing executables
- Ensure games are within configured library paths or manual paths are valid.
- Check file permissions on macOS/Linux

### Performance issues
- Large libraries (1000+ games) may take a moment to scan
- The 0.5 second search delay prevents lag while typing

