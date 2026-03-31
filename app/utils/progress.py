# app/utils/progress.py
import sys
import time
import asyncio
from typing import Optional, Callable, Any
import threading

class ProgressIndicator:
    """
    A simple progress indicator for long-running operations.
    
    This class provides different styles of progress indicators:
    - dots: Animated dots (. .. ... ....)
    - spinner: Spinning cursor (|/-\)
    - percentage: Progress percentage [####    ] 40%
    """
    
    def __init__(self, 
                 message: str = "Processing", 
                 style: str = "dots", 
                 total: Optional[int] = None):
        """
        Initialize the progress indicator.
        
        Args:
            message: The message to display before the indicator
            style: The indicator style ('dots', 'spinner', or 'percentage')
            total: Total items for percentage style (required for percentage)
        """
        self.message = message
        self.style = style
        self.total = total
        self.current = 0
        self.start_time = None
        self._running = False
        self._thread = None
        self._task = None
        
        # Validate style
        if style not in ["dots", "spinner", "percentage"]:
            raise ValueError("Style must be 'dots', 'spinner', or 'percentage'")
            
        # Validate total for percentage style
        if style == "percentage" and total is None:
            raise ValueError("Total must be specified for percentage style")
    
    def start(self):
        """Start the progress indicator in a separate thread."""
        if self._running:
            return
            
        self._running = True
        self.start_time = time.time()
        
        # Start the appropriate indicator
        if self.style == "dots":
            self._thread = threading.Thread(target=self._dots_indicator)
        elif self.style == "spinner":
            self._thread = threading.Thread(target=self._spinner_indicator)
        elif self.style == "percentage":
            self._thread = threading.Thread(target=self._percentage_indicator)
            
        self._thread.daemon = True
        self._thread.start()
        
    async def start_async(self):
        """Start the progress indicator as an asyncio task."""
        if self._running:
            return
            
        self._running = True
        self.start_time = time.time()
        
        # Start the appropriate indicator
        if self.style == "dots":
            self._task = asyncio.create_task(self._dots_indicator_async())
        elif self.style == "spinner":
            self._task = asyncio.create_task(self._spinner_indicator_async())
        elif self.style == "percentage":
            self._task = asyncio.create_task(self._percentage_indicator_async())
    
    def update(self, current: int):
        """Update the progress (for percentage style)."""
        self.current = current
    
    def stop(self):
        """Stop the progress indicator."""
        if not self._running:
            return
            
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=1.0)
            
        # Clear the progress line and write a newline
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        
    async def stop_async(self):
        """Stop the progress indicator (async version)."""
        if not self._running:
            return
            
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
        # Clear the progress line and write a newline
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
    
    def _dots_indicator(self):
        """Display an animated dots indicator."""
        i = 0
        while self._running:
            dots = "." * (i % 4 + 1)
            elapsed = time.time() - self.start_time
            sys.stdout.write(f"\r{self.message}{dots:<4} ({elapsed:.1f}s)")
            sys.stdout.flush()
            time.sleep(0.5)
            i += 1
    
    async def _dots_indicator_async(self):
        """Display an animated dots indicator (async version)."""
        i = 0
        while self._running:
            dots = "." * (i % 4 + 1)
            elapsed = time.time() - self.start_time
            sys.stdout.write(f"\r{self.message}{dots:<4} ({elapsed:.1f}s)")
            sys.stdout.flush()
            await asyncio.sleep(0.5)
            i += 1
    
    def _spinner_indicator(self):
        """Display a spinning cursor indicator."""
        chars = "|/-\\"
        i = 0
        while self._running:
            char = chars[i % len(chars)]
            elapsed = time.time() - self.start_time
            sys.stdout.write(f"\r{self.message} {char} ({elapsed:.1f}s)")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    
    async def _spinner_indicator_async(self):
        """Display a spinning cursor indicator (async version)."""
        chars = "|/-\\"
        i = 0
        while self._running:
            char = chars[i % len(chars)]
            elapsed = time.time() - self.start_time
            sys.stdout.write(f"\r{self.message} {char} ({elapsed:.1f}s)")
            sys.stdout.flush()
            await asyncio.sleep(0.1)
            i += 1
    
    def _percentage_indicator(self):
        """Display a percentage progress bar."""
        while self._running:
            percentage = min(100, int((self.current / self.total) * 100))
            bar_length = 20
            filled_length = int(bar_length * percentage // 100)
            bar = '#' * filled_length + ' ' * (bar_length - filled_length)
            elapsed = time.time() - self.start_time
            
            # Estimate time remaining if we have progress
            if percentage > 0:
                remaining = elapsed * (100 - percentage) / percentage
                sys.stdout.write(f"\r{self.message} [{bar}] {percentage}% ({elapsed:.1f}s elapsed, ~{remaining:.1f}s remaining)")
            else:
                sys.stdout.write(f"\r{self.message} [{bar}] {percentage}% ({elapsed:.1f}s elapsed)")
                
            sys.stdout.flush()
            time.sleep(0.2)
    
    async def _percentage_indicator_async(self):
        """Display a percentage progress bar (async version)."""
        while self._running:
            percentage = min(100, int((self.current / self.total) * 100))
            bar_length = 20
            filled_length = int(bar_length * percentage // 100)
            bar = '#' * filled_length + ' ' * (bar_length - filled_length)
            elapsed = time.time() - self.start_time
            
            # Estimate time remaining if we have progress
            if percentage > 0:
                remaining = elapsed * (100 - percentage) / percentage
                sys.stdout.write(f"\r{self.message} [{bar}] {percentage}% ({elapsed:.1f}s elapsed, ~{remaining:.1f}s remaining)")
            else:
                sys.stdout.write(f"\r{self.message} [{bar}] {percentage}% ({elapsed:.1f}s elapsed)")
                
            sys.stdout.flush()
            await asyncio.sleep(0.2)

# Convenience function for running a task with progress indicator
def with_progress(func: Callable, *args, message: str = "Processing", style: str = "dots", **kwargs) -> Any:
    """
    Run a function with a progress indicator.
    
    Args:
        func: Function to run
        *args: Arguments to pass to the function
        message: Message to display
        style: Progress indicator style
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function
    """
    progress = ProgressIndicator(message=message, style=style)
    progress.start()
    
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        progress.stop()

# Async version of with_progress
async def with_progress_async(func: Callable, *args, message: str = "Processing", style: str = "dots", **kwargs) -> Any:
    """
    Run an async function with a progress indicator.
    
    Args:
        func: Async function to run
        *args: Arguments to pass to the function
        message: Message to display
        style: Progress indicator style
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function
    """
    progress = ProgressIndicator(message=message, style=style)
    await progress.start_async()
    
    try:
        result = await func(*args, **kwargs)
        return result
    finally:
        await progress.stop_async()