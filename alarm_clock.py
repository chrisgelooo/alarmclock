import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont, simpledialog
import time
import datetime
import threading
import pygame
from plyer import notification
import os
import sys
from PIL import Image # Requires Pillow
import pystray # Requires pystray
import json
import uuid
import pytz # Requires pytz
from tkcalendar import Calendar, DateEntry # Requires tkcalendar
from collections import defaultdict

# --- Constants ---
# Light Theme Colors (Default)
L_COLOR_BACKGROUND = "#F5F5F5"; L_COLOR_FRAME_BG = "#FFFFFF"; L_COLOR_TEXT = "#333333"
L_COLOR_TEXT_SECONDARY = "#666666"; L_COLOR_ACCENT = "#0078D4"; L_COLOR_ACCENT_FG = "#FFFFFF"
L_COLOR_SUCCESS = "#107C10"; L_COLOR_ERROR = "#D83B01"; L_COLOR_DISABLED = "#BDBDBD"
L_COLOR_HIGHLIGHT = "#E0E0E0"; L_CAL_BG = "#DDEBF7"; L_CAL_FG = L_COLOR_TEXT

# Dark Theme Colors
D_COLOR_BACKGROUND = "#2D2D30"; D_COLOR_FRAME_BG = "#1E1E1E"; D_COLOR_TEXT = "#F1F1F1"
D_COLOR_TEXT_SECONDARY = "#A0A0A0"; D_COLOR_ACCENT = "#007ACC"; D_COLOR_ACCENT_FG = "#FFFFFF"
D_COLOR_SUCCESS = "#4CAF50"; D_COLOR_ERROR = "#F44336"; D_COLOR_DISABLED = "#6E6E6E"
D_COLOR_HIGHLIGHT = "#4A4A4A"; D_CAL_BG = "#3C3C3C"; D_CAL_FG = D_COLOR_TEXT

# Font Constants
FONT_FAMILY_UI = "Segoe UI"; FONT_SIZE_BASE = 10; FONT_SIZE_LARGE = 12
FONT_SIZE_XLARGE = 16; FONT_SIZE_CLOCK = 36
FONT_SIZE_CLOCK_COMPACT = 28

# Functionality Constants
SETTINGS_FILE = "settings.json"; ALARMS_FILE = "alarms.json"; WORLD_CLOCKS_FILE = "world_clocks.json"
RECURRENCE_ONCE = "Once"; RECURRENCE_DAILY = "Daily"; RECURRENCE_WEEKDAYS = "Weekdays (Mon-Fri)"
RECURRENCE_WEEKENDS = "Weekends (Sat-Sun)"; RECURRENCE_SPECIFIC_DATE = "Specific Date"
WEEKDAYS = [0, 1, 2, 3, 4]; WEEKENDS = [5, 6]; DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_WORLD_CLOCK = "Asia/Manila"; DEFAULT_VOLUME = 0.7; DEFAULT_SNOOZE_MINUTES = 9
FADE_IN_DURATION_MS = 5000; FADE_IN_STEPS = 20; DEFAULT_SOUNDS_DIR = "sounds"
CALENDAR_EVENT_TAG = "alarm_event"

# --- Helper Functions ---
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except AttributeError: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_alarm_time(hour, minute, time_format):
    dt = datetime.time(hour, minute)
    if time_format == "12h": return dt.strftime("%I:%M %p")
    else: return dt.strftime("%H:%M")

def get_recurrence_display(alarm_data):
    rec_type = alarm_data.get('recurrence_type', RECURRENCE_ONCE)
    if rec_type == RECURRENCE_DAILY: return "Daily"
    if rec_type == RECURRENCE_WEEKDAYS: return "Weekdays"
    if rec_type == RECURRENCE_WEEKENDS: return "Weekends"
    if rec_type == RECURRENCE_SPECIFIC_DATE:
        date_str = alarm_data.get('specific_date')
        if date_str:
             try: return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %b %d, %Y")
             except ValueError: return "Invalid Date"
        else: return "Specific Date (Not Set)"
    if rec_type == "Specific Days":
        days_idx = alarm_data.get('recurrence_days', [])
        if not days_idx: return "Once"
        selected_days = [DAY_NAMES[i] for i in sorted(days_idx)]
        return ", ".join(selected_days)
    return "Once"

