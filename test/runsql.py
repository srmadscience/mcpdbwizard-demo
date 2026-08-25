"""Run a SQL*Plus-style script through python-oracledb thin mode.

No Oracle client needed - just `pip install oracledb`. Usage:

    export DB_PASS=...
    python test/runsql.py db/mcp_db_demo_drop.sql --tolerant
    python test/runsql.py db/mcp_db_demo_ddl.sql
    python test/runsql.py db/mcp_db_demo_dml.sql

--tolerant ignores "object does not exist" errors, which is what you want when
running the drop script against a schema that is already partly empty.
"""
import re
import sys

import oracledb

import dbconfig

PLSQL_START = re.compile(
    r'^\s*(CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE)'
    r'|DECLARE|BEGIN)\b', re.I)


def statements(text):
    """Split a script into statements: ';' ends SQL, a lone '/' ends a PL/SQL block."""
    buf, in_plsql = [], False
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped == '/':
            if buf:
                yield '\n'.join(buf).strip()
                buf, in_plsql = [], False
            continue
        if not buf and not stripped:
            continue
        if not buf and PLSQL_START.match(line):
            in_plsql = True
        buf.append(line)
        if not in_plsql and stripped.endswith(';'):
            yield '\n'.join(buf).strip()[:-1].strip()
            buf = []
    if buf and '\n'.join(buf).strip():
        yield '\n'.join(buf).strip()


def label(sql):
    return ' '.join(sql.split()[:5])[:60]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    tolerant = '--tolerant' in sys.argv
    if not args:
        sys.exit("usage: python test/runsql.py <script.sql> [--tolerant]")
    path = args[0]

    conn = dbconfig.connect()
    cur = conn.cursor()
    ok = failed = 0
    for sql in statements(open(path, encoding='utf-8').read()):
        if not sql:
            continue
        try:
            cur.execute(sql)
            ok += 1
        except oracledb.DatabaseError as e:            # report, do not stop
            code = getattr(e.args[0], 'code', None) if e.args else None
            if tolerant and code in (942, 2289, 4043):  # does not exist
                print(f'  skip  {label(sql)}  (not there)')
                continue
            failed += 1
            print(f'  FAIL  {label(sql)}\n        {str(e).splitlines()[0]}')
    conn.commit()

    cur.execute("""SELECT object_type, object_name, status FROM user_objects
                   WHERE status <> 'VALID' ORDER BY object_type, object_name""")
    bad = cur.fetchall()
    print(f'\n{path}: {ok} ok, {failed} failed')
    if bad:
        print('INVALID OBJECTS:')
        for t, n, s in bad:
            print(f'  {t} {n} = {s}')
    conn.close()
    sys.exit(1 if failed or bad else 0)


if __name__ == '__main__':
    main()
