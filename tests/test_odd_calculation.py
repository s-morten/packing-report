import math

import pytest

from utils.odd_calculation import odd_to_percentage


class TestOddToPercentage:
    def test_even_odd(self):
        assert odd_to_percentage(2.0) == pytest.approx((0.5, 50.0))

    def test_odd_with_one_decimal(self):
        probability, percentage = odd_to_percentage(1.5)

        assert probability == pytest.approx(1 / 1.5)
        assert percentage == pytest.approx(100 / 1.5)

    def test_odd_with_two_decimals(self):
        assert odd_to_percentage(1.25) == pytest.approx((0.8, 80.0))

    def test_odd_of_one(self):
        assert odd_to_percentage(1.0) == pytest.approx((1.0, 100.0))

    def test_large_odd(self):
        probability, percentage = odd_to_percentage(10.0)

        assert probability == pytest.approx(0.1)
        assert percentage == pytest.approx(10.0)

    def test_zero_raises_value_error(self):
        with pytest.raises(ValueError):
            odd_to_percentage(0.0)

    def test_negative_odd_raises_value_error(self):
        with pytest.raises(ValueError):
            odd_to_percentage(-1.5)

    def test_infinity_raises_value_error(self):
        with pytest.raises(ValueError):
            odd_to_percentage(math.inf)

    def test_nan_raises_value_error(self):
        with pytest.raises(ValueError):
            odd_to_percentage(math.nan)
