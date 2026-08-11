import pytest

from launchpad.capacity_units import set_capacity_unit_mode


@pytest.fixture(autouse=True)
def _reset_capacity_unit_mode():
    set_capacity_unit_mode("iec")
    yield
    set_capacity_unit_mode("iec")
