from pathlib import Path

import pytest

from src.power import PowermetricsParser, RawSample, align_samples, parse_powermetrics

FIXTURE = Path(__file__).parent / "fixtures" / "powermetrics_synthetic.txt"


def test_parse_fixture_uses_combined_power_and_fallback():
    samples = parse_powermetrics(FIXTURE.read_text())
    assert [round(s.watts, 3) for s in samples] == [1.5, 12.0, 3.1]
    assert [round(s.elapsed_s, 5) for s in samples] == [0.10042, 0.09958, 0.1]


def test_fallback_ignores_second_gpu_power_line():
    # Sampel ketiga tidak punya baris Combined; GPU Power 999 mW di bagian
    # GPU usage tidak boleh menggantikan nilai pertama (500 mW).
    samples = parse_powermetrics(FIXTURE.read_text())
    assert samples[2].watts == pytest.approx(2.5 + 0.5 + 0.1)


def test_combined_emits_without_waiting_for_next_header():
    parser = PowermetricsParser()
    assert parser.feed("*** Sampled system activity (x) (100.0ms elapsed) ***", 1.0) is None
    sample = parser.feed("Combined Power (CPU + GPU + ANE): 2500 mW", 1.25)
    assert sample == RawSample(arrival=1.25, elapsed_s=0.1, watts=2.5)
    assert parser.flush() is None


def test_lines_before_first_header_are_ignored():
    parser = PowermetricsParser()
    assert parser.feed("CPU Power: 100 mW", 0.0) is None
    assert parser.flush() is None


def test_align_uses_earliest_arrival_as_anchor():
    # Sampel kedua tiba terlambat 0.3 s; anchor tetap dari sampel tercepat.
    raw = [RawSample(10.1, 0.1, 1.0), RawSample(10.5, 0.1, 2.0), RawSample(10.3, 0.1, 3.0)]
    aligned = align_samples(raw)
    assert [round(s.end, 6) for s in aligned] == [10.1, 10.2, 10.3]
    assert aligned[1].start == pytest.approx(10.1)


def test_align_empty():
    assert align_samples([]) == []
