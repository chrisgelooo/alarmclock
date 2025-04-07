# Installation Guide for Pro Alarm & World Clock

This guide provides detailed instructions for installing and running the Pro Alarm & World Clock application.

## Prerequisites

### For Running from Source
- Python 3.8 or higher
- pip (Python package installer)
- Git (optional, for cloning the repository)

### For Running the Executable
- Windows operating system
- No additional prerequisites required

## Installation Methods

### Method 1: Run from Source Code

1. **Get the Source Code**
   
   Option A: Clone the repository using Git:
   ```
   git clone https://github.com/yourusername/alarmclock.git
   cd alarmclock
   ```
   
   Option B: Download the ZIP file from GitHub:
   - Go to https://github.com/yourusername/alarmclock
   - Click the "Code" button and select "Download ZIP"
   - Extract the ZIP file to a location of your choice
   - Open a command prompt and navigate to the extracted folder

2. **Install Dependencies**
   
   Run the following command to install all required packages:
   ```
   pip install pygame pillow pystray pytz tkcalendar
   ```

3. **Run the Application**
   
   Start the application with:
   ```
   python alarm_clock.py
   ```

### Method 2: Run the Windows Executable

1. **Download the Executable**
   
   Option A: Download from GitHub Releases:
   - Go to https://github.com/yourusername/alarmclock/releases
   - Download the latest release ZIP file
   - Extract the ZIP file to a location of your choice

   Option B: Build the executable yourself:
   - Follow the "Run from Source Code" steps 1-2 above
   - Install PyInstaller: `pip install pyinstaller`
   - Build the executable:
     ```
     pyinstaller --onefile --windowed --icon=alarm_icon.ico --add-data "sounds;sounds" --add-data "alarm_icon.ico;." alarm_clock.py
     ```
   - Find the executable in the `dist` folder

2. **Run the Application**
   
   - Navigate to the folder containing `alarm_clock.exe`
   - Double-click on `alarm_clock.exe` to start the application

3. **Create a Shortcut (Optional)**
   
   - Right-click on `alarm_clock.exe`
   - Select "Create shortcut"
   - Move the shortcut to your desktop or start menu

## Troubleshooting

### Common Issues with Source Code Installation

1. **Missing Dependencies**
   
   If you see an error about missing modules, try installing the specific package:
   ```
   pip install <package_name>
   ```

2. **Python Version Issues**
   
   Ensure you're using Python 3.8 or higher:
   ```
   python --version
   ```

3. **Pygame Installation Problems**
   
   If Pygame fails to install, try:
   ```
   pip install --upgrade pip
   pip install pygame --pre
   ```

### Common Issues with Executable

1. **Antivirus Blocking**
   
   Some antivirus software may flag the executable. You may need to add an exception for the application.

2. **Missing DLL Files**
   
   If you see errors about missing DLL files, try installing the Microsoft Visual C++ Redistributable:
   https://aka.ms/vs/17/release/vc_redist.x64.exe

3. **Application Not Starting**
   
   Try running the executable as administrator:
   - Right-click on `alarm_clock.exe`
   - Select "Run as administrator"

## Data Storage

The application creates the following files to store your settings:

- `settings.json`: Application settings
- `alarms.json`: Alarm configurations
- `world_clocks.json`: Saved world clock timezones

These files are created in the same directory as the application.

## Uninstallation

### For Source Code Installation
- Simply delete the project folder

### For Executable Installation
- Delete the folder containing `alarm_clock.exe` and associated files
- Delete any shortcuts you created

## Support

If you encounter any issues, please create an issue on the GitHub repository:
https://github.com/yourusername/alarmclock/issues
