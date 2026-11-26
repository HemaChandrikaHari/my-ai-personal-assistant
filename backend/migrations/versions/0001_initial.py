"""Initial assistant tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("integration_id", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.UniqueConstraint("user_id", "integration_id", "scope"),
    )
    op.create_index("ix_grants_user_id", "grants", ["user_id"])
    op.create_index("ix_grants_integration_id", "grants", ["integration_id"])
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("integration_id", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approvals_user_id", "approvals", ["user_id"])
    op.create_table(
        "audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=200), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_user_id", "audit", ["user_id"])


def downgrade():
    op.drop_index("ix_audit_user_id", table_name="audit")
    op.drop_table("audit")
    op.drop_index("ix_approvals_user_id", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_grants_integration_id", table_name="grants")
    op.drop_index("ix_grants_user_id", table_name="grants")
    op.drop_table("grants")
    op.drop_table("integrations")