# --- Main Application Class ---
class AlarmClockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pro Alarm & World Clock")
        self.root.resizable(True, True)
        self.alarms = []
        self.alarm_lock = threading.Lock()
        self.world_clocks = []
        self.world_clock_lock = threading.Lock()
        self.settings = {}
        self.running = True
        self.time_format = tk.StringVar(value="12h")
        self.current_time_var = tk.StringVar()
        self.close_to_tray_var = tk.BooleanVar(value=True)
        self.ringing_alarms = {}
        self.currently_handled_ringing_id = None
        self.volume_var = tk.DoubleVar()
        self.snooze_duration_var = tk.IntVar()
        self.theme_mode = tk.StringVar()
        self.compact_mode = tk.BooleanVar()
        self.tray_icon = None
        self.tray_thread = None
        self.icon_path = resource_path("alarm_icon.ico")
        
        try: 
            self.root.iconbitmap(self.icon_path)
        except Exception as e: 
            print(f"Warn: Icon load err: {e}")
            
        try:
            pygame.init()
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            print(f"Pygame OK. Ch: {pygame.mixer.get_num_channels()}")
        except pygame.error as e: 
            messagebox.showerror("Audio Error", f"Pygame init fail: {e}\nSounds off.")
            
        self.load_settings()
        self.root.configure(bg=self.BG_COLOR) # Load settings before styling/widgets
        self.style = ttk.Style()
        self.setup_styles()
        self.load_alarms()
        self.load_world_clocks()
        self.create_widgets()
        self.volume_var.trace_add("write", self.on_volume_change)
        self.snooze_duration_var.trace_add("write", self.on_snooze_change)
        self.theme_mode.trace_add("write", self.on_theme_change)
        self.compact_mode.trace_add("write", self.on_compact_mode_change)
        self.update_local_clock()
        self.update_world_clocks_display()
        self.alarm_check_thread = threading.Thread(target=self.check_alarm_loop, daemon=True)
        self.alarm_check_thread.start()
        self.setup_tray_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_alarm_list_display()
        self.update_calendar_events()
        self.toggle_compact_mode(init=True) # Set initial size

    # --- Theme Properties ---
    @property
    def BG_COLOR(self): 
        return D_COLOR_BACKGROUND if self.theme_mode.get() == 'dark' else L_COLOR_BACKGROUND
    
    @property
    def FRAME_BG(self): 
        return D_COLOR_FRAME_BG if self.theme_mode.get() == 'dark' else L_COLOR_FRAME_BG
    
    @property
    def TEXT_COLOR(self): 
        return D_COLOR_TEXT if self.theme_mode.get() == 'dark' else L_COLOR_TEXT
    
    @property
    def TEXT_SECONDARY(self): 
        return D_COLOR_TEXT_SECONDARY if self.theme_mode.get() == 'dark' else L_COLOR_TEXT_SECONDARY
    
    @property
    def ACCENT_COLOR(self): 
        return D_COLOR_ACCENT if self.theme_mode.get() == 'dark' else L_COLOR_ACCENT
    
    @property
    def ACCENT_FG(self): 
        return D_COLOR_ACCENT_FG
    
    @property
    def DISABLED_COLOR(self): 
        return D_COLOR_DISABLED if self.theme_mode.get() == 'dark' else L_COLOR_DISABLED
    
    @property
    def ERROR_COLOR(self): 
        return D_COLOR_ERROR if self.theme_mode.get() == 'dark' else L_COLOR_ERROR
    
    @property
    def SUCCESS_COLOR(self): 
        return D_COLOR_SUCCESS if self.theme_mode.get() == 'dark' else L_COLOR_SUCCESS
    
    @property
    def CAL_BG(self): 
        return D_CAL_BG if self.theme_mode.get() == 'dark' else L_CAL_BG
    
    @property
    def CAL_FG(self): 
        return D_CAL_FG if self.theme_mode.get() == 'dark' else L_CAL_FG

    def setup_styles(self):
        mode = self.theme_mode.get()
        try: 
            self.style.theme_use('clam')
        except tk.TclError:
            try: 
                self.style.theme_use('vista')
            except tk.TclError: 
                self.style.theme_use('default')
                
        self.style.configure('.', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('TFrame', background=self.BG_COLOR)
        self.style.configure('TLabel', background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('TRadiobutton', background=self.BG_COLOR, foreground=self.TEXT_COLOR, indicatorcolor=self.FRAME_BG)
        self.style.map('TRadiobutton', background=[('active', self.FRAME_BG)])
        self.style.configure('TCheckbutton', background=self.BG_COLOR, foreground=self.TEXT_COLOR, indicatorcolor=self.FRAME_BG)
        self.style.map('TCheckbutton', background=[('active', self.FRAME_BG)])
        self.style.configure('TNotebook', background=self.BG_COLOR, borderwidth=0, tabmargins=[2, 5, 2, 0])
        self.style.configure('TNotebook.Tab', font=(FONT_FAMILY_UI, FONT_SIZE_BASE, 'bold'), padding=[10, 5], background=self.BG_COLOR, foreground=self.TEXT_SECONDARY, borderwidth=0)
        self.style.map('TNotebook.Tab', background=[('selected', self.FRAME_BG)], foreground=[('selected', self.ACCENT_COLOR)])
        self.style.configure('TButton', font=(FONT_FAMILY_UI, FONT_SIZE_BASE, 'bold'), padding=(10, 6), relief=tk.FLAT, borderwidth=0, background=self.ACCENT_COLOR, foreground=self.ACCENT_FG)
        self.style.map('TButton', background=[('active', '#005A9E' if mode == 'light' else '#1F8DCD'), ('disabled', self.DISABLED_COLOR)], foreground=[('disabled', self.TEXT_SECONDARY)])
        self.style.configure('Secondary.TButton', background=self.TEXT_SECONDARY, foreground=self.ACCENT_FG)
        self.style.map('Secondary.TButton', background=[('active', '#505050' if mode == 'light' else '#7A7A7A'), ('disabled', self.DISABLED_COLOR)])
        self.style.configure('TSpinbox', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), padding=(5, 5), relief=tk.FLAT, borderwidth=1, bordercolor=self.DISABLED_COLOR, fieldbackground=self.FRAME_BG, foreground=self.TEXT_COLOR, arrowcolor=self.TEXT_COLOR)
        self.style.map('TSpinbox', bordercolor=[('focus', self.ACCENT_COLOR)])
        self.style.configure('TEntry', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), padding=(5, 5), relief=tk.FLAT, borderwidth=1, bordercolor=self.DISABLED_COLOR, fieldbackground=self.FRAME_BG, foreground=self.TEXT_COLOR)
        self.style.map('TEntry', bordercolor=[('focus', self.ACCENT_COLOR)], fieldbackground=[('readonly', self.BG_COLOR)])
        self.style.configure('Horizontal.TScale', background=self.BG_COLOR, troughcolor=self.FRAME_BG)
        self.style.map('Horizontal.TScale', background=[('active', self.ACCENT_COLOR)])
        self.style.configure("Treeview", rowheight=25, fieldbackground=self.FRAME_BG, background=self.FRAME_BG, foreground=self.TEXT_COLOR, relief=tk.FLAT, borderwidth=0)
        self.style.configure("Treeview.Heading", font=(FONT_FAMILY_UI, FONT_SIZE_BASE, 'bold'), background=self.ACCENT_COLOR, foreground=self.ACCENT_FG, relief=tk.FLAT)
        self.style.map("Treeview.Heading", background=[('active', self.ACCENT_COLOR)])
        self.style.configure("ringing.Treeview", background=self.ERROR_COLOR, foreground='white')
        self.style.configure("disabled.Treeview", foreground=self.DISABLED_COLOR)
        clock_font_size = FONT_SIZE_CLOCK_COMPACT if self.compact_mode.get() else FONT_SIZE_CLOCK
        self.style.configure('Clock.TLabel', font=(FONT_FAMILY_UI, clock_font_size, 'bold'), foreground=self.TEXT_COLOR, background=self.BG_COLOR)
        self.style.configure('Status.TLabel', font=(FONT_FAMILY_UI, FONT_SIZE_LARGE), background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('WorldClockTime.TLabel', font=(FONT_FAMILY_UI, FONT_SIZE_XLARGE), background=self.FRAME_BG, foreground=self.TEXT_COLOR)
        self.style.configure('WorldClockZone.TLabel', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), background=self.FRAME_BG, foreground=self.TEXT_SECONDARY)
        self.style.configure('CalendarDate.TLabel', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), background=self.BG_COLOR, foreground=self.TEXT_SECONDARY)

    def apply_theme_to_widgets(self, widget):
        bg_color = self.BG_COLOR
        fg_color = self.TEXT_COLOR
        try:
             if isinstance(widget, (tk.Toplevel, tk.Frame, tk.LabelFrame, tk.Label, tk.Radiobutton, tk.Checkbutton)):
                  widget.configure(background=bg_color)
                  if not isinstance(widget, (tk.Toplevel, tk.Frame, tk.LabelFrame)):
                      try: 
                          widget.configure(foreground=fg_color)
                      except tk.TclError: 
                          pass
             for child in widget.winfo_children(): 
                 self.apply_theme_to_widgets(child)
        except tk.TclError: 
            pass
        except Exception as e: 
            print(f"Theme apply err {widget}: {e}")

    def create_widgets(self):
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=10)
        
        self.clock_label = ttk.Label(self.top_frame, textvariable=self.current_time_var, style='Clock.TLabel', anchor=tk.CENTER)
        self.clock_label.pack(pady=(0, 5))
        
        self.format_frame = ttk.Frame(self.top_frame)
        self.format_frame.pack()
        ttk.Radiobutton(self.format_frame, text="12-Hour", variable=self.time_format, value="12h", command=self.time_format_changed).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.format_frame, text="24-Hour", variable=self.time_format, value="24h", command=self.time_format_changed).pack(side=tk.LEFT, padx=10)
        
        self.notebook = ttk.Notebook(self.root, padding="10 5")
        self.notebook.pack(expand=True, fill=tk.BOTH, side=tk.TOP, padx=10, pady=(0, 5))
        
        self.alarm_tab_frame = ttk.Frame(self.notebook, padding="10")
        self.world_clock_tab_frame = ttk.Frame(self.notebook, padding="10")
        self.calendar_tab_frame = ttk.Frame(self.notebook, padding="10")
        
        self.alarm_tab_frame.pack(fill=tk.BOTH, expand=True)
        self.world_clock_tab_frame.pack(fill=tk.BOTH, expand=True)
        self.calendar_tab_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook.add(self.alarm_tab_frame, text=' Alarms ')
        self.notebook.add(self.world_clock_tab_frame, text=' World Clock ')
        self.notebook.add(self.calendar_tab_frame, text=' Calendar ')
        
        self.create_alarm_tab_widgets(self.alarm_tab_frame)
        self.create_world_clock_tab_widgets(self.world_clock_tab_frame)
        self.create_calendar_tab_widgets(self.calendar_tab_frame)
        
        self.bottom_frame = ttk.Frame(self.root, padding="10 5")
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 10))
        
        self.ringing_controls_frame = ttk.Frame(self.bottom_frame)
        self.ringing_status_label = ttk.Label(self.ringing_controls_frame, text="ALARM RINGING!", font=(FONT_FAMILY_UI, FONT_SIZE_LARGE, 'bold'), foreground=self.ERROR_COLOR)
        self.ringing_status_label.pack(pady=5)
        
        ringing_buttons = ttk.Frame(self.ringing_controls_frame)
        ringing_buttons.pack(pady=5)
        self.snooze_button = ttk.Button(ringing_buttons, text=f"Snooze ({self.snooze_duration_var.get()} min)", command=self.snooze_current_alarm, width=15)
        self.snooze_button.pack(side=tk.LEFT, padx=10)
        ttk.Button(ringing_buttons, text="Stop Alarm", command=self.stop_current_alarm, style='Secondary.TButton', width=15).pack(side=tk.LEFT, padx=10)
        
        self.options_frame = ttk.Frame(self.bottom_frame)
        self.options_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM)
        
        self.volume_frame = ttk.Frame(self.options_frame)
        self.volume_frame.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        ttk.Label(self.volume_frame, text="Volume:").pack(side=tk.LEFT)
        ttk.Scale(self.volume_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=self.volume_var, length=150, style='Horizontal.TScale').pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.snooze_frame = ttk.Frame(self.options_frame)
        self.snooze_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(self.snooze_frame, text="Snooze (min):").pack(side=tk.LEFT)
        ttk.Spinbox(self.snooze_frame, from_=1, to=60, width=3, textvariable=self.snooze_duration_var).pack(side=tk.LEFT, padx=5)
        
        self.misc_options_frame = ttk.Frame(self.options_frame)
        self.misc_options_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Checkbutton(self.misc_options_frame, text="Dark Mode", variable=self.theme_mode, onvalue='dark', offvalue='light').pack(anchor=tk.E)
        ttk.Checkbutton(self.misc_options_frame, text="Compact Mode", variable=self.compact_mode).pack(anchor=tk.E)
        ttk.Checkbutton(self.misc_options_frame, text="Minimize to tray", variable=self.close_to_tray_var).pack(anchor=tk.E)

    def create_alarm_tab_widgets(self, parent_frame):
        # Top controls with date picker
        top_controls_frame = ttk.Frame(parent_frame)
        top_controls_frame.pack(pady=(5, 10), fill=tk.X)
        
        # Left side - buttons
        buttons_frame = ttk.Frame(top_controls_frame)
        buttons_frame.pack(side=tk.LEFT, fill=tk.X)
        ttk.Button(buttons_frame, text="Add New Alarm", command=lambda: self.open_add_alarm_dialog(use_date=True)).pack(side=tk.LEFT, padx=5)
        self.edit_button = ttk.Button(buttons_frame, text="Edit Selected", state=tk.DISABLED, command=self.open_edit_alarm_dialog)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ttk.Button(buttons_frame, text="Delete Selected", state=tk.DISABLED, style='Secondary.TButton', command=self.delete_selected_alarm)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        # Right side - date picker
        date_frame = ttk.Frame(top_controls_frame)
        date_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Label(date_frame, text="Filter by date:").pack(side=tk.LEFT, padx=(0, 5))
        self.alarm_date_var = tk.StringVar(value="")
        self.alarm_date_picker = DateEntry(
            date_frame, 
            width=12,
            background=self.ACCENT_COLOR, 
            foreground=self.ACCENT_FG,
            normalbackground=self.FRAME_BG, 
            normalforeground=self.TEXT_COLOR,
            selectbackground=self.ACCENT_COLOR, 
            selectforeground=self.ACCENT_FG,
            borderwidth=2, 
            date_pattern='yyyy-mm-dd', 
            textvariable=self.alarm_date_var
        )
        self.alarm_date_picker.pack(side=tk.LEFT)
        ttk.Button(date_frame, text="Clear", command=self.clear_alarm_date_filter, style='Secondary.TButton', width=5).pack(side=tk.LEFT, padx=5)
        self.alarm_date_var.trace_add("write", self.on_alarm_date_change)
        
        tree_frame = ttk.Frame(parent_frame)
        tree_frame.pack(expand=True, fill=tk.BOTH)
        cols = ("time", "label", "recurrence", "sound", "enabled")
        self.alarm_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')
        self.alarm_tree.heading("time", text="Time")
        self.alarm_tree.heading("label", text="Label")
        self.alarm_tree.heading("recurrence", text="Repeats")
        self.alarm_tree.heading("sound", text="Sound")
        self.alarm_tree.heading("enabled", text="Enabled")
        self.alarm_tree.column("time", width=100, anchor=tk.CENTER)
        self.alarm_tree.column("label", width=170)
        self.alarm_tree.column("recurrence", width=130)
        self.alarm_tree.column("sound", width=130)
        self.alarm_tree.column("enabled", width=60, anchor=tk.CENTER)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.alarm_tree.yview)
        self.alarm_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.alarm_tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.alarm_tree.bind('<<TreeviewSelect>>', self.on_alarm_select)
        self.alarm_tree.tag_configure("ringing", background=self.ERROR_COLOR, foreground='white', font=(FONT_FAMILY_UI, FONT_SIZE_BASE, 'bold'))
        self.alarm_tree.tag_configure("disabled", foreground=self.DISABLED_COLOR)

    def create_world_clock_tab_widgets(self, parent_frame):
        wc_controls_frame = ttk.Frame(parent_frame)
        wc_controls_frame.pack(pady=(5, 10), fill=tk.X)
        ttk.Button(wc_controls_frame, text="Add Timezone", command=self.add_timezone_dialog).pack(side=tk.LEFT, padx=5)
        self.wc_delete_button = ttk.Button(wc_controls_frame, text="Remove Selected", state=tk.DISABLED, style='Secondary.TButton', command=self.remove_selected_timezone)
        self.wc_delete_button.pack(side=tk.LEFT, padx=5)
        
        wc_tree_frame = ttk.Frame(parent_frame)
        wc_tree_frame.pack(expand=True, fill=tk.BOTH)
        wc_cols = ("timezone", "time", "offset")
        self.wc_tree = ttk.Treeview(wc_tree_frame, columns=wc_cols, show='headings', selectmode='browse')
        self.wc_tree.heading("timezone", text="Timezone / City")
        self.wc_tree.heading("time", text="Current Time")
        self.wc_tree.heading("offset", text="UTC Offset")
        self.wc_tree.column("timezone", width=250)
        self.wc_tree.column("time", width=150, anchor=tk.CENTER)
        self.wc_tree.column("offset", width=100, anchor=tk.CENTER)
        
        wc_scrollbar = ttk.Scrollbar(wc_tree_frame, orient=tk.VERTICAL, command=self.wc_tree.yview)
        self.wc_tree.configure(yscrollcommand=wc_scrollbar.set)
        wc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.wc_tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.wc_tree.bind('<<TreeviewSelect>>', self.on_world_clock_select)
        self.wc_tree.tag_configure("WorldClock", background=self.FRAME_BG, foreground=self.TEXT_COLOR)

    def create_calendar_tab_widgets(self, parent_frame):
        # Create a frame to hold the calendar and add alarm button
        calendar_container = ttk.Frame(parent_frame)
        calendar_container.pack(fill="both", expand=True)
        
        # Add a button to create a new alarm directly from the calendar tab
        calendar_controls = ttk.Frame(calendar_container)
        calendar_controls.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(calendar_controls, text="Add Alarm for Selected Date", 
                  command=self.add_alarm_from_calendar).pack(side=tk.LEFT)
        
        # Create the calendar with enhanced visibility for events
        self.calendar = Calendar(
            calendar_container, 
            selectmode='day', 
            showweeknumbers=False, 
            date_pattern='yyyy-mm-dd', 
            background=self.ACCENT_COLOR, 
            foreground=self.ACCENT_FG, 
            headersbackground=self.ACCENT_COLOR, 
            headersforeground=self.ACCENT_FG, 
            normalbackground=self.FRAME_BG, 
            normalforeground=self.TEXT_COLOR, 
            weekendbackground=self.FRAME_BG, 
            weekendforeground=self.TEXT_COLOR, 
            othermonthbackground=self.DISABLED_COLOR, 
            othermonthforeground=self.TEXT_SECONDARY, 
            othermonthwebackground=self.DISABLED_COLOR, 
            othermonthweforeground=self.TEXT_SECONDARY, 
            selectbackground=self.ACCENT_COLOR, 
            selectforeground=self.ACCENT_FG, 
            disabledbackground=self.BG_COLOR, 
            bordercolor=self.BG_COLOR,
            # Make sure events are visible with high contrast colors
            markbackground=self.CAL_BG,
            markforeground=self.CAL_FG
        )
        self.calendar.pack(pady=10, fill="both", expand=True)
        self.calendar.bind("<<CalendarSelected>>", self.on_calendar_select)
        
        self.calendar_info_label = ttk.Label(
            parent_frame, 
            text="Select date.", 
            justify=tk.LEFT, 
            wraplength=parent_frame.winfo_width()-20, 
            style='CalendarDate.TLabel'
        )
        self.calendar_info_label.pack(pady=5, fill=tk.X)
        parent_frame.bind("<Configure>", lambda e: self.calendar_info_label.config(wraplength=e.width-20))
        self.calendar.tag_config(CALENDAR_EVENT_TAG, background=self.CAL_BG, foreground=self.CAL_FG)

    # --- Settings Management ---
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f: 
                    self.settings = json.load(f)
                    print(f"Loaded settings: {self.settings}")
            else: 
                self.settings = {}
        except Exception as e: 
            print(f"Error loading settings: {e}")
            self.settings = {}
            
        self.volume_var.set(self.settings.get('volume', DEFAULT_VOLUME))
        self.snooze_duration_var.set(self.settings.get('snooze_minutes', DEFAULT_SNOOZE_MINUTES))
        self.theme_mode.set(self.settings.get('theme_mode', 'light'))
        self.compact_mode.set(self.settings.get('compact_mode', False))
        
    def save_settings(self):
        try:
            self.settings['volume'] = self.volume_var.get()
            self.settings['snooze_minutes'] = self.snooze_duration_var.get()
            self.settings['theme_mode'] = self.theme_mode.get()
            self.settings['compact_mode'] = self.compact_mode.get()
            
            with open(SETTINGS_FILE, 'w') as f: 
                json.dump(self.settings, f, indent=4)
                print(f"Saved settings: {self.settings}")
        except Exception as e: 
            print(f"Error saving settings: {e}")
            
    def on_volume_change(self, *args):
        print(f"Volume changed: {self.volume_var.get():.2f}")
        self.save_settings()
        
    def on_snooze_change(self, *args):
        new_snooze = self.snooze_duration_var.get()
        if new_snooze < 1: 
            new_snooze = 1
            self.snooze_duration_var.set(1)
            
        print(f"Snooze changed: {new_snooze} min")
        try: 
            self.snooze_button.config(text=f"Snooze ({new_snooze} min)")
        except tk.TclError: 
            pass
        self.save_settings()
        
    def on_theme_change(self, *args):
        print(f"Theme changed: {self.theme_mode.get()}")
        self.root.configure(bg=self.BG_COLOR)
        self.setup_styles()
        self.apply_theme_to_widgets(self.root)
        try: 
            self.calendar.configure(
                background=self.ACCENT_COLOR, 
                foreground=self.ACCENT_FG, 
                headersbackground=self.ACCENT_COLOR, 
                headersforeground=self.ACCENT_FG, 
                normalbackground=self.FRAME_BG, 
                normalforeground=self.TEXT_COLOR, 
                weekendbackground=self.FRAME_BG, 
                weekendforeground=self.TEXT_COLOR, 
                othermonthbackground=self.DISABLED_COLOR, 
                othermonthforeground=self.TEXT_SECONDARY, 
                othermonthwebackground=self.DISABLED_COLOR, 
                othermonthweforeground=self.TEXT_SECONDARY, 
                selectbackground=self.ACCENT_COLOR, 
                selectforeground=self.ACCENT_FG, 
                disabledbackground=self.BG_COLOR, 
                bordercolor=self.BG_COLOR
            )
            self.calendar.tag_config(CALENDAR_EVENT_TAG, background=self.CAL_BG, foreground=self.CAL_FG)
        except AttributeError: 
            pass
        except tk.TclError: 
            pass
        self.save_settings()
        
    def on_compact_mode_change(self, *args):
        self.toggle_compact_mode()
        self.save_settings()
        
    def toggle_compact_mode(self, init=False):
        is_compact = self.compact_mode.get()
        if not init: 
            print(f"Toggling Compact: {is_compact}")
        new_geometry = "600x550" if is_compact else "750x750"
        try: 
            self.root.geometry(new_geometry)
        except tk.TclError: 
            pass
            
        # Update clock font size
        clock_font_size = FONT_SIZE_CLOCK_COMPACT if is_compact else FONT_SIZE_CLOCK
        self.style.configure('Clock.TLabel', font=(FONT_FAMILY_UI, clock_font_size, 'bold'))
        try: 
            self.clock_label.configure(style='Clock.TLabel')
        except (AttributeError, tk.TclError): 
            pass
            
        # Adjust padding for compact mode
        top_padding = 5 if is_compact else 10
        nb_padding = "5 2" if is_compact else "10 5"
        bottom_padding = "5 2" if is_compact else "10 5"
        options_padding = 2 if is_compact else 5
        
        try: 
            self.top_frame.configure(padding=top_padding)
            self.notebook.configure(padding=nb_padding)
            self.bottom_frame.configure(padding=bottom_padding)
            self.options_frame.configure(pady=options_padding)
        except (AttributeError, tk.TclError): 
            pass
        
        # Adjust UI elements for compact mode
        try:
            # Make sure all tabs are visible regardless of compact mode
            # We no longer hide tabs in compact mode to ensure all functionality is accessible
            
            # Just adjust the UI proportions for compact mode
            
            # Adjust tree column widths for compact mode
            if hasattr(self, 'alarm_tree'):
                if is_compact:
                    self.alarm_tree.column("time", width=80)
                    self.alarm_tree.column("label", width=140)
                    self.alarm_tree.column("recurrence", width=100)
                    self.alarm_tree.column("sound", width=100)
                    self.alarm_tree.column("enabled", width=50)
                else:
                    self.alarm_tree.column("time", width=100)
                    self.alarm_tree.column("label", width=170)
                    self.alarm_tree.column("recurrence", width=130)
                    self.alarm_tree.column("sound", width=130)
                    self.alarm_tree.column("enabled", width=60)
        except (IndexError, tk.TclError, AttributeError): 
            pass

    # --- Data Loading/Saving ---
    def load_alarms(self):
        try:
            if os.path.exists(ALARMS_FILE):
                with open(ALARMS_FILE, 'r') as f: 
                    alarms_data = json.load(f)
                if isinstance(alarms_data, list): 
                    with self.alarm_lock: 
                        self.alarms = alarms_data
                        print(f"Loaded {len(self.alarms)} alarms.")
                else: 
                    print(f"Err: Invalid {ALARMS_FILE}")
                    self.alarms = []
            else: 
                print(f"{ALARMS_FILE} not found.")
                self.alarms = []
        except Exception as e: 
            print(f"Err loading alarms: {e}")
            self.alarms = []
            
    def save_alarms(self):
        try:
            with self.alarm_lock: 
                alarms_to_save = list(self.alarms)
            with open(ALARMS_FILE, 'w') as f: 
                json.dump(alarms_to_save, f, indent=4)
                print(f"Saved {len(alarms_to_save)} alarms.")
        except Exception as e: 
            print(f"Err saving alarms: {e}")
            messagebox.showerror("Save Err", f"Could not save alarms: {e}")
            
    def load_world_clocks(self):
        try:
            if os.path.exists(WORLD_CLOCKS_FILE):
                with open(WORLD_CLOCKS_FILE, 'r') as f: 
                    clocks_data = json.load(f)
                if isinstance(clocks_data, list): 
                    valid_clocks = [tz for tz in clocks_data if tz in pytz.all_timezones_set]
                    with self.world_clock_lock: 
                        self.world_clocks = valid_clocks
                        print(f"Loaded {len(self.world_clocks)} world clocks.")
                else: 
                    print(f"Err: Invalid {WORLD_CLOCKS_FILE}")
                    self._set_default_world_clocks()
            else: 
                self._set_default_world_clocks()
        except Exception as e: 
            print(f"Err loading world clocks: {e}")
            self._set_default_world_clocks()
            
    def _set_default_world_clocks(self):
         with self.world_clock_lock:
              if DEFAULT_WORLD_CLOCK in pytz.all_timezones_set and DEFAULT_WORLD_CLOCK not in self.world_clocks: 
                  self.world_clocks = [DEFAULT_WORLD_CLOCK]
              else: 
                  self.world_clocks = []
                  
    def save_world_clocks(self):
        try:
            with self.world_clock_lock: 
                clocks_to_save = list(self.world_clocks)
            with open(WORLD_CLOCKS_FILE, 'w') as f: 
                json.dump(clocks_to_save, f, indent=4)
                print(f"Saved {len(clocks_to_save)} world clocks.")
        except Exception as e: 
            print(f"Err saving world clocks: {e}")
            messagebox.showerror("Save Err", f"Could not save clocks: {e}")

    # --- Alarm Data Management ---
    def add_alarm(self, alarm_data):
        with self.alarm_lock: 
            alarm_data['id'] = str(uuid.uuid4())
            alarm_data.setdefault('enabled', True)
            alarm_data.setdefault('snooze_until', None)
            alarm_data.setdefault('last_triggered_day', None)
            self.alarms.append(alarm_data)
        self.update_alarm_list_display()
        self.update_calendar_events()
        self.save_alarms()
        
    def update_alarm(self, alarm_id, updated_data):
        with self.alarm_lock:
            for i, alarm in enumerate(self.alarms):
                if alarm.get('id') == alarm_id: 
                    orig = {'id': alarm.get('id')}
                    
                    # Check if this is an edit to a future time
                    old_hour, old_minute = alarm.get('hour', 0), alarm.get('minute', 0)
                    new_hour, new_minute = updated_data.get('hour', 0), updated_data.get('minute', 0)
                    
                    # Reset alarm state when time or date is changed
                    reset_state = (old_hour != new_hour or old_minute != new_minute or 
                                  alarm.get('recurrence_type') != updated_data.get('recurrence_type') or
                                  alarm.get('specific_date') != updated_data.get('specific_date'))
                    
                    # Update the alarm with new data
                    self.alarms[i] = updated_data
                    self.alarms[i].update(orig)
                    
                    # Reset alarm state if time or date changed
                    if reset_state:
                        self.alarms[i]['snooze_until'] = None
                        self.alarms[i]['last_triggered_day'] = None
                        print(f"Reset alarm state for {alarm_id} due to time/date change")
                    
                    self.alarms[i].setdefault('enabled', True)
                    print(f"Updated {alarm_id}")
                    break
            else: 
                print(f"Err: Cannot find {alarm_id}")
                return
                
        # Stop any currently ringing alarm that was edited
        if alarm_id in self.ringing_alarms: 
            print(f"Stopping edited {alarm_id}")
            self._stop_sound(alarm_id)
            self.update_ringing_ui()
            
        self.update_alarm_list_display()
        self.update_calendar_events()
        self.save_alarms()
        
    def delete_alarm(self, alarm_id):
         with self.alarm_lock:
            if alarm_id in self.ringing_alarms: 
                self._stop_sound(alarm_id)
            self.alarms = [a for a in self.alarms if a.get('id') != alarm_id]
         self.update_alarm_list_display()
         self.update_calendar_events()
         self.edit_button.config(state=tk.DISABLED)
         self.delete_button.config(state=tk.DISABLED)
         self.save_alarms()
         
    def delete_selected_alarm(self):
        selected_item = self.alarm_tree.focus()
        if not selected_item: 
            return messagebox.showwarning("No Selection", "Select alarm.")
        alarm_id = self.alarm_tree.item(selected_item, 'values')[-1]
        if messagebox.askyesno("Confirm Deletion", f"Delete alarm '{self.alarm_tree.item(selected_item, 'values')[1]}'?"): 
            self.delete_alarm(alarm_id)
            
    def clear_alarm_date_filter(self):
        self.alarm_date_var.set("")
        self.update_alarm_list_display()
        
    def on_alarm_date_change(self, *args):
        self.update_alarm_list_display()
        
    def update_alarm_list_display(self):
        if threading.current_thread() != threading.main_thread():
            try: 
                self.root.after(0, self.update_alarm_list_display)
            except tk.TclError: 
                pass
            return
        
        selected_iid = self.alarm_tree.focus()
        try:
            for item in self.alarm_tree.get_children(): 
                self.alarm_tree.delete(item)
                
            # Get filter date if set
            filter_date = self.alarm_date_var.get() if hasattr(self, 'alarm_date_var') else ""
                
            with self.alarm_lock:
                # First sort alarms by time
                sorted_alarms = sorted(self.alarms, key=lambda x: (x.get('hour', 0), x.get('minute', 0)))
                
                # Apply date filter if set
                if filter_date:
                    filtered_alarms = []
                    for alarm in sorted_alarms:
                        # Include alarms with matching specific date
                        if alarm.get('recurrence_type') == RECURRENCE_SPECIFIC_DATE and alarm.get('specific_date') == filter_date:
                            filtered_alarms.append(alarm)
                            continue
                            
                        # For recurring alarms, check if they occur on the filter date
                        filter_date_obj = datetime.datetime.strptime(filter_date, "%Y-%m-%d").date()
                        weekday = filter_date_obj.weekday()
                        
                        if alarm.get('recurrence_type') == RECURRENCE_DAILY:
                            filtered_alarms.append(alarm)
                        elif alarm.get('recurrence_type') == RECURRENCE_WEEKDAYS and weekday in WEEKDAYS:
                            filtered_alarms.append(alarm)
                        elif alarm.get('recurrence_type') == RECURRENCE_WEEKENDS and weekday in WEEKENDS:
                            filtered_alarms.append(alarm)
                        elif alarm.get('recurrence_type') == "Specific Days" and weekday in alarm.get('recurrence_days', []):
                            filtered_alarms.append(alarm)
                    
                    # Use filtered alarms
                    sorted_alarms = filtered_alarms
                for alarm in sorted_alarms:
                    alarm_id = alarm.get('id', '')
                    hour, minute = alarm.get('hour', 0), alarm.get('minute', 0)
                    label = alarm.get('label', 'No Label')
                    sound_path = alarm.get('sound_file', '')
                    sound_display = os.path.basename(sound_path) if sound_path and not sound_path.startswith("builtin:") else (sound_path.split(":", 1)[1].replace('_', ' ') if sound_path else "None")
                    enabled = alarm.get('enabled', False)
                    snooze_until_ts = alarm.get('snooze_until')
                    is_snoozed = False
                    
                    if snooze_until_ts: 
                        snooze_until_dt = datetime.datetime.fromtimestamp(snooze_until_ts)
                        is_snoozed = snooze_until_dt > datetime.datetime.now()
                        
                    display_time = format_alarm_time(hour, minute, self.time_format.get())
                    display_recurrence = get_recurrence_display(alarm)
                    display_enabled = "Yes" if enabled else "No"
                    tags = ["disabled"] if not enabled else []
                    current_label = label
                    
                    if alarm_id in self.ringing_alarms: 
                        tags.append("ringing")
                    if is_snoozed: 
                        current_label += f" (Snoozed until {snooze_until_dt.strftime('%H:%M')})"
                        
                    values = (display_time, current_label, display_recurrence, sound_display, display_enabled, alarm_id)
                    self.alarm_tree.insert('', tk.END, iid=alarm_id, values=values, tags=tuple(tags))
                    
            if selected_iid and self.alarm_tree.exists(selected_iid): 
                self.alarm_tree.focus(selected_iid)
                self.alarm_tree.selection_set(selected_iid)
            else: 
                self.on_alarm_select()
        except tk.TclError: 
            pass
            
    def on_alarm_select(self, event=None):
        try: 
            state = tk.NORMAL if self.alarm_tree.focus() else tk.DISABLED
            self.edit_button.config(state=state)
            self.delete_button.config(state=state)
        except tk.TclError: 
            pass

    # --- World Clock Management ---
    def add_timezone_dialog(self):
        dialog = TimezoneDialog(self.root, "Add Timezone", pytz.common_timezones, current_theme=self.theme_mode.get())
        if dialog.result:
            tz_name = dialog.result
            with self.world_clock_lock:
                if tz_name not in self.world_clocks: 
                    self.world_clocks.append(tz_name)
                    self.world_clocks.sort()
                else: 
                    messagebox.showinfo("Already Added", f"'{tz_name}' added.", parent=self.root)
                    return
            self.update_world_clocks_display()
            self.save_world_clocks()
            
    def remove_selected_timezone(self):
        selected_item = self.wc_tree.focus()
        if not selected_item: 
            return messagebox.showwarning("No Selection", "Select timezone.")
        tz_name = self.wc_tree.item(selected_item, 'values')[0]
        if messagebox.askyesno("Confirm Removal", f"Remove '{tz_name}'?"):
             with self.world_clock_lock:
                 if tz_name in self.world_clocks: 
                     self.world_clocks.remove(tz_name)
             self.update_world_clocks_display()
             self.wc_delete_button.config(state=tk.DISABLED)
             self.save_world_clocks()
             
    def update_world_clocks_display(self):
        if not self.running: 
            return
            
        if threading.current_thread() != threading.main_thread():
            try: 
                self.root.after(0, self.update_world_clocks_display)
            except tk.TclError: 
                pass
            return
            
        selected_iid = self.wc_tree.focus()
        try:
            for item in self.wc_tree.get_children(): 
                self.wc_tree.delete(item)
                
            utc_now = datetime.datetime.now(pytz.utc)
            use_12hr = self.time_format.get() == "12h"
            time_fmt = "%I:%M:%S %p" if use_12hr else "%H:%M:%S"
            
            with self.world_clock_lock:
                 sorted_clocks = sorted(self.world_clocks)
                 for tz_name in sorted_clocks:
                     try:
                         tz = pytz.timezone(tz_name)
                         local_time = utc_now.astimezone(tz)
                         time_str = local_time.strftime(time_fmt)
                         offset_str = local_time.strftime("%Z %z")
                         values = (tz_name, time_str, offset_str)
                         self.wc_tree.insert('', tk.END, iid=tz_name, values=values, tags=("WorldClock",))
                     except Exception as e: 
                         print(f"TZ Error {tz_name}: {e}")
                         
            if selected_iid and self.wc_tree.exists(selected_iid): 
                self.wc_tree.focus(selected_iid)
                self.wc_tree.selection_set(selected_iid)
            else: 
                self.on_world_clock_select()
        except tk.TclError: 
            pass
            
        if self.root and self.root.winfo_exists():
             try: 
                 self.root.after(1000, self.update_world_clocks_display)
             except tk.TclError: 
                 pass
                 
    def on_world_clock_select(self, event=None):
        try: 
            self.wc_delete_button.config(state=tk.NORMAL if self.wc_tree.focus() else tk.DISABLED)
        except tk.TclError: 
            pass

    # --- Calendar Management ---
    def update_calendar_events(self):
        if threading.current_thread() != threading.main_thread():
             try: 
                 self.root.after(0, self.update_calendar_events)
                 return
             except tk.TclError: 
                 return
                 
        try:
             if not hasattr(self, 'calendar'): 
                 return
                 
             # Clear all existing calendar events
             self.calendar.calevent_remove('all')
             events_by_date = defaultdict(list)
             today = datetime.date.today()
             lookahead_days = 60
             relevant_dates = set()
             
             with self.alarm_lock:
                 for alarm in self.alarms:
                     if not alarm.get('enabled'): 
                         continue
                         
                     alarm_info = f"{format_alarm_time(alarm.get('hour',0), alarm.get('minute',0), self.time_format.get())} - {alarm.get('label', 'Alarm')}"
                     rec_type = alarm.get('recurrence_type')
                     spec_date_str = alarm.get('specific_date')
                     
                     # Handle specific date alarms
                     if rec_type == RECURRENCE_SPECIFIC_DATE and spec_date_str:
                         try: 
                             alarm_date = datetime.datetime.strptime(spec_date_str, "%Y-%m-%d").date()
                             if alarm_date >= today: 
                                 events_by_date[alarm_date].append(alarm_info)
                                 relevant_dates.add(alarm_date)
                         except ValueError: 
                             continue
                     # Handle one-time alarms that haven't triggered yet
                     elif rec_type == RECURRENCE_ONCE:
                         # For one-time alarms, add them to today if they haven't triggered yet
                         if not alarm.get('last_triggered_day'):
                             events_by_date[today].append(alarm_info)
                             relevant_dates.add(today)
                     # Handle recurring alarms
                     else:
                         days_to_check = set(range(7)) if rec_type == RECURRENCE_DAILY else (set(WEEKDAYS) if rec_type == RECURRENCE_WEEKDAYS else (set(WEEKENDS) if rec_type == RECURRENCE_WEEKENDS else (set(alarm.get('recurrence_days',[])) if rec_type == "Specific Days" else set())))
                         if days_to_check:
                             for i in range(lookahead_days): 
                                 check_date = today + datetime.timedelta(days=i)
                                 if check_date.weekday() in days_to_check: 
                                     events_by_date[check_date].append(alarm_info)
                                     relevant_dates.add(check_date)
                                     
             # Create calendar events for each relevant date
             for date_obj in relevant_dates: 
                 # Use a more visible text for the event
                 event_text = ", ".join(events_by_date[date_obj])
                 event_id = self.calendar.calevent_create(date_obj, text=event_text, tags=[CALENDAR_EVENT_TAG])
                 
                 # Mark the date to make it visually distinct
                 self.calendar.tag_config(CALENDAR_EVENT_TAG, background=self.CAL_BG, foreground=self.CAL_FG)
                 
             print(f"Updated calendar: {len(relevant_dates)} dates with {sum(len(events) for events in events_by_date.values())} alarms.")
             
             # Force calendar to redraw to show the events
             self.calendar.update_idletasks()
        except tk.TclError: 
            pass
        except Exception as e: 
            print(f"Error updating calendar: {e}")
            
    def on_calendar_select(self, event=None):
        try:
            selected_date_str = self.calendar.get_date()
            selected_date = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            alarms_on_date = []
            
            with self.alarm_lock:
                 for alarm in self.alarms:
                     if not alarm.get('enabled'): 
                         continue
                         
                     alarm_info = f"{format_alarm_time(alarm.get('hour',0), alarm.get('minute',0), self.time_format.get())} - {alarm.get('label', 'Alarm')}"
                     rec_type = alarm.get('recurrence_type')
                     spec_date_str = alarm.get('specific_date')
                     matches = False
                     
                     if rec_type == RECURRENCE_SPECIFIC_DATE and spec_date_str == selected_date_str: 
                         matches = True
                     elif rec_type == RECURRENCE_DAILY: 
                         matches = True
                     elif rec_type == RECURRENCE_WEEKDAYS and selected_date.weekday() in WEEKDAYS: 
                         matches = True
                     elif rec_type == RECURRENCE_WEEKENDS and selected_date.weekday() in WEEKENDS: 
                         matches = True
                     elif rec_type == "Specific Days" and selected_date.weekday() in alarm.get('recurrence_days', []): 
                         matches = True
                         
                     if matches: 
                         alarms_on_date.append(alarm_info)
                         
            info_text = f"Alarms for {selected_date.strftime('%a, %b %d')}:\n- " + "\n- ".join(alarms_on_date) if alarms_on_date else f"No alarms for {selected_date.strftime('%a, %b %d')}."
            self.calendar_info_label.config(text=info_text)
            
            # Update the alarm date picker but don't switch tabs
            if hasattr(self, 'alarm_date_var'):
                self.alarm_date_var.set(selected_date_str)
                # Don't switch tabs - stay on calendar tab
        except tk.TclError: 
            pass
        except Exception as e: 
            print(f"Err calendar select: {e}")

    # --- Add/Edit Alarm Dialog ---
    def add_alarm_from_calendar(self):
        """Add a new alarm using the currently selected date in the calendar"""
        if hasattr(self, 'calendar'):
            selected_date = self.calendar.get_date()
            # Create initial data with the selected date
            initial_data = {
                'recurrence_type': RECURRENCE_SPECIFIC_DATE,
                'specific_date': selected_date
            }
            AlarmDialog(self.root, "Add New Alarm", self.add_alarm, 
                       time_format=self.time_format.get(), 
                       initial_data=initial_data,
                       current_theme=self.theme_mode.get())
        
    def open_add_alarm_dialog(self, use_date=True):
        """Open dialog to add a new alarm
        
        Args:
            use_date: If True, include date selection in the dialog
        """
        # Get current date from calendar or alarm date picker
        current_date = None
        if use_date:
            if hasattr(self, 'alarm_date_var') and self.alarm_date_var.get():
                current_date = self.alarm_date_var.get()
            elif hasattr(self, 'calendar') and self.calendar.get_date():
                current_date = self.calendar.get_date()
            else:
                # Default to tomorrow
                current_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                
            # Create initial data with the date
            initial_data = {
                'recurrence_type': RECURRENCE_SPECIFIC_DATE,
                'specific_date': current_date
            }
            AlarmDialog(self.root, "Add New Alarm", self.add_alarm, 
                       time_format=self.time_format.get(),
                       initial_data=initial_data,
                       current_theme=self.theme_mode.get())
        else:
            # Standard alarm without date
            AlarmDialog(self.root, "Add New Alarm", self.add_alarm, 
                       time_format=self.time_format.get(), 
                       current_theme=self.theme_mode.get())
        
    def open_edit_alarm_dialog(self):
        selected_iid = self.alarm_tree.focus()
        if not selected_iid: 
            return messagebox.showwarning("No Selection", "Select alarm.")
            
        with self.alarm_lock: 
            alarm_data = next((a for a in self.alarms if a.get('id') == selected_iid), None)
            
        if alarm_data: 
            AlarmDialog(self.root, "Edit Alarm", self.update_alarm, time_format=self.time_format.get(), initial_data=alarm_data.copy(), current_theme=self.theme_mode.get())
        else: 
            messagebox.showerror("Error", "Alarm data not found.")

    # --- Core Clock and Alarm Logic ---
    def time_format_changed(self):
        self.update_local_clock_display_only()
        self.update_alarm_list_display()
        self.update_world_clocks_display()
        
    def update_local_clock(self):
        if not self.running: 
            return
            
        now = datetime.datetime.now()
        try: 
            fmt = "%I:%M:%S %p" if self.time_format.get() == "12h" else "%H:%M:%S"
            self.current_time_var.set(now.strftime(fmt))
        except Exception as e: 
            print(f"Local clock update error: {e}")
            
        if self.root and self.root.winfo_exists():
            try: 
                self.root.after(1000, self.update_local_clock)
            except tk.TclError: 
                pass
                
    def update_local_clock_display_only(self): 
        self.update_local_clock()
        
    def check_alarm_loop(self):
         while self.running:
            now = datetime.datetime.now()
            current_day_index = now.weekday()
            current_date_str = now.strftime("%Y-%m-%d")
            alarms_to_trigger, alarms_to_unsnooze = [], []
            
            with self.alarm_lock:
                for alarm in self.alarms:
                    alarm_id = alarm.get('id')
                    snooze_until_ts = alarm.get('snooze_until')
                    
                    if not alarm.get('enabled') or alarm_id in self.ringing_alarms: 
                        continue
                        
                    if snooze_until_ts and now < datetime.datetime.fromtimestamp(snooze_until_ts): 
                        continue
                    elif snooze_until_ts: 
                        alarms_to_unsnooze.append(alarm_id)
                        alarm['snooze_until'] = None
                        
                    alarm_hour, alarm_minute = alarm.get('hour', -1), alarm.get('minute', -1)
                    if now.hour != alarm_hour or now.minute != alarm_minute or now.second != 0: 
                        continue
                        
                    recurrence_type = alarm.get('recurrence_type', RECURRENCE_ONCE)
                    last_triggered = alarm.get('last_triggered_day')
                    specific_date = alarm.get('specific_date')
                    
                    should_trigger = (recurrence_type == RECURRENCE_SPECIFIC_DATE and specific_date == current_date_str and last_triggered != current_date_str) or \
                                     (recurrence_type == RECURRENCE_ONCE and not specific_date and last_triggered != current_date_str) or \
                                     (recurrence_type == RECURRENCE_DAILY) or \
                                     (recurrence_type == RECURRENCE_WEEKDAYS and current_day_index in WEEKDAYS) or \
                                     (recurrence_type == RECURRENCE_WEEKENDS and current_day_index in WEEKENDS) or \
                                     (recurrence_type == "Specific Days" and current_day_index in alarm.get('recurrence_days', []))
                                     
                    if last_triggered == current_date_str and recurrence_type in [RECURRENCE_ONCE, RECURRENCE_SPECIFIC_DATE]: 
                        should_trigger = False
                        
                    if should_trigger: 
                        alarms_to_trigger.append(alarm_id)
                        alarm['last_triggered_day'] = current_date_str
                        
            if alarms_to_trigger or alarms_to_unsnooze:
                ids_to_action = list(set(alarms_to_trigger + alarms_to_unsnooze))
                if self.root and self.root.winfo_exists():
                    try: 
                        self.root.after(0, lambda ids=ids_to_action: self.trigger_multiple_alarms(ids))
                    except tk.TclError: 
                        pass
                        
            time.sleep(0.5)

    def trigger_multiple_alarms(self, alarm_ids):
        if not self.root or not self.root.winfo_exists(): 
            return
            
        first_newly_ringing_id = None
        with self.alarm_lock:
             for alarm_id in alarm_ids:
                 alarm_data = next((a for a in self.alarms if a.get('id') == alarm_id), None)
                 if alarm_id not in self.ringing_alarms and alarm_data and alarm_data.get('enabled'):
                    sound_identifier = alarm_data.get('sound_file')
                    channel, fade_job = self._play_sound_with_fade(sound_identifier)
                    if channel is not None: 
                        self.ringing_alarms[alarm_id] = {'channel': channel, 'fade_job': fade_job}
                        first_newly_ringing_id = first_newly_ringing_id or alarm_id
                    else: 
                        print(f"Failed sound for alarm {alarm_id}")
                    self.send_notification(alarm_data)
                    
        try: 
            self.update_ringing_ui()
        except tk.TclError: 
            pass
            
        if first_newly_ringing_id: 
            self.currently_handled_ringing_id = first_newly_ringing_id
            self.show_window()

    def _resolve_sound_path(self, identifier):
        if not identifier: 
            return None
            
        if identifier.startswith("builtin:"):
             sound_name = identifier.split(":", 1)[1]
             path = resource_path(os.path.join(DEFAULT_SOUNDS_DIR, sound_name))
             if not os.path.exists(path): 
                 print(f"Built-in sound missing: {path}")
                 return None
             return path
        elif os.path.exists(identifier): 
            return identifier
        else: 
            print(f"Sound path missing: {identifier}")
            return None

    def _play_sound_with_fade(self, sound_identifier):
        sound_path = self._resolve_sound_path(sound_identifier)
        if not sound_path or not pygame.mixer.get_init(): 
            return None, None
            
        target_volume = self.volume_var.get()
        try:
            sound = pygame.mixer.Sound(sound_path)
            channel = pygame.mixer.find_channel(True)
            if channel: 
                print(f"Starting {sound_path} on {channel} with fade...")
                channel.set_volume(0)
                channel.play(sound, loops=-1)
                fade_job_id = self._schedule_fade_in(channel, target_volume, FADE_IN_DURATION_MS, FADE_IN_STEPS)
                return channel, fade_job_id
            else: 
                print("No free channels.")
                return None, None
        except Exception as e: 
            print(f"Sound prepare error {sound_path}: {e}")
            messagebox.showerror("Sound Error", f"Could not play:\n{os.path.basename(sound_path)}\n{e}")
            return None, None

    # FIXED: This method has been corrected to avoid modifying dictionary during iteration
    def _schedule_fade_in(self, channel, target_volume, duration_ms, steps):
        if not self.root or not self.root.winfo_exists(): 
            return None
            
        step_delay = max(1, duration_ms // steps)
        volume_step = target_volume / steps
        current_step = 0
        
        def fade_step(current_step):
            try:
                if not self.running or not channel.get_busy():
                    print(f"Fade cancelled for {channel}")
                    return
                current_step += 1
                next_volume = min(volume_step * current_step, target_volume)
                channel.set_volume(next_volume)
                
                if current_step < steps:
                    job_id = self.root.after(step_delay, lambda cs=current_step: fade_step(cs))
                    # Update fade job in ringing_alarms without modifying during iteration
                    for alarm_id, info in list(self.ringing_alarms.items()):
                        if info.get('channel') == channel:
                            self.ringing_alarms[alarm_id]['fade_job'] = job_id
                            break  # Found it, stop loop
                else:
                    print(f"Fade complete for {channel}")
                    # Update fade job completion in ringing_alarms
                    for alarm_id, info in list(self.ringing_alarms.items()):
                        if info.get('channel') == channel:
                            self.ringing_alarms[alarm_id]['fade_job'] = None
                            break  # Found it, stop loop
            except tk.TclError:
                print("Error during fade step (window closed?).")
            except Exception as e:
                print(f"Unexpected error in fade_step: {e}")
        
        # Start fade
        try:
            initial_job_id = self.root.after(step_delay, lambda: fade_step(0))
            return initial_job_id
        except tk.TclError:
            print("Error scheduling initial fade step (window closed?).")
            return None

    # FIXED: This method has been corrected to add better error handling
    def _stop_sound(self, alarm_id):
        if alarm_id in self.ringing_alarms:
            ring_info = self.ringing_alarms.pop(alarm_id)
            channel = ring_info.get('channel')
            fade_job_id = ring_info.get('fade_job')
            
            if fade_job_id and self.root and self.root.winfo_exists():
                try:
                    self.root.after_cancel(fade_job_id)
                    print(f"Cancelled fade job {fade_job_id}")
                except tk.TclError:
                    # Job might already be invalid or window closing
                    print(f"Ignoring TclError cancelling fade job {fade_job_id}")
                except Exception as e:
                    # Catch other potential errors during cancellation
                    print(f"Error cancelling fade job {fade_job_id}: {e}")
            
            if channel and channel.get_busy():
                print(f"Stopping sound on {channel}")
                try:
                    channel.stop()
                except Exception as e:
                    print(f"Error stopping channel: {e}")
                    
            if self.currently_handled_ringing_id == alarm_id:
                self.currently_handled_ringing_id = next(iter(self.ringing_alarms.keys()), None)

    def send_notification(self, alarm_data):
        try: 
            # Get current time for the notification
            now = datetime.datetime.now()
            current_time = format_alarm_time(now.hour, now.minute, self.time_format.get())
            
            # Get alarm details
            alarm_time = format_alarm_time(alarm_data.get('hour',0), alarm_data.get('minute',0), self.time_format.get())
            label = alarm_data.get('label', '')
            
            # Create notification message with current time
            message = f"Alarm {alarm_time}" + (f": {label}" if label else "")
            title = f"ALARM! ({current_time})"
            
            notification.notify(
                title=title, 
                message=message, 
                app_name='Enhanced Alarm Clock', 
                app_icon=self.icon_path, 
                timeout=15
            )
        except Exception as e: 
            print(f"Notify error: {e}")

    def update_ringing_ui(self):
        if threading.current_thread() != threading.main_thread():
            try: 
                self.root.after(0, self.update_ringing_ui)
            except tk.TclError: 
                pass
            return
            
        try: 
            self.update_alarm_list_display()
        except tk.TclError: 
            pass
            
        try:
            if self.ringing_alarms:
                if not self.ringing_controls_frame.winfo_ismapped(): 
                    self.ringing_controls_frame.pack(side=tk.TOP, pady=5, fill=tk.X, before=self.options_frame)
                first_ringing_id = self.currently_handled_ringing_id
                status_text = "ALARMS RINGING!"
                
                if first_ringing_id:
                     with self.alarm_lock: 
                         alarm_data = next((a for a in self.alarms if a.get('id') == first_ringing_id), None)
                     if alarm_data: 
                         d_time = format_alarm_time(alarm_data.get('hour',0), alarm_data.get('minute',0), self.time_format.get())
                         d_label = alarm_data.get('label','')
                         status_text = f"ALARM: {d_time}" + (f" - {d_label}" if d_label else "")
                         
                self.ringing_status_label.config(text=status_text)
                self.snooze_button.config(text=f"Snooze ({self.snooze_duration_var.get()} min)")
            else:
                if self.ringing_controls_frame.winfo_ismapped(): 
                    self.ringing_controls_frame.pack_forget()
                self.currently_handled_ringing_id = None
        except tk.TclError: 
            pass

    def snooze_current_alarm(self):
        alarm_id = self.currently_handled_ringing_id
        if not alarm_id: 
            print("Snooze called but no alarm handled.")
            return
            
        try: 
            snooze_minutes = self.snooze_duration_var.get()
            if snooze_minutes < 1: 
                print("Warning: Invalid snooze (<1), default 1.")
                snooze_minutes = 1
        except tk.TclError: 
            print("Error getting snooze duration, using default.")
            snooze_minutes = DEFAULT_SNOOZE_MINUTES
            
        print(f"Snoozing {alarm_id} for {snooze_minutes}m")
        snooze_until = datetime.datetime.now() + datetime.timedelta(minutes=snooze_minutes)
        snooze_until_ts = snooze_until.timestamp()
        
        with self.alarm_lock:
             for alarm in self.alarms:
                 if alarm.get('id') == alarm_id: 
                     # Set snooze timestamp
                     alarm['snooze_until'] = snooze_until_ts
                     # Reset last_triggered_day to ensure it will trigger again after snooze
                     if alarm.get('recurrence_type') in [RECURRENCE_ONCE, RECURRENCE_SPECIFIC_DATE]:
                         alarm['last_triggered_day'] = None
                     break
             self._stop_sound(alarm_id)
             
        # Show notification about snooze
        try:
            snooze_time = snooze_until.strftime("%H:%M")
            notification.notify(
                title='Alarm Snoozed', 
                message=f"Alarm snoozed until {snooze_time}", 
                app_name='Enhanced Alarm Clock', 
                app_icon=self.icon_path, 
                timeout=5
            )
        except Exception as e:
            print(f"Snooze notification error: {e}")
             
        self.save_alarms()
        self.update_ringing_ui()

    def stop_current_alarm(self):
        alarm_id = self.currently_handled_ringing_id
        if not alarm_id: 
            return
            
        print(f"Stopping {alarm_id}")
        with self.alarm_lock:
             for alarm in self.alarms:
                if alarm.get('id') == alarm_id: 
                    alarm['snooze_until'] = None
                    break
             self._stop_sound(alarm_id)
             
        self.save_alarms()
        self.update_ringing_ui()

    # --- System Tray & Window Management ---
    def setup_tray_icon(self):
        try: 
            image = Image.open(self.icon_path)
            menu = (
                pystray.MenuItem('Show', self.show_window, default=True),
                pystray.MenuItem('Quit', self.quit_application)
            )
            self.tray_icon = pystray.Icon("alarm_clock", image, "Enhanced Alarm Clock", menu)
            self.tray_thread = threading.Thread(target=self.run_tray_icon, daemon=True)
            self.tray_thread.start()
        except Exception as e: 
            print(f"Tray setup error: {e}")
            
    def run_tray_icon(self):
        if self.tray_icon: 
            print("Starting tray...")
            self.tray_icon.run()
            print("Tray stopped.")
            
    def show_window(self):
        try: 
            self.root.after(0, self._show_window_action)
        except tk.TclError: 
            pass
            
    def _show_window_action(self):
         if self.root and self.root.winfo_exists():
            try: 
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except tk.TclError as e: 
                print(f"Show window error: {e}")
                
    def hide_to_tray(self):
         if self.root and self.root.winfo_exists(): 
             self.root.withdraw()
         try: 
             notification.notify(
                 title='Clock Minimized',
                 message='Running in system tray.',
                 app_name='Enhanced Alarm Clock',
                 app_icon=self.icon_path,
                 timeout=5
             )
         except Exception as e: 
             print(f"Hide notify error: {e}")

    # FIXED: This method has been corrected to handle errors better during shutdown
    def quit_application(self):
        print("Quitting...")
        self.running = False
        
        # Stop tray icon
        if hasattr(self, 'tray_icon') and self.tray_icon:
            print("Stopping tray...")
            try:
                self.tray_icon.stop()
                if hasattr(self, 'tray_thread') and self.tray_thread:
                    self.tray_thread.join(0.5)
            except Exception as e:
                print(f"Error stopping tray: {e}")
        
        # Stop all sounds
        print("Stopping sounds...")
        try:
            with self.alarm_lock:
                ringing_ids = list(self.ringing_alarms.keys())
                for aid in ringing_ids:
                    self._stop_sound(aid)
        except Exception as e:
            print(f"Error stopping sounds: {e}")
        
        # Quit pygame
        print("Quitting pygame...")
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            if pygame.get_init():
                pygame.quit()
        except Exception as e:
            print(f"Error quitting pygame: {e}")
        
        # Save data
        print("Saving data...")
        try:
            self.save_settings()
            self.save_alarms()
            self.save_world_clocks()
        except Exception as e:
            print(f"Error during final save: {e}")
        
        # Destroy window
        print("Destroying window...")
        if self.root and hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
            try:
                self.root.after(0, self.root.destroy)
            except tk.TclError:
                print("Error scheduling destroy (already closing?).")
            except Exception as e:
                print(f"Unexpected error during destroy: {e}")
        
        print("Shutdown complete.")

    def on_closing(self):
        if self.close_to_tray_var.get(): 
            self.hide_to_tray()
        else: 
            self.quit_application()


# --- Alarm Add/Edit Dialog Window ---
class AlarmDialog(tk.Toplevel):
    BUILTIN_SOUNDS_PREFIX = "builtin:"
    BROWSE_OPTION = "<Browse for file...>"

    def __init__(self, parent, title, save_callback, time_format="12h", initial_data=None, current_theme='light'):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)
        self.geometry("480x450")
        self.resizable(False, False)

        # Store theme colors locally
        self.BG_COLOR = D_COLOR_BACKGROUND if current_theme == 'dark' else L_COLOR_BACKGROUND
        self.FRAME_BG = D_COLOR_FRAME_BG if current_theme == 'dark' else L_COLOR_FRAME_BG
        self.TEXT_COLOR = D_COLOR_TEXT if current_theme == 'dark' else L_COLOR_TEXT
        self.ACCENT_COLOR = D_COLOR_ACCENT if current_theme == 'dark' else L_COLOR_ACCENT
        self.ACCENT_FG = D_COLOR_ACCENT_FG # Assumed same for both
        self.TEXT_SECONDARY = D_COLOR_TEXT_SECONDARY if current_theme == 'dark' else L_COLOR_TEXT_SECONDARY

        self.configure(bg=self.BG_COLOR) # Apply background

        self.save_callback = save_callback
        self.initial_data = initial_data or {}
        self.result = None
        self.time_format = time_format
        self.hour_var = tk.StringVar()
        self.minute_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.sound_selection_var = tk.StringVar()
        self.sound_filepath = self.initial_data.get('sound_file', None)
        self.enabled_var = tk.BooleanVar(value=self.initial_data.get('enabled', True))
        self.recurrence_type_var = tk.StringVar(value=self.initial_data.get('recurrence_type', RECURRENCE_ONCE))
        self.day_vars = {i: tk.BooleanVar(value=(i in self.initial_data.get('recurrence_days', []))) for i in range(7)}
        self.specific_date_var = tk.StringVar(value=self.initial_data.get('specific_date', ''))

        # Setup styles *locally* using the stored theme colors
        self.style = ttk.Style(self)
        self.style.configure('.', background=self.BG_COLOR, foreground=self.TEXT_COLOR, fieldbackground=self.FRAME_BG)
        self.style.configure('TFrame', background=self.BG_COLOR)
        self.style.configure('TLabel', background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('TCheckbutton', background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('TRadiobutton', background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure('TButton', font=(FONT_FAMILY_UI, FONT_SIZE_BASE, 'bold'), padding=(8, 5), background=self.ACCENT_COLOR, foreground=self.ACCENT_FG)
        self.style.configure('Secondary.TButton', background=self.TEXT_SECONDARY, foreground=self.ACCENT_FG)
        self.style.map('TCombobox', fieldbackground=[('readonly', self.FRAME_BG)])
        self.style.map('TCombobox', selectbackground=[('readonly', self.FRAME_BG)])
        self.style.map('TCombobox', selectforeground=[('readonly', self.TEXT_COLOR)])
        self.style.configure('TSpinbox', fieldbackground=self.FRAME_BG, foreground=self.TEXT_COLOR, arrowcolor=self.TEXT_COLOR)

        self.create_dialog_widgets()
        self.populate_initial_data()
        self.wait_window(self)

    def get_available_sounds(self):
        sounds = [self.BROWSE_OPTION]
        try: 
            sounds_path = resource_path(DEFAULT_SOUNDS_DIR)
            if os.path.isdir(sounds_path): 
                sounds.extend([fname.rsplit('.', 1)[0].replace('_', ' ') for fname in os.listdir(sounds_path) if fname.lower().endswith((".wav", ".ogg", ".mp3"))])
        except Exception as e: 
            print(f"Sound scan error: {e}")
        return sounds
        
    def map_display_to_internal_sound(self, display_name):
        if display_name == self.BROWSE_OPTION: 
            return None
        try: 
            sounds_path = resource_path(DEFAULT_SOUNDS_DIR)
            if os.path.isdir(sounds_path):
                for fname in os.listdir(sounds_path):
                    if fname.lower().endswith((".wav", ".ogg", ".mp3")):
                        if fname.rsplit('.', 1)[0].replace('_', ' ') == display_name: 
                            return f"{self.BUILTIN_SOUNDS_PREFIX}{fname}"
        except Exception as e: 
            print(f"Sound map error {display_name}: {e}")
        print(f"Warn: Cannot map {display_name}.")
        return None

    def create_dialog_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(pady=5, fill=tk.X)
        ttk.Label(time_frame, text="Time:").pack(side=tk.LEFT, padx=(0,5))
        
        # Add AM/PM selection for 12-hour format
        if self.time_format == "12h":
            # For 12-hour format, use 1-12 for hours
            self.ampm_var = tk.StringVar(value="AM")
            ttk.Spinbox(time_frame, from_=1, to=12, width=2, format="%02.0f", textvariable=self.hour_var).pack(side=tk.LEFT)
            ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)
            ttk.Spinbox(time_frame, from_=0, to=59, width=2, format="%02.0f", textvariable=self.minute_var).pack(side=tk.LEFT)
            ttk.Label(time_frame, text=" ").pack(side=tk.LEFT, padx=2)
            ampm_frame = ttk.Frame(time_frame)
            ampm_frame.pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(ampm_frame, text="AM", variable=self.ampm_var, value="AM").pack(side=tk.LEFT)
            ttk.Radiobutton(ampm_frame, text="PM", variable=self.ampm_var, value="PM").pack(side=tk.LEFT)
        else:
            # For 24-hour format, use 0-23 for hours
            ttk.Spinbox(time_frame, from_=0, to=23, width=2, format="%02.0f", textvariable=self.hour_var).pack(side=tk.LEFT)
            ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)
            ttk.Spinbox(time_frame, from_=0, to=59, width=2, format="%02.0f", textvariable=self.minute_var).pack(side=tk.LEFT)
        
        label_frame = ttk.Frame(main_frame)
        label_frame.pack(pady=5, fill=tk.X)
        ttk.Label(label_frame, text="Label:").pack(side=tk.LEFT, padx=(0,5))
        ttk.Entry(label_frame, textvariable=self.label_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        sound_frame = ttk.Frame(main_frame)
        sound_frame.pack(pady=5, fill=tk.X)
        ttk.Label(sound_frame, text="Sound:").pack(side=tk.LEFT, padx=(0,5))
        available_sounds = self.get_available_sounds()
        self.sound_combo = ttk.Combobox(sound_frame, textvariable=self.sound_selection_var, values=available_sounds, state='readonly', width=38)
        self.sound_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.sound_combo.bind("<<ComboboxSelected>>", self.on_sound_select)
        
        recur_frame = ttk.LabelFrame(main_frame, text="Recurrence", padding="10")
        recur_frame.pack(pady=10, fill=tk.X)
        recur_options = [RECURRENCE_ONCE, RECURRENCE_DAILY, RECURRENCE_WEEKDAYS, RECURRENCE_WEEKENDS, "Specific Days", RECURRENCE_SPECIFIC_DATE]
        option_frame = ttk.Frame(recur_frame)
        option_frame.pack(fill=tk.X)
        self.recur_combobox = ttk.Combobox(option_frame, textvariable=self.recurrence_type_var, values=recur_options, state='readonly')
        self.recur_combobox.pack(fill=tk.X)
        self.recur_combobox.bind("<<ComboboxSelected>>", self.on_recurrence_change)
        
        self.days_frame = ttk.Frame(recur_frame)
        for i, day_name in enumerate(DAY_NAMES):
            ttk.Checkbutton(self.days_frame, text=day_name, variable=self.day_vars[i]).pack(side=tk.LEFT, padx=3, pady=5)
            
        self.date_frame = ttk.Frame(recur_frame)
        ttk.Label(self.date_frame, text="Date:").pack(side=tk.LEFT, padx=(0,5))
        
        # Apply theme colors to DateEntry
        self.date_entry = DateEntry(
            self.date_frame, 
            width=12,
            background=self.ACCENT_COLOR, 
            foreground=self.ACCENT_FG, # Header
            normalbackground=self.FRAME_BG, 
            normalforeground=self.TEXT_COLOR, # Normal days
            selectbackground=self.ACCENT_COLOR, 
            selectforeground=self.ACCENT_FG, # Selected day
            borderwidth=2, 
            date_pattern='yyyy-mm-dd', 
            textvariable=self.specific_date_var
        )
        self.date_entry.pack(side=tk.LEFT)
        
        ttk.Checkbutton(main_frame, text="Enable this alarm", variable=self.enabled_var).pack(pady=5, anchor=tk.W)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(15,5), fill=tk.X)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="Save", command=self.save).grid(row=0, column=0, sticky=tk.E, padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.destroy, style='Secondary.TButton').grid(row=0, column=1, sticky=tk.W, padx=10)
        
        self.on_recurrence_change()

    def populate_initial_data(self):
        if not self.initial_data:
            now = datetime.datetime.now() + datetime.timedelta(minutes=1)
            
            # Set hour based on time format
            if self.time_format == "12h":
                # Convert to 12-hour format
                hour_12 = now.hour % 12
                if hour_12 == 0:
                    hour_12 = 12  # 0 hour in 12-hour format is 12
                self.hour_var.set(f"{hour_12:02}")
                # Set AM/PM
                self.ampm_var.set("PM" if now.hour >= 12 else "AM")
            else:
                self.hour_var.set(f"{now.hour:02}")
                
            self.minute_var.set(f"{now.minute:02}")
            available = self.get_available_sounds()
            default_sound = available[1] if len(available) > 1 else self.BROWSE_OPTION
            self.sound_selection_var.set(default_sound)
            self.sound_filepath = self.map_display_to_internal_sound(default_sound) if default_sound != self.BROWSE_OPTION else None
            self.specific_date_var.set((datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
            return
            
        self.hour_var.set(f"{self.initial_data.get('hour', 0):02}")
        self.minute_var.set(f"{self.initial_data.get('minute', 0):02}")
        self.label_var.set(self.initial_data.get('label', ''))
        self.enabled_var.set(self.initial_data.get('enabled', True))
        self.recurrence_type_var.set(self.initial_data.get('recurrence_type', RECURRENCE_ONCE))
        self.specific_date_var.set(self.initial_data.get('specific_date', (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")))
        
        self.sound_filepath = self.initial_data.get('sound_file')
        if self.sound_filepath:
             if self.sound_filepath.startswith(self.BUILTIN_SOUNDS_PREFIX):
                 fname = self.sound_filepath.split(":", 1)[1]
                 dname = fname.rsplit('.', 1)[0].replace('_', ' ')
                 available_display_names = [s for s in self.get_available_sounds() if s != self.BROWSE_OPTION]
                 if dname in available_display_names: 
                     self.sound_selection_var.set(dname)
                 else: 
                     print(f"Warn: Saved sound '{dname}' not found.")
                     self.sound_selection_var.set(self.BROWSE_OPTION)
                     self.sound_filepath = None
             else: # Custom file
                 if os.path.exists(self.sound_filepath): 
                     self.sound_selection_var.set(f"Custom: {os.path.basename(self.sound_filepath)}")
                 else: 
                     print(f"Warn: Custom sound missing: {self.sound_filepath}")
                     self.sound_selection_var.set(self.BROWSE_OPTION)
                     self.sound_filepath = None
        else: 
            self.sound_selection_var.set(self.BROWSE_OPTION)
            self.sound_filepath = None
            
        rec_days = self.initial_data.get('recurrence_days', [])
        for i in range(7):
            self.day_vars[i].set(i in rec_days)
        self.on_recurrence_change()

    def on_recurrence_change(self, event=None):
        selected_type = self.recurrence_type_var.get()
        show_days = selected_type == "Specific Days"
        show_date = selected_type == RECURRENCE_SPECIFIC_DATE
        
        # Handle days frame visibility
        if show_days and not self.days_frame.winfo_ismapped():
            self.days_frame.pack(fill=tk.X, pady=(5, 0))
        elif not show_days and self.days_frame.winfo_ismapped():
            self.days_frame.pack_forget()
            
        # Handle date frame visibility - always show for Specific Date
        if show_date and not self.date_frame.winfo_ismapped():
            self.date_frame.pack(fill=tk.X, pady=(5, 0))
        elif not show_date and self.date_frame.winfo_ismapped():
            self.date_frame.pack_forget()
            
        # Force update to ensure the UI reflects the current state
        self.update_idletasks()
            
    def on_sound_select(self, event=None):
        selection = self.sound_selection_var.get()
        if selection == self.BROWSE_OPTION: 
            self.browse_sound_file()
        else: 
            self.sound_filepath = self.map_display_to_internal_sound(selection)
            print(f"Selected sound: {self.sound_filepath}")
            
    def browse_sound_file(self):
        filepath = filedialog.askopenfilename(
            title="Select Alarm Sound", 
            filetypes=[("Audio Files", "*.wav *.mp3 *.ogg"), ("All Files", "*.*")]
        )
        if filepath:
            if os.path.isfile(filepath): 
                self.sound_filepath = filepath
                self.sound_selection_var.set(f"Custom: {os.path.basename(filepath)}")
                print(f"Selected custom: {self.sound_filepath}")
            else: 
                messagebox.showerror("Invalid File", "Not valid file.", parent=self)
                self.sound_selection_var.set(self.BROWSE_OPTION)
                self.sound_filepath = None
        elif self.sound_filepath is None: 
            self.sound_selection_var.set(self.BROWSE_OPTION)
            
    def save(self):
        try:
            minute = int(self.minute_var.get())
            if not (0 <= minute <= 59):
                raise ValueError("Invalid minute (must be 0-59)")
                
            # Convert hour based on time format
            hour = int(self.hour_var.get())
            if self.time_format == "12h":
                # Validate 12-hour format
                if not (1 <= hour <= 12):
                    raise ValueError("Invalid hour (must be 1-12 in 12-hour format)")
                    
                # Convert to 24-hour format for storage
                if self.ampm_var.get() == "PM" and hour < 12:
                    hour += 12
                elif self.ampm_var.get() == "AM" and hour == 12:
                    hour = 0  # 12 AM is 0 in 24-hour format
            else:
                # Validate 24-hour format
                if not (0 <= hour <= 23):
                    raise ValueError("Invalid hour (must be 0-23 in 24-hour format)")
                
            label = self.label_var.get().strip()
            enabled = self.enabled_var.get()
            recurrence_type = self.recurrence_type_var.get()
            recurrence_days = []
            specific_date = None
            
            if recurrence_type == "Specific Days": 
                recurrence_days = [i for i, var in self.day_vars.items() if var.get()]
            elif recurrence_type == RECURRENCE_SPECIFIC_DATE: 
                specific_date = self.specific_date_var.get()
                
            sound_file = self.sound_filepath
            if enabled and not sound_file: 
                messagebox.showerror("Missing Sound", "Select sound file.", parent=self)
                return
                
            self.result = {
                'hour': hour, 
                'minute': minute, 
                'label': label, 
                'sound_file': sound_file, 
                'enabled': enabled, 
                'recurrence_type': recurrence_type, 
                'recurrence_days': recurrence_days, 
                'specific_date': specific_date
            }
            
            alarm_id = self.initial_data.get('id') if self.initial_data else None
            if alarm_id: 
                self.save_callback(alarm_id, self.result)
            else: 
                self.save_callback(self.result)
                
            self.destroy()
        except ValueError as e: 
            messagebox.showerror("Invalid Input", f"Check input:\n{e}", parent=self)
        except Exception as e: 
            messagebox.showerror("Error", f"Error: {e}", parent=self)


# --- Timezone Selection Dialog ---
class TimezoneDialog(tk.Toplevel):
      def __init__(self, parent, title, timezone_list, current_theme='light'):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(title)
        self.geometry("350x150")
        self.resizable(False, False)

        # Store theme colors locally
        self.BG_COLOR = D_COLOR_BACKGROUND if current_theme == 'dark' else L_COLOR_BACKGROUND
        self.FRAME_BG = D_COLOR_FRAME_BG if current_theme == 'dark' else L_COLOR_FRAME_BG
        self.TEXT_COLOR = D_COLOR_TEXT if current_theme == 'dark' else L_COLOR_TEXT
        self.ACCENT_COLOR = D_COLOR_ACCENT if current_theme == 'dark' else L_COLOR_ACCENT
        self.ACCENT_FG = D_COLOR_ACCENT_FG
        self.TEXT_SECONDARY = D_COLOR_TEXT_SECONDARY if current_theme == 'dark' else L_COLOR_TEXT_SECONDARY

        self.configure(bg=self.BG_COLOR) # Apply background

        self.result = None
        self.timezone_list = sorted(timezone_list)
        self.selected_tz = tk.StringVar()

        # Setup styles locally using the stored theme colors
        style = ttk.Style(self)
        style.configure('.', background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        style.configure('TFrame', background=self.BG_COLOR)
        style.configure('TLabel', background=self.BG_COLOR)
        style.configure('TButton', font=(FONT_FAMILY_UI, FONT_SIZE_BASE), padding=(8, 5), background=self.ACCENT_COLOR, foreground=self.ACCENT_FG)
        style.configure('Secondary.TButton', background=self.TEXT_SECONDARY, foreground=self.ACCENT_FG)
        style.map('TCombobox', fieldbackground=[('readonly', self.FRAME_BG)])
        style.map('TCombobox', selectbackground=[('readonly', self.FRAME_BG)])
        style.map('TCombobox', selectforeground=[('readonly', self.TEXT_COLOR)])

        # Widgets
        ttk.Label(self, text="Select a timezone:").pack(pady=(10, 5))
        combo = ttk.Combobox(self, textvariable=self.selected_tz, values=self.timezone_list, state='readonly', width=40)
        combo.pack(pady=5, padx=15, fill=tk.X)
        if self.timezone_list: 
            combo.current(0)
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Add", command=self.add).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.destroy, style='Secondary.TButton').pack(side=tk.LEFT, padx=10)
        self.wait_window(self)

      def add(self): 
          self.result = self.selected_tz.get()
          self.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = None
    try:
        app = AlarmClockApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("Keyboard interrupt, quitting.")
        if app:
            try: 
                app.quit_application()
            except Exception as qe: 
                print(f"Error during KB interrupt quit: {qe}")
    except Exception as e:
        print(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        if app and app.running:
            try: 
                app.quit_application()
            except Exception as qe: 
                print(f"Error during exception quit: {qe}")
        elif pygame.get_init(): 
            print("Final pygame quit check (exception).")
            pygame.quit()
        if root and root.winfo_exists():
             try: 
                 root.destroy()
             except Exception as de: 
                 print(f"Error destroying root: {de}")
    finally:
        if 'app' in locals() and app and app.running:
            print("Mainloop finished, ensuring quit.")
            try: 
                app.quit_application()
            except Exception as qe: 
                print(f"Error during final quit: {qe}")
        elif pygame.get_init():
            print("Final pygame quit check (end).")
            pygame.quit()
    print("Application finished.")
