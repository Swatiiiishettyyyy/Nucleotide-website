"""Compatibility marker for shared blood-test revision

Revision ID: 086_add_blood_test_coupon_fields_to_orders
Revises: 058_merge_coupon_product_enquiry
Create Date: 2026-05-24
"""

from typing import Sequence, Union


revision: str = "086_add_blood_test_coupon_fields_to_orders"
down_revision: Union[str, None] = "058_merge_coupon_product_enquiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
