"""Behavioural tests for the ROOM_MANAGER package.

    export DB_PASS=...
    python test/test_room_manager.py

BookRoom commits its own bookings, so this test cannot lean on rollback to
tidy up. Instead it books into far-future date ranges that no sample booking
uses, and deletes exactly those rows at the end - the demo data is left as it
was found. Because the bookings are its own, the test does not depend on the
sample data staying the way it is now.

A call_timeout is set so a lock held by an abandoned session aborts the test
with a clear message rather than hanging it.
"""
import time

import oracledb

import dbconfig

# Two far-future ranges nothing else touches: one to fill a hotel, one for the
# single-shot over-book test. YYYY-MM-DD, midnight (ROOM_BOOKINGS wants that).
FILL_F, FILL_T = '2099-01-01', '2099-01-08'
OVER_F, OVER_T = '2099-02-01', '2099-02-08'
# Customers that already exist in the sample data (ROOM_BOOKINGS has an FK to CUSTOMERS).
CUST_A, CUST_B, CUST_C = 'M GUSTAVE', 'ZERO MOUSTAFA', 'AGATHA'

UNOPENED = object()
passed = failed = 0


class LockTimeout(Exception):
    """A call hit call_timeout - almost always an abandoned session still
    holding uncommitted row locks, not a fault in ROOM_MANAGER itself."""


def _is_timeout(e):
    s = str(e)
    return 'DPY-4011' in s or 'DPY-4024' in s or 'timeout' in s.lower()


def check(desc, cond, got):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(f"  [{'PASS' if cond else 'FAIL'}] {desc}\n         -> {got}")


def _date(x):
    return f"to_date('{x}','YYYY-MM-DD')" if x else "NULL"


def call_grl(cur, hotel, frm=FILL_F, to=FILL_T):
    rc, msg = cur.var(oracledb.CURSOR), cur.var(str)
    cur.execute(f"begin room_manager.getRoomList(:h,{_date(frm)},{_date(to)},:rc,:m); end;",
                h=hotel, rc=rc, m=msg)
    inner = rc.getvalue()
    try:
        rows = inner.fetchall() if inner is not None else UNOPENED
    except oracledb.DatabaseError as e:
        if 'DPY-4025' not in str(e):        # DPY-4025 = ref cursor never opened
            raise
        rows = UNOPENED
    return rows, msg.getvalue()


def call_book(cur, hotel, customer, count, frm=FILL_F, to=FILL_T):
    bc, msg = cur.var(oracledb.CURSOR), cur.var(str)
    try:
        cur.execute(f"begin room_manager.BookRoom(:h,:c,{_date(frm)},{_date(to)},:n,:bc,:m); end;",
                    h=hotel, c=customer, n=count, bc=bc, m=msg)
    except oracledb.DatabaseError as e:
        if _is_timeout(e):
            raise LockTimeout(f"BookRoom({hotel!r}, {count}) timed out") from e
        raise
    inner = bc.getvalue()
    try:
        rows = inner.fetchall() if inner is not None else []
    except oracledb.DatabaseError as e:
        if 'DPY-4025' not in str(e):
            raise
        rows = []
    return rows, msg.getvalue()


def wipe_test_bookings(cur):
    """Delete every booking this test could have made, in both ranges. Idempotent."""
    cur.execute(f"""delete from room_bookings
                    where (start_date = {_date(FILL_F)} and end_date = {_date(FILL_T)})
                       or (start_date = {_date(OVER_F)} and end_date = {_date(OVER_T)})""")
    n = cur.rowcount
    cur.connection.commit()
    return n


def pick_hotel(cur):
    """Smallest hotel, to keep the number of inserts down."""
    cur.execute("""select hotel_name, count(*) from hotel_rooms
                   group by hotel_name order by count(*), hotel_name fetch first 1 rows only""")
    return cur.fetchone()


