"""Minimal in-process metrics registry exposed at /metrics (Prometheus text format)."""

import threading
from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)

    def inc(self, name: str, value: float = 1.0, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels) -> None:
        self.inc(f"{name}_sum", value, **labels)
        self.inc(f"{name}_count", 1.0, **labels)

    def _key(self, name: str, labels: dict) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def render(self) -> str:
        with self._lock:
            lines = [f"{key} {value}" for key, value in sorted(self._counters.items())]
        return "\n".join(lines) + "\n"

    def get(self, name: str, **labels) -> float:
        return self._counters.get(self._key(name, labels), 0.0)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


metrics = MetricsRegistry()
