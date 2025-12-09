# RogueFinder

A Windows-based WiFi security monitoring tool that detects rogue access points (APs) attempting to impersonate your network. RogueFinder actively scans for access points and alerts you when it detects:

- **Unknown BSSIDs** broadcasting your network's SSID
- **Similar SSIDs** that could be impersonation attempts
- **BSSID changes** on your current connection

## Features

### 🎥 Demo Video
Watch RogueFinder in action:

<video src="RogueAPFinder.mp4" width="320" height="240" controls></video>

### 🔍 Detection Capabilities
- **Active Scanning**: Scans all visible access points, not just your current connection
- **BSSID Monitoring**: Tracks MAC addresses (BSSIDs) of legitimate access points
- **Similar SSID Detection**: Identifies networks with similar names (70%+ similarity) that could be rogue APs
- **Real-time Alerts**: Windows notifications when threats are detected

### 🖥️ Two Interfaces
- **GUI Application**: User-friendly interface with system tray support
- **Command Line**: Lightweight script for automation and scripting

### 🔄 Smart Refresh
- Automatically refreshes network scans to detect newly appeared APs
- Configurable scan intervals

## Installation

### Prerequisites
- Windows 10/11
- Python 3.6 or higher
- WiFi adapter with `netsh` support (standard on Windows)

### Setup

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure your baseline** (first time setup):
   ```powershell
   python rogue_finder.py --setup
   ```
   This scans for all legitimate access points for your current network and saves them as the baseline.

## Usage

### GUI Application (Recommended)

Launch the GUI application:
```powershell
python rogue_finder_gui.py
```

**Features:**
- **System Tray Icon**: Minimizes to system tray when closed
- **Activity Log**: View all detections and monitoring activity
- **Start/Stop Controls**: Pause monitoring anytime
- **Setup Baseline**: Configure baseline directly from the GUI
- **Status Display**: See current SSID, known BSSIDs count, and monitoring status

**First Run:**
1. If no baseline is configured, click "Setup Baseline"
2. Click "Start Monitoring" to begin
3. Close the window to minimize to system tray
4. Right-click the system tray icon to show window or exit

### Command Line Interface

#### Initial Setup
```powershell
# Configure baseline (run once)
python rogue_finder.py --setup
```

#### Monitoring Options

**Continuous monitoring** (default 10-second intervals):
```powershell
python rogue_finder.py
```

**One-time scan**:
```powershell
python rogue_finder.py --once
```

**Custom scan interval** (in seconds):
```powershell
python rogue_finder.py --interval 5
```

#### Command Line Options

| Option | Description |
|--------|-------------|
| `--setup` | Configure baseline from current network and exit |
| `--once` | Run a single scan and exit |
| `--interval`, `-i` | Set scan interval in seconds (default: 10) |

## How It Works

1. **Baseline Configuration**: On first run with `--setup`, the tool:
   - Scans all visible access points for your current SSID
   - Records all BSSIDs (MAC addresses) as legitimate
   - Saves this baseline to `.last_bssid`

2. **Active Monitoring**: During monitoring, the tool:
   - Scans all visible WiFi networks
   - Compares found BSSIDs against the baseline
   - Checks for similar SSIDs (70%+ similarity)
   - Alerts when unknown BSSIDs or similar SSIDs are detected

3. **Detection Types**:
   - **Rogue AP**: Unknown BSSID broadcasting your SSID
   - **Similar SSID**: Network name similar to yours (e.g., "MyNetwork" vs "MyNetwork2")
   - **BSSID Change**: Your connection switched to an unknown BSSID

## File Structure

```
RogueFinder/
├── rogue_finder.py          # Command-line version
├── rogue_finder_gui.py      # GUI application
├── requirements.txt          # Python dependencies
├── .last_bssid              # Baseline configuration (auto-generated)
└── README.md                # This file
```

## Configuration

The baseline configuration is stored in `.last_bssid`:
- **Line 1**: Your network's SSID
- **Lines 2+**: One BSSID per line (legitimate access points)

To reset the baseline, delete `.last_bssid` and run `--setup` again.

## Packaging as Executable

Create a standalone `.exe` file using PyInstaller:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed rogue_finder_gui.py
```

The executable will be in the `dist/` folder.

## Troubleshooting

### "No baseline configured"
**Solution**: Run `python rogue_finder.py --setup` first

### Not detecting rogue APs
- Ensure the rogue AP is broadcasting and visible
- The tool refreshes scans, but Windows may cache results
- Try disconnecting and reconnecting to WiFi to force a fresh scan

### Notifications not appearing
- Ensure Windows notifications are enabled
- Check that `win10toast` is installed: `pip install win10toast`
- For GUI version, check the activity log in the application

### "netsh command not found"
- This tool requires Windows
- Ensure you're running from Command Prompt or PowerShell
- Verify WiFi adapter is enabled

## Security Notes

⚠️ **Important**: This tool helps detect potential rogue APs but:
- Does not prevent connection to rogue APs
- Requires manual baseline configuration
- May produce false positives (legitimate APs with similar names)
- Always verify network security through other means

**Best Practices**:
- Configure baseline when you're certain all visible APs are legitimate
- Review alerts carefully before taking action
- Use in combination with other security measures
- Keep your baseline updated if your network changes

## How Similar SSID Detection Works

The similarity algorithm checks:
- **Exact match**: 100% similarity
- **Substring match**: One SSID contains the other (90% similarity)
- **Character matching**: Percentage of matching characters
- **Length similarity**: Bonus for similar lengths

SSIDs with ≥70% similarity trigger alerts. Examples:
- "MyNetwork" vs "MyNetwork2" → Alert
- "MyNetwork" vs "MyNetwork " → Alert
- "MyNetwork" vs "MyNetworkX" → Alert
- "MyNetwork" vs "OtherNetwork" → No alert

## License

This project is provided as-is for educational and security research purposes.

## Contributing

Feel free to submit issues, feature requests, or pull requests.

## Acknowledgments

Built for Windows WiFi security monitoring using `netsh` and Python.
