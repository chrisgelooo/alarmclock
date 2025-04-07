# Pro Alarm & World Clock

A feature-rich alarm clock and world time application built with Python and Tkinter.

![Alarm Clock Screenshot](screenshots/alarm_clock.png)

## Features

- **Multiple Alarms**: Create and manage multiple alarms with different settings
- **Recurring Alarms**: Set alarms to repeat daily, on weekdays, weekends, or specific days
- **Date-Specific Alarms**: Schedule alarms for specific calendar dates
- **World Clock**: View the current time in multiple time zones
- **Calendar View**: Visual calendar showing all scheduled alarms
- **Snooze Function**: Easily snooze alarms for a customizable duration
- **Custom Sounds**: Choose from built-in sounds or use your own audio files
- **System Tray**: Minimize to system tray for background operation
- **Dark Mode**: Toggle between light and dark themes
- **Compact Mode**: Adjust the UI size for different screen sizes

## Installation

### Option 1: Run from Source (Requires Python)

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/alarmclock.git
   cd alarmclock
   ```

2. Install the required dependencies:
   ```
   pip install pygame pillow pystray pytz tkcalendar
   ```

3. Run the application:
   ```
   python alarm_clock.py
   ```

### Option 2: Standalone Executable (Windows)

1. Download the latest release from the [Releases](https://github.com/yourusername/alarmclock/releases) page
2. Extract the ZIP file to a location of your choice
3. Run `alarm_clock.exe`

## Building the Executable

If you want to build the executable yourself:

1. Install PyInstaller:
   ```
   pip install pyinstaller
   ```

2. Build the executable:
   ```
   pyinstaller --onefile --windowed --icon=alarm_icon.ico --add-data "sounds;sounds" --add-data "alarm_icon.ico;." alarm_clock.py
   ```

3. The executable will be created in the `dist` folder

## Usage

### Setting Alarms

1. Click "Add New Alarm" in the Alarms tab
2. Set the time, label, and sound for your alarm
3. Choose the recurrence pattern (once, daily, weekdays, weekends, or specific days)
4. For date-specific alarms, select "Specific Date" and choose a date
5. Click "Save" to create the alarm

### Managing Alarms

- **Edit**: Select an alarm and click "Edit Selected" to modify its settings
- **Delete**: Select an alarm and click "Delete Selected" to remove it
- **Filter**: Use the date picker to filter alarms by date

### World Clock

1. Click "Add Timezone" in the World Clock tab
2. Select a timezone from the list
3. The current time in that timezone will be displayed

### Calendar View

- The Calendar tab shows all your scheduled alarms
- Click on a date to see alarms scheduled for that day
- Click "Add Alarm for Selected Date" to create a new alarm for the selected date

### Settings

- **Volume**: Adjust the alarm sound volume
- **Snooze Duration**: Set the default snooze time in minutes
- **Dark Mode**: Toggle between light and dark themes
- **Compact Mode**: Toggle between normal and compact UI sizes
- **Minimize to Tray**: Enable/disable minimizing to system tray when closing

## Data Storage

The application stores your settings and alarms in JSON files:
- `settings.json`: Application settings
- `alarms.json`: Alarm configurations
- `world_clocks.json`: Saved world clock timezones

These files are created in the same directory as the application.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Python and Tkinter
- Uses pygame for sound playback
- Uses pystray for system tray functionality
- Uses pytz for timezone handling
- Uses tkcalendar for the calendar widget
