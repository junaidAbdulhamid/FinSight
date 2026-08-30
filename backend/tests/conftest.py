import os

# Test-only placeholders satisfy fail-closed startup validation; no network call is made unless mocked.
os.environ.setdefault("FINSIGHT_SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("FINSIGHT_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_placeholder")
