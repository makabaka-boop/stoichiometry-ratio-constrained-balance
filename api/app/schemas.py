"""Pydantic request models for the API.

The wire models intentionally stay permissive about value *content*
(counts may be any integer, including zero or negative) so that the
validator in :mod:`app.validation` can report a single, stable set of
semantic error codes. Unknown JSON fields are rejected here via
``extra="forbid"``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class CompoundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    side: Literal["REACTANT", "PRODUCT"]
    # StrictInt refuses booleans (which would otherwise coerce to 0/1).
    composition: dict[str, StrictInt]


class BalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compounds: list[CompoundIn] = Field(min_length=2, max_length=12)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compounds: list[CompoundIn] = Field(min_length=2, max_length=12)
    coefficients: dict[str, StrictInt]
