"""Timestamped output.

Everything this app prints while running goes through here. The scheduled task
appends to busy-bar.log across weeks of logons, and a bare "bar: on_call" tells
you nothing about when your status actually changed.
"""

import time


def log(message):
    """Print a message prefixed with the local date and time."""
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}")