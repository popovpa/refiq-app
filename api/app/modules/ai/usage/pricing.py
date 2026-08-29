"""Pricing is intentionally empty on MVP.

Usage metrics are stored independently. When real provider price tables exist,
compute estimated_cost here without embedding rates in Offer use cases.
"""


def estimate_cost(*, provider: str, model: str, input_tokens: int | None, output_tokens: int | None) -> None:
    return None
