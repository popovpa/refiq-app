from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import mapped_column

EntityId = BigInteger().with_variant(Integer, "sqlite")


def pk_column():
    return mapped_column(EntityId, primary_key=True, autoincrement=True)


def fk_column(target: str, *, nullable: bool = False, unique: bool = False, index: bool = True):
    return mapped_column(EntityId, ForeignKey(target), nullable=nullable, unique=unique, index=index)


def parse_id(value: str | int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid id: {value}") from exc
    if parsed < 1:
        raise ValueError(f"Invalid id: {value}")
    return parsed


def parse_optional_id(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return parse_id(value)
