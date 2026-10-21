import sys
import textwrap
import time

import pytest

from src.power import PowerMonitor

# Meniru `powermetrics -i 50`: satu sampel 4 W tiap 50 ms.
FAKE = textwrap.dedent(
    """
    import sys, time
    while True:
        time.sleep(0.05)
        print("*** Sampled system activity (x) (50.0ms elapsed) ***")
        print("Combined Power (CPU + GPU + ANE): 4000 mW", flush=True)
    """
)


def test_monitor_measures_window_from_subprocess():
    with PowerMonitor(interval_ms=50, command=[sys.executable, "-c", FAKE]) as monitor:
        idle = monitor.measure_idle(0.3)
        t0 = time.monotonic()
        time.sleep(0.3)
        window = monitor.window(t0, time.monotonic())
    assert idle == pytest.approx(4.0)
    assert window.avg_watts == pytest.approx(4.0)
    assert window.coverage > 0.9


def test_monitor_reports_early_exit():
    monitor = PowerMonitor(command=[sys.executable, "-c", "import sys; sys.exit('butuh sudo')"])
    with pytest.raises(RuntimeError, match="butuh sudo"):
        monitor.start()
