"""Pembacaan daya chip lewat macOS `powermetrics` dan perhitungan energi.

Alur yang dipakai benchmark:

1. `PowerMonitor` menjalankan `powermetrics` di latar belakang dan menyimpan
   setiap sampel (daya gabungan CPU + GPU + ANE, panjang interval sampel).
2. Sampel diletakkan pada sumbu waktu `time.monotonic()` lewat
   `align_samples`, sehingga bisa dipotong tepat pada jendela satu run.
3. `window_power` mengintegrasikan daya pada jendela run (bobot = lama
   tumpang-tindih tiap sampel), lalu `energy_metrics` menghitung `J/token`
   di atas daya idle sesuai rumus pada docs/PRD.md §7.
"""

from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import dataclass

HEADER_RE = re.compile(r"\*\*\* Sampled system activity .*\(([\d.]+)\s*ms elapsed\)")
COMBINED_RE = re.compile(r"Combined Power \(CPU \+ GPU \+ ANE\):\s*([\d.]+)\s*mW")
COMPONENT_RE = re.compile(r"^(CPU|GPU|ANE) Power:\s*([\d.]+)\s*mW")


@dataclass(frozen=True)
class RawSample:
    """Satu sampel seperti yang dibaca: waktu tiba, panjang interval, daya."""

    arrival: float
    elapsed_s: float
    watts: float


@dataclass(frozen=True)
class PowerSample:
    """Sampel yang sudah diletakkan pada sumbu waktu monotonic."""

    end: float
    elapsed_s: float
    watts: float

    @property
    def start(self) -> float:
        return self.end - self.elapsed_s


@dataclass(frozen=True)
class WindowPower:
    avg_watts: float
    covered_s: float
    coverage: float
    samples: int


class PowermetricsParser:
    """Parser inkremental untuk output teks `powermetrics`.

    Daya diambil dari baris `Combined Power (CPU + GPU + ANE)`. Jika baris itu
    tidak ada, dipakai jumlah baris `CPU/GPU/ANE Power` pertama pada sampel
    tersebut (baris `GPU Power` kedua di bagian GPU usage diabaikan).
    """

    def __init__(self) -> None:
        self._elapsed_s: float | None = None
        self._components: dict[str, float] = {}
        self._last_time = 0.0
        self._emitted = False

    def feed(self, line: str, now: float) -> RawSample | None:
        header = HEADER_RE.search(line)
        if header:
            done = self.flush()
            self._elapsed_s = float(header.group(1)) / 1000.0
            self._components = {}
            self._emitted = False
            return done
        if self._elapsed_s is None or self._emitted:
            return None
        combined = COMBINED_RE.search(line)
        if combined:
            self._emitted = True
            return RawSample(now, self._elapsed_s, float(combined.group(1)) / 1000.0)
        component = COMPONENT_RE.match(line.strip())
        if component and component.group(1) not in self._components:
            self._components[component.group(1)] = float(component.group(2))
            self._last_time = now
        return None

    def flush(self) -> RawSample | None:
        """Tutup sampel yang sedang dibaca (dipanggil saat header baru/EOF)."""
        if self._elapsed_s is None or self._emitted or not self._components:
            return None
        self._emitted = True
        watts = sum(self._components.values()) / 1000.0
        return RawSample(self._last_time, self._elapsed_s, watts)


def parse_powermetrics(text: str) -> list[RawSample]:
    """Parse output lengkap; waktu tiba diisi kumulatif interval (untuk test/audit)."""
    parser = PowermetricsParser()
    raw = [s for line in text.splitlines() if (s := parser.feed(line, 0.0))]
    if last := parser.flush():
        raw.append(last)
    elapsed = 0.0
    timed = []
    for sample in raw:
        elapsed += sample.elapsed_s
        timed.append(RawSample(elapsed, sample.elapsed_s, sample.watts))
    return timed


def align_samples(raw: list[RawSample]) -> list[PowerSample]:
    """Letakkan sampel pada sumbu waktu monotonic.

    Sampel ke-k berakhir pada `anchor + jumlah interval 0..k`. Waktu tiba
    selalu sama atau lebih lambat dari akhir sampel sebenarnya (keterlambatan
    pipe/buffer), sehingga offset terkecil adalah estimasi anchor terbaik.
    """
    if not raw:
        return []
    ends = []
    cumulative = 0.0
    for sample in raw:
        cumulative += sample.elapsed_s
        ends.append(cumulative)
    anchor = min(s.arrival - end for s, end in zip(raw, ends))
    return [PowerSample(anchor + end, s.elapsed_s, s.watts) for s, end in zip(raw, ends)]


