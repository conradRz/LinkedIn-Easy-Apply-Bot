import os
import time
import ctypes
from datetime import datetime, timedelta

# Path to the file
file_path = "output.csv"

# Function to show a popup notification on Windows
def show_notification(message):
    ctypes.windll.user32.MessageBoxW(0, message, "File Monitor Alert", 0x40 | 0x1)

# Function to get the next check time
def get_next_check_time(file_mod_time):
    return file_mod_time + timedelta(minutes=10)

# Function to check the modification time of the file
def check_file_modification_time(file_path):
    # Get the file's last modification time
    try:
        file_mod_time = os.path.getmtime(file_path)
        file_mod_time = datetime.fromtimestamp(file_mod_time)
    except FileNotFoundError:
        show_notification(f"The file '{file_path}' does not exist.")
        return None

    # Calculate the next check time
    next_check_time = get_next_check_time(file_mod_time)
    
    # Get the current time
    current_time = datetime.now()

    # If the file is older than 10 minutes, show a notification
    if current_time >= next_check_time:
        show_notification(f"The file '{file_path}' was last modified more than 10 minutes ago.")
        return None
    
    return next_check_time

# Monitor the file
while True:
    next_check_time = check_file_modification_time(file_path)
    
    if next_check_time is None:
        break  # Stop monitoring if file does not exist or is already older than 10 minutes
    
    # Sleep until the next check time
    time_to_sleep = (next_check_time - datetime.now()).total_seconds()
    time.sleep(time_to_sleep)
