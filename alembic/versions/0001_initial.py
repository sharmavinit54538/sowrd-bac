"""initial migration

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-31 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. company_profile table
    op.create_table(
        "company_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tagline", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state_name", sa.String(100), nullable=False),
        sa.Column("state_code", sa.String(10), nullable=False),
        sa.Column("gstin", sa.String(20), nullable=False),
        sa.Column("pan", sa.String(20), nullable=False),
        sa.Column("iec", sa.String(20), nullable=False),
        sa.Column("phones", sa.JSON(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("founder", sa.String(100), nullable=True),
        sa.Column("founder_mobile", sa.String(50), nullable=True),
        sa.Column("jurisdiction", sa.String(100), nullable=False),
    )

    # 3. customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("billing_address", sa.Text(), nullable=False),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("state_name", sa.String(100), nullable=False),
        sa.Column("state_code", sa.String(10), nullable=False),
        sa.Column("gstin", sa.String(20), nullable=True),
        sa.Column("contact_person", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 4. products table
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("technical_specs", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("hsn_code", sa.String(20), server_default="84779000", nullable=False),
        sa.Column("unit", sa.String(20), server_default="Nos", nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("total_stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_stock_level", sa.Integer(), server_default="5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    # 5. documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("doc_number", sa.String(50), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(50), server_default="DRAFT", nullable=False),
        sa.Column("parent_doc_id", sa.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_doc_number", sa.String(50), nullable=True),
        sa.Column("customer_id", sa.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("buyer_order_ref", sa.String(100), nullable=True),
        sa.Column("buyer_order_date", sa.Date(), nullable=True),
        sa.Column("mode_of_dispatch", sa.String(100), nullable=True),
        sa.Column("mode_of_payment", sa.String(100), nullable=True),
        sa.Column("place_of_supply", sa.String(100), nullable=True),
        sa.Column("sub_total", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("cgst_rate", sa.Numeric(5, 2), server_default="0.00", nullable=False),
        sa.Column("cgst_amount", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("sgst_rate", sa.Numeric(5, 2), server_default="0.00", nullable=False),
        sa.Column("sgst_amount", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("igst_rate", sa.Numeric(5, 2), server_default="0.00", nullable=False),
        sa.Column("igst_amount", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("rounding_off", sa.Numeric(6, 2), server_default="0.00", nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("amount_in_words", sa.Text(), nullable=True),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("parts_value", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("service_charges_value", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("job_work_total_value", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("transporter_name", sa.String(150), nullable=True),
        sa.Column("vehicle_no", sa.String(50), nullable=True),
        sa.Column("dispatch_date", sa.Date(), nullable=True),
        sa.Column("pkg_number", sa.String(50), nullable=True),
        sa.Column("gross_weight", sa.String(50), nullable=True),
        sa.Column("payment_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_by_role", sa.String(50), nullable=True),
        sa.Column("stock_reserved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("stock_deducted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_documents_doc_number", "documents", ["doc_number"], unique=True)
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # 6. document_items table
    op.create_table(
        "document_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sr", sa.Integer(), server_default="1", nullable=False),
        sa.Column("product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("technical_specs", sa.Text(), nullable=True),
        sa.Column("hsn_code", sa.String(20), server_default="84779000", nullable=False),
        sa.Column("qty", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit", sa.String(20), server_default="Nos", nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("net_weight", sa.String(50), nullable=True),
    )
    op.create_index("ix_document_items_document_id", "document_items", ["document_id"])

    # 7. inventory_logs table
    op.create_table(
        "inventory_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference_doc_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("reference_doc_number", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inventory_logs_product_id", "inventory_logs", ["product_id"])

    # 8. audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("user_role", sa.String(50), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("inventory_logs")
    op.drop_table("document_items")
    op.drop_table("documents")
    op.drop_table("products")
    op.drop_table("customers")
    op.drop_table("company_profile")
    op.drop_table("users")