def window_power(samples: list[PowerSample], t0: float, t1: float) -> WindowPower | None:
    """Rata-rata daya berbobot waktu pada jendela [t0, t1]; None jika tanpa sampel."""
    if t1 <= t0:
        raise ValueError("jendela waktu harus positif")
    joules = 0.0
    covered = 0.0
    count = 0
    for sample in samples:
        overlap = min(sample.end, t1) - max(sample.start, t0)
        if overlap > 0:
            joules += sample.watts * overlap
            covered += overlap
            count += 1
    if covered == 0:
        return None
    return WindowPower(joules / covered, covered, covered / (t1 - t0), count)


def energy_metrics(
    avg_watts: float, idle_watts: float, duration_s: float, generation_tokens: int
) -> tuple[float, bool]:
    """Kembalikan (`joules_per_token`, `energy_clipped`).

    Energi tambahan = max(avg - idle, 0) × durasi. `energy_clipped` bernilai
    True bila selisih negatif dipotong menjadi 0, agar bisa diaudit.
    """
    if generation_tokens <= 0:
        raise ValueError("generation_tokens harus > 0")
    if duration_s <= 0:
        raise ValueError("duration_s harus > 0")
    excess = avg_watts - idle_watts
    clipped = excess < 0
    return max(excess, 0.0) * duration_s / generation_tokens, clipped


def powermetrics_command(interval_ms: int) -> list[str]:
    # `sudo -n` gagal cepat alih-alih meminta password di tengah benchmark;
    # jalankan `sudo -v` sebelum sesi (docs/EXPERIMENT_PLAN.md).
    return [
        "sudo", "-n", "powermetrics",
        "--samplers", "cpu_power,gpu_power",
        "-i", str(interval_ms),
    ]


class PowerMonitor:
    """Menjalankan `powermetrics` di latar belakang selama satu blok benchmark."""

    def __init__(self, interval_ms: int = 100, command: list[str] | None = None) -> None:
        self.interval_ms = interval_ms
        self.command = command or powermetrics_command(interval_ms)
        self._raw: list[RawSample] = []
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "PowerMonitor":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self, first_sample_timeout_s: float = 10.0) -> None:
        self._proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + first_sample_timeout_s
        while not self._latest_arrival():
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read() if self._proc.stderr else ""
                raise RuntimeError(f"powermetrics berhenti: {stderr.strip()}")
            if time.monotonic() > deadline:
                self.stop()
                raise RuntimeError("tidak ada sampel powermetrics; periksa format output")
            time.sleep(0.05)

    def _read(self) -> None:
        parser = PowermetricsParser()
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            sample = parser.feed(line, time.monotonic())
            if sample:
                with self._lock:
                    self._raw.append(sample)
        if sample := parser.flush():
            with self._lock:
                self._raw.append(sample)

    def _latest_arrival(self) -> float | None:
        with self._lock:
            return self._raw[-1].arrival if self._raw else None

    def samples(self) -> list[PowerSample]:
        with self._lock:
            raw = list(self._raw)
        return align_samples(raw)

    def wait_until(self, t: float, timeout_s: float = 5.0) -> None:
        """Tunggu sampai ada sampel yang menutup waktu `t` (akhir jendela run)."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            samples = self.samples()
            if samples and samples[-1].end >= t:
                return
            time.sleep(self.interval_ms / 2000.0)

    def window(self, t0: float, t1: float) -> WindowPower | None:
        self.wait_until(t1)
        return window_power(self.samples(), t0, t1)

    def measure_idle(self, seconds: float) -> float:
        """Rata-rata daya selama `seconds` detik tanpa beban benchmark."""
        t0 = time.monotonic()
        time.sleep(seconds)
        window = self.window(t0, time.monotonic())
        if window is None or window.coverage < 0.5:
            raise RuntimeError("sampel daya idle tidak cukup")
        return window.avg_watts

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._thread:
            self._thread.join(timeout=5)
