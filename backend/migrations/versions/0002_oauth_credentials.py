"""Add encrypted per-user OAuth credentials and one-time OAuth state."""
from alembic import op
import sqlalchemy as sa

revision = "0002_oauth_credentials"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=8192), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=8192), nullable=True),
        sa.Column("token_type", sa.String(length=32), nullable=False, server_default="Bearer"),
        sa.Column("scopes", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )
    op.create_index("ix_oauth_credentials_user_id", "oauth_credentials", ["user_id"])
    op.create_index("ix_oauth_credentials_provider", "oauth_credentials", ["provider"])
    op.create_table(
        "oauth_states",
        sa.Column("state_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])


def downgrade():
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_oauth_credentials_provider", table_name="oauth_credentials")
    op.drop_index("ix_oauth_credentials_user_id", table_name="oauth_credentials")
    op.drop_table("oauth_credentials")
