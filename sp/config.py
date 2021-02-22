import os

CONN_STR = os.environ.get("SP_CONN_STR") or "sqlite:///validation.db"
CONN_ARGS = {} if "PYTEST" in os.environ else {"pool_size": 20, "max_overflow": 0}
