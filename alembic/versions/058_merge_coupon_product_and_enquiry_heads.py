"""Merge coupon/product and enquiry migration heads

Revision ID: 058_merge_coupon_product_enquiry
Revises: 054_add_enquiry_requests, 057_product_plan_members
Create Date: 2026-05-24
"""

from typing import Sequence, Tuple, Union


revision: str = "058_merge_coupon_product_enquiry"
down_revision: Union[str, Tuple[str, str]] = (
    "054_add_enquiry_requests",
    "057_product_plan_members",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
