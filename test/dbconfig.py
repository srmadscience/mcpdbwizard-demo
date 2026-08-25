"""Shared connection settings for the test scripts.

The password never lives in this repo: it comes from the environment, the same
way mcpdemo.json expects FROM_ENV_VARIABLE_DB_PASS. Set it before running:

    export DB_PASS=...

Host, service and user default to the demo database but can be overridden with
ORACLE_DSN and ORACLE_USER.
"""
import os
import sys

DSN = os.environ.get("ORACLE_DSN", "10.13.1.226:1521/FREEPDB1")
USER = os.environ.get("ORACLE_USER", "MCP_DEMO")


def password():
    pw = os.environ.get("DB_PASS")
    if not pw:
        sys.exit("DB_PASS is not set. export DB_PASS=<password> before running.")
    return pw


def connect():
    import oracledb
    return oracledb.connect(user=USER, password=password(), dsn=DSN)
