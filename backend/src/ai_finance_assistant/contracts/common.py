"""Shared constrained scalar types."""

from typing import Annotated

from pydantic import StringConstraints

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
NARRATIVE_TEXT_MAX_LENGTH = 4_000
NarrativeText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=NARRATIVE_TEXT_MAX_LENGTH,
    ),
]
CurrencyCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$"),
]
