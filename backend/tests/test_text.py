"""Slovak noun forms after a number."""

import pytest

from app.core.text import FAULTS, SOURCES, YEARS, counted, plural


class TestPlural:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(1, "rok"), (2, "roky"), (3, "roky"), (4, "roky"), (5, "rokov"), (11, "rokov")],
    )
    def test_years(self, count: int, expected: str):
        assert plural(count, *YEARS) == expected

    def test_zero_takes_the_genitive_form(self):
        # "0 rokov", never "0 rok".
        assert plural(0, *YEARS) == "rokov"

    def test_counted_joins_the_number_and_the_form(self):
        assert counted(1, *SOURCES) == "1 zdroj"
        assert counted(3, *SOURCES) == "3 zdroje"
        assert counted(8, *SOURCES) == "8 zdrojov"

    def test_every_noun_set_has_three_forms(self):
        for forms in (YEARS, SOURCES, FAULTS):
            assert len(forms) == 3
            assert len(set(forms)) == 3
