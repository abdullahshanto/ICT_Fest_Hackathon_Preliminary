"""Human-facing booking reference codes.

Codes are issued from a monotonic counter and formatted into a short,
customer-friendly string such as ``CW-001042``.
"""
import threading

_counter = 1000
_lock = threading.Lock()


def next_reference_code() -> str:
    global _counter
    with _lock:
        current = _counter
        _counter += 1
        return f"CW-{current:06d}"
