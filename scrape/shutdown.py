"""Graceful shutdown handling for long-running scrape operations.

Provides signal handling to cleanly stop scraping operations,
saving state and closing connections properly.
"""

import signal
import sys
import threading
from typing import Callable, Optional

__all__ = [
    "ShutdownHandler",
    "get_shutdown_handler",
    "shutdown_requested",
    "register_cleanup",
]


class ShutdownHandler:
    """Handles graceful shutdown on SIGINT/SIGTERM signals.

    Usage:
        handler = ShutdownHandler()
        handler.register_cleanup(lambda: print("Cleaning up..."))

        while not handler.shutdown_requested:
            # Do work
            pass

        handler.cleanup()
    """

    _instance: Optional["ShutdownHandler"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._shutdown_requested = threading.Event()
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._original_sigint = None
        self._original_sigterm = None
        self._installed = False

    @classmethod
    def get_instance(cls) -> "ShutdownHandler":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def install(self) -> "ShutdownHandler":
        """Install signal handlers.

        Returns:
            Self for chaining
        """
        if self._installed:
            return self

        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._installed = True
        return self

    def uninstall(self) -> None:
        """Restore original signal handlers."""
        if not self._installed:
            return

        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)

        self._installed = False

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle shutdown signal."""
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n\n⚠️  Received {signal_name} - initiating graceful shutdown...")
        print("    (Press Ctrl+C again to force quit)\n")

        # Set shutdown flag
        self._shutdown_requested.set()

        # On second signal, force exit
        signal.signal(signum, self._force_exit)

    def _force_exit(self, signum: int, frame) -> None:
        """Force exit on second signal."""
        print("\n❌ Force quitting...")
        self.cleanup()
        sys.exit(1)

    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested.is_set()

    def check_shutdown(self) -> None:
        """Check for shutdown and raise if requested.

        Raises:
            KeyboardInterrupt: If shutdown was requested
        """
        if self._shutdown_requested.is_set():
            raise KeyboardInterrupt("Graceful shutdown requested")

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """Register a cleanup callback to run on shutdown.

        Args:
            callback: Function to call during cleanup
        """
        self._cleanup_callbacks.append(callback)

    def cleanup(self) -> None:
        """Run all registered cleanup callbacks."""
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Warning: Cleanup callback failed: {e}")

        self._cleanup_callbacks.clear()

    def reset(self) -> None:
        """Reset shutdown state (for testing or reuse)."""
        self._shutdown_requested.clear()


# Module-level convenience functions
def get_shutdown_handler() -> ShutdownHandler:
    """Get the global shutdown handler instance."""
    return ShutdownHandler.get_instance()


def shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return get_shutdown_handler().shutdown_requested


def register_cleanup(callback: Callable[[], None]) -> None:
    """Register a cleanup callback."""
    get_shutdown_handler().register_cleanup(callback)
