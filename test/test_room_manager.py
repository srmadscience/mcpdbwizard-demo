"""Behavioural tests for the ROOM_MANAGER package against the demo data.

    export DB_PASS=...
    python test/test_room_manager.py

Exercises getRoomList and BookRoom. Everything BookRoom inserts is rolled back
at the end, so the demo data is left exactly as it was found. Availability is
measured from getRoomList rather than hard-coded, so the tests keep working if
the sample bookings change.

A call_timeout is set so a lock held by an abandoned session aborts the test
rather than hanging it.
"""
import time

import oracledb

import dbconfig

FROM, TO = '2026-05-04', '2026-05-11'
UNOPENED = object()
passed = failed = 0


def check(desc, cond, got):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(f"  [{'PASS' if cond else 'FAIL'}] {desc}\n         -> {got}")


def _date(x):
    return f"to_date('{x}','YYYY-MM-DD')" if x else "NULL"


def call_grl(cur, hotel, frm=FROM, to=TO):
    rc, msg = cur.var(oracledb.CURSOR), cur.var(str)
    cur.execute(f"begin room_manager.getRoomList(:h,{_date(frm)},{_date(to)},:rc,:m); end;",
                h=hotel, rc=rc, m=msg)
    inner = rc.getvalue()
    try:
        rows = inner.fetchall() if inner is not None else UNOPENED
    except oracledb.DatabaseError as e:
        if 'DPY-4025' not in str(e):        # DPY-4025 = cursor never opened
            raise
        rows = UNOPENED
    return rows, msg.getvalue()


def call_book(cur, hotel, customer, count, frm=FROM, to=TO):
    bc, msg = cur.var(oracledb.CURSOR), cur.var(str)
    cur.execute(f"begin room_manager.BookRoom(:h,:c,{_date(frm)},{_date(to)},:n,:bc,:m); end;",
                h=hotel, c=customer, n=count, bc=bc, m=msg)
    inner = bc.getvalue()
    try:
        rows = inner.fetchall() if inner is not None else []
    except oracledb.DatabaseError as e:
        if 'DPY-4025' not in str(e):
            raise
        rows = []
    return rows, msg.getvalue()


def count_bookings(cur):
    return cur.execute("select count(*) from room_bookings").fetchone()[0]


def main():
    conn = dbconfig.connect()
    conn.call_timeout = 15000               # ms: abort rather than hang on a lock
    cur = conn.cursor()

    free_tt = len(call_grl(cur, 'THORIUM TOWERS')[0])
    free_gb = len(call_grl(cur, 'GRAND BUDAPEST')[0])
    print(f"=== baseline {FROM}..{TO}: THORIUM TOWERS free={free_tt}, "
          f"GRAND BUDAPEST free={free_gb} ===\n")
    if free_tt < 2 or free_gb != 0:
        print("NOTE: expected THORIUM TOWERS to have >=2 free and GRAND BUDAPEST "
              "to be sold out for this week; the demo data may have changed.")

    print("### getRoomList ###")
    rows, _ = call_grl(cur, 'THORIUM TOWERS')
    check("available hotel returns its free rooms",
          rows is not UNOPENED and len(rows) == free_tt, f"{len(rows)} rooms")

    rows2, _ = call_grl(cur, '  thorIum towErs  ')
    check("whitespace + mixed case matches the canonical name",
          rows2 is not UNOPENED and len(rows2) == free_tt,
          f"{len(rows2)} rooms (canonical {free_tt})")

    rows, _ = call_grl(cur, 'GRAND BUDAPEST')
    check("sold-out hotel returns 0 rooms",
          rows is not UNOPENED and rows == [], f"{len(rows)} rooms")

    rows, msg = call_grl(cur, None)
    check("null hotel -> cursor unopened, 'Hotel Name Needed'",
          rows is UNOPENED and msg == 'Hotel Name Needed',
          f"unopened={rows is UNOPENED}, msg={msg!r}")

    rows, msg = call_grl(cur, 'THORIUM TOWERS', frm=None)
    check("null from date -> cursor unopened, 'From Date Needed'",
          rows is UNOPENED and msg == 'From Date Needed',
          f"unopened={rows is UNOPENED}, msg={msg!r}")

    rows, msg = call_grl(cur, 'THORIUM TOWERS', to=None)
    check("null to date -> cursor unopened, 'To Date Needed'",
          rows is UNOPENED and msg == 'To Date Needed',
          f"unopened={rows is UNOPENED}, msg={msg!r}")

    print("\n### BookRoom ###")
    start = count_bookings(cur)

    want = free_tt - 1                      # book all but one of the free rooms
    rows, msg = call_book(cur, 'THORIUM TOWERS', 'M GUSTAVE', want)
    after = count_bookings(cur)
    check(f"book {want} of {free_tt} free -> {want} booked, cursor returns them",
          len(rows) == want and after == start + want,
          f"cursor={len(rows)}, table +{after - start}, msg={msg!r}")

    free_now = len(call_grl(cur, 'THORIUM TOWERS')[0])
    check("availability drops by the number booked",
          free_now == free_tt - want, f"free now {free_now} (was {free_tt})")

    mark = count_bookings(cur)
    rows, msg = call_book(cur, 'THORIUM TOWERS', 'ZERO MOUSTAFA', 99)
    after = count_bookings(cur)
    check("over-book -> all-or-nothing: nothing inserted, empty cursor, 'Unable to book'",
          after == mark and rows == [] and 'Unable to book' in (msg or ''),
          f"table delta={after - mark}, cursor={len(rows)}, msg={msg!r}")

    rows, msg = call_book(cur, 'GRAND BUDAPEST', 'AGATHA', 1)
    check("book in sold-out hotel -> nothing booked",
          rows == [] and 'Unable to book' in (msg or ''),
          f"cursor={len(rows)}, msg={msg!r}")

    conn.rollback()
    check("rollback restores the demo data",
          count_bookings(cur) == start,
          f"room_bookings back to {count_bookings(cur)} (started {start})")

    print(f"\n==== {passed} passed, {failed} failed ====")
    conn.close()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
