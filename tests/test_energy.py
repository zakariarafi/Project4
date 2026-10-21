import pytest

from src.power import PowerSample, energy_metrics, window_power


def samples(watts, interval=0.1, start=0.0):
    return [
        PowerSample(start + (i + 1) * interval, interval, w) for i, w in enumerate(watts)
    ]


def test_window_power_weights_partial_overlap():
    s = samples([10.0, 20.0, 30.0])  # [0,.1] [.1,.2] [.2,.3]
    w = window_power(s, 0.05, 0.25)
    # energi = 10*.05 + 20*.1 + 30*.05 = 4.0 J pada 0.2 s
    assert w.avg_watts == pytest.approx(20.0)
    assert w.coverage == pytest.approx(1.0)
    assert w.samples == 3


def test_window_power_reports_gaps_in_coverage():
    s = samples([10.0])  # hanya menutup [0, .1]
    w = window_power(s, 0.0, 0.4)
    assert w.coverage == pytest.approx(0.25)
    assert w.avg_watts == pytest.approx(10.0)


def test_window_power_without_samples():
    assert window_power(samples([5.0]), 1.0, 2.0) is None
    with pytest.raises(ValueError):
        window_power([], 1.0, 1.0)


def test_energy_metrics_formula():
    # (12 W - 2 W) × 3 s / 100 token = 0.3 J/token
    jpt, clipped = energy_metrics(12.0, 2.0, 3.0, 100)
    assert jpt == pytest.approx(0.3)
    assert clipped is False


def test_energy_metrics_clips_negative_and_flags_it():
    jpt, clipped = energy_metrics(1.5, 2.0, 3.0, 100)
    assert jpt == 0.0
    assert clipped is True


@pytest.mark.parametrize("duration,tokens", [(0.0, 10), (1.0, 0)])
def test_energy_metrics_rejects_invalid_input(duration, tokens):
    with pytest.raises(ValueError):
        energy_metrics(10.0, 1.0, duration, tokens)
