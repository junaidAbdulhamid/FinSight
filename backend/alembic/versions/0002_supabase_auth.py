"""Allow Supabase-managed identities without local password hashes."""
from alembic import op
import sqlalchemy as sa

revision = "0002_supabase_auth"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE users SET password_hash = 'supabase-managed-no-local-password' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
