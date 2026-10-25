import os
import tempfile

# Wordt geladen voor elke app-import: settings en engine zijn gecachet, dus de testdatabase
# moet hier al vastliggen. Anders draaien integratietests tegen de dev-database.
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("ALLOWLIST", "admin@example.test=admin,editor@example.test=editor")
# Publiceren: vaste testsleutel (geen echt geheim) en het Sandbox-netwerk.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dGVzdC1zbGV1dGVsLWFsbGVlbi12b29yLXRlc3RzLTA=")
os.environ.setdefault("ALLOW_SANDBOX_PROVIDER", "true")
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["STORAGE_ROOT"] = tempfile.mkdtemp(prefix="flow-social-test-")
