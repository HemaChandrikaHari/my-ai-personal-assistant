"""Add Blueticks OAuth PKCE state and per-user public client registration."""
from alembic import op
import sqlalchemy as sa

revision = "0003_blueticks_oauth"
down_revision = "0002_oauth_credentials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "blueticks_oauth_states",
        sa.Column("state_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("client_id", sa.String(length=500), nullable=False),
        sa.Column("code_verifier_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_blueticks_oauth_states_user_id", "blueticks_oauth_states", ["user_id"])
    op.create_table(
        "blueticks_oauth_clients",
        sa.Column("user_id", sa.String(length=160), primary_key=True),
        sa.Column("client_id", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("blueticks_oauth_clients")
    op.drop_index("ix_blueticks_oauth_states_user_id", table_name="blueticks_oauth_states")
    op.drop_table("blueticks_oauth_states")
