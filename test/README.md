# Tests

Pure-Python checks that run against the demo schema with the `oracledb` thin
driver - no Oracle client needed.

```sh
pip install oracledb
export DB_PASS=...                     # the schema password; never stored here
python test/runsql.py db/mcp_db_demo_drop.sql --tolerant
python test/runsql.py db/mcp_db_demo_ddl.sql
python test/runsql.py db/mcp_db_demo_dml.sql
python test/test_room_manager.py
```

Host, service and user default to the demo database and can be overridden with
`ORACLE_DSN` and `ORACLE_USER` (see `dbconfig.py`).

- `runsql.py` - runs a SQL*Plus-style script (`;` statements, `/`-terminated
  PL/SQL blocks) and reports any objects left invalid.
- `test_room_manager.py` - exercises `ROOM_MANAGER`. Everything it books is
  rolled back, so the demo data is left untouched.