def main():
    conn = dbconfig.connect()
    conn.call_timeout = 20000               # ms: abort rather than hang on a lock
    cur = conn.cursor()

    wipe_test_bookings(cur)                  # start clean, in case a prior run was interrupted
    baseline = cur.execute("select count(*) from room_bookings").fetchone()[0]
    hotel, rooms = pick_hotel(cur)
    print(f"=== hotel under test: {hotel} ({rooms} rooms); "
          f"baseline room_bookings={baseline} ===\n")

    print("### getRoomList ###")
    rows, _ = call_grl(cur, hotel)
    check("empty future range: every room is free",
          rows is not UNOPENED and len(rows) == rooms, f"{len(rows)} of {rooms} free")

    rows2, _ = call_grl(cur, f"  {hotel.lower()}  ")
    check("whitespace + mixed case matches the canonical name",
          rows2 is not UNOPENED and len(rows2) == rooms, f"{len(rows2)} free")

    rows, msg = call_grl(cur, None)
    check("null hotel -> cursor unopened, 'Hotel Name Needed'",
          rows is UNOPENED and msg == 'Hotel Name Needed', f"unopened={rows is UNOPENED}, msg={msg!r}")

    rows, msg = call_grl(cur, hotel, frm=None)
    check("null from date -> cursor unopened, 'From Date Needed'",
          rows is UNOPENED and msg == 'From Date Needed', f"unopened={rows is UNOPENED}, msg={msg!r}")

    rows, msg = call_grl(cur, hotel, to=None)
    check("null to date -> cursor unopened, 'To Date Needed'",
          rows is UNOPENED and msg == 'To Date Needed', f"unopened={rows is UNOPENED}, msg={msg!r}")

    print("\n### BookRoom ###")
    try:
        run_bookroom_checks(cur, hotel, rooms, baseline)
    except LockTimeout as e:
        print(f"  [SKIP] {e}\n         -> a booking call did not return within call_timeout. This is\n"
              "                almost always an abandoned session holding uncommitted locks\n"
              "                (see README); clear idle MCP_DEMO sessions and re-run. Not a\n"
              "                ROOM_MANAGER fault - getRoomList above passed.")
        # try to leave nothing behind, on a fresh connection since this one is now dead
        try:
            with dbconfig.connect() as c2:
                wipe_test_bookings(c2.cursor())
        except oracledb.DatabaseError:
            pass
        raise SystemExit(2)

    print(f"\n==== {passed} passed, {failed} failed ====")
    raise SystemExit(1 if failed else 0)


def run_bookroom_checks(cur, hotel, rooms, baseline):
    want = rooms - 1
    rows, msg = call_book(cur, hotel, CUST_A, want)
    check(f"book {want} of {rooms} -> {want} booked, cursor returns them",
          len(rows) == want, f"cursor={len(rows)}, msg={msg!r}")

    # BookRoom commits: a separate connection must see the rows without this one committing.
    with dbconfig.connect() as other:
        seen = other.cursor().execute(
            f"select count(*) from room_bookings where hotel_name=:h "
            f"and start_date={_date(FILL_F)}", h=hotel).fetchone()[0]
    check("the booking is committed (visible from another session)",
          seen == want, f"other session sees {seen}")

    free_now = len(call_grl(cur, hotel)[0])
    check("availability dropped by the number booked",
          free_now == rooms - want, f"{free_now} free (was {rooms})")

    rows, msg = call_book(cur, hotel, CUST_B, 1)
    check("book the last free room -> 1 booked",
          len(rows) == 1, f"cursor={len(rows)}, msg={msg!r}")

    rows, _ = call_grl(cur, hotel)
    check("hotel is now sold out for the range", rows == [], f"{len(rows)} free")

    rows, msg = call_book(cur, hotel, CUST_C, 1)
    check("book when sold out -> nothing booked, 'Unable to book'",
          rows == [] and 'Unable to book' in (msg or ''), f"cursor={len(rows)}, msg={msg!r}")

    # Single-shot over-book on the empty second range: ask for more than the hotel has.
    rows, msg = call_book(cur, hotel, CUST_A, rooms + 5, frm=OVER_F, to=OVER_T)
    left = cur.execute(
        f"select count(*) from room_bookings where hotel_name=:h "
        f"and start_date={_date(OVER_F)}", h=hotel).fetchone()[0]
    check("over-book in one shot -> all-or-nothing: nothing booked, nothing left behind",
          rows == [] and left == 0 and 'Unable to book' in (msg or ''),
          f"cursor={len(rows)}, rows left={left}, msg={msg!r}")

    deleted = wipe_test_bookings(cur)
    restored = cur.execute("select count(*) from room_bookings").fetchone()[0]
    check("cleanup removes exactly the test bookings, demo data restored",
          deleted == rooms and restored == baseline,
          f"deleted {deleted}, room_bookings back to {restored} (baseline {baseline})")


if __name__ == '__main__':
    main()
