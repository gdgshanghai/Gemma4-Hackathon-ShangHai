"""Role-name → canonical role_id resolver."""

from __future__ import annotations

DEFAULT_ROLE_ID = "mentor_ying"

# Ordered keyword → role_id rules. First match wins.
_ROLE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("高凌", "Ling", "mentor_ling"), "mentor_ling"),
    (("Amy", "pm_amy"), "pm_amy"),
    (("市场专员", "colleague_marketing"), "colleague_marketing"),
    (("运营经理", "colleague_operations"), "colleague_operations"),
    (("销售总监", "stakeholder_sales"), "stakeholder_sales"),
    (("产品经理", "stakeholder_product"), "stakeholder_product"),
)


def resolve_role_id(role_name: str) -> str:
  """Map a free-form display name to a canonical ``role_id``."""
  for keywords, role_id in _ROLE_RULES:
    if any(kw in role_name for kw in keywords):
      return role_id
  return DEFAULT_ROLE_ID
