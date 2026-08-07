"""Slovak wording helpers for customer-facing copy.

Slovak nouns take three forms after a number — 1 rok, 2 roky, 5 rokov — so a
count cannot simply be concatenated with a fixed word.
"""


def plural(count: int, one: str, few: str, many: str) -> str:
    """The noun form that follows `count`: 1 → one, 2-4 → few, otherwise many."""
    if count == 1:
        return one
    if 2 <= count <= 4:
        return few
    return many


def counted(count: int, one: str, few: str, many: str) -> str:
    """`count` with the noun form it takes: "1 rok", "2 roky", "5 rokov"."""
    return f"{count} {plural(count, one, few, many)}"


YEARS = ("rok", "roky", "rokov")
SOURCES = ("zdroj", "zdroje", "zdrojov")
WEBSITES = ("webstránka", "webstránky", "webstránok")
PASSAGES = ("pasáž", "pasáže", "pasáží")
FAULTS = ("porucha", "poruchy", "porúch")
PAGES = ("stránka", "stránky", "stránok")
