from typing import Annotated, Literal, TypeAlias

from pydantic import Field
from typing_extensions import TypedDict

Status: TypeAlias = Literal["OK", "ERROR"]
Price: TypeAlias = Annotated[int, Field(strict=True, gt=0)]
Prices: TypeAlias = list[Price]


class Record(TypedDict):
    utc: str
    status: Status
    prices: Prices
