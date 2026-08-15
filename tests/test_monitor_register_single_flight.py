import threading
import time

from launchpad.monitor import RegisterSingleFlight


def test_overlapping_runs_share_one_call():
    flight = RegisterSingleFlight()
    started = threading.Event()
    releases = threading.Event()
    calls = {"n": 0}

    def fn() -> int:
        calls["n"] += 1
        started.set()
        assert releases.wait(timeout=2)
        return 7

    results: list[int] = []
    errors: list[BaseException] = []

    def caller() -> None:
        try:
            results.append(flight.run(fn))
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=caller)
    t2 = threading.Thread(target=caller)
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    time.sleep(0.05)
    releases.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert errors == []
    assert results == [7, 7]
    assert calls["n"] == 1


def test_later_call_after_finish_runs_again():
    flight = RegisterSingleFlight()
    calls = {"n": 0}

    def fn() -> int:
        calls["n"] += 1
        return calls["n"]

    assert flight.run(fn) == 1
    assert flight.run(fn) == 2
