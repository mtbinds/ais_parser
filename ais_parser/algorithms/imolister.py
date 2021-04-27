
import logging
import time

EXPORT_COMMANDS = [('run', 'create or update the imo list table.')]
INPUTS = []
OUTPUTS = ["aisdb"]

def run(_, out):
    create_imo_list(out['aisdb'])

def create_imo_list(aisdb):
    """Create the imo list table from MMSI, IMO_Number pairs in clean and dirty tables.

    This method collects the unique MMSI, IMO_Number pairs from a table, and the time
    intervals over-which they have been seen in the data. These tuples are
    then upserted into the `imo_list` table.

    Removes cases where ships have clashing MMSI numbers within a time threshold.

    On the clean table pairs with no IMO_Number are also collected to get the
    activity intervals of MMSI numbers. On the dirty table only messages
    specifying an IMO are collected.

    Arguments
    ---------
    aisdb : postgresdb
        The database upon which to operate
    """

    with aisdb.conn.cursor() as cur:
        start = time.time()

        # collect existing set of mmsi, imo_number tuples in imo_list
        cur.execute("SELECT mmsi, imo_number FROM {}".format(aisdb.imolist.get_name()))
        existing_tuples = set(cur.fetchall())
        logging.info("Existing mmsi, imo_number Pairs = %d (%fs)", len(existing_tuples), time.time()-start)

        # query for mmsi, imo_number, interval tuples from clean db, and then upsert into
        # imo_list table.
        logging.info("Getting mmsi, imo_number Pairs from Clean DB")
        start = time.time()
        cur.execute("SELECT mmsi, imo_number, MIN(complete_sys_date), MAX(complete_sys_date) FROM {} GROUP BY mmsi, imo_number".format(aisdb.clean.get_name()))
        logging.info("Got New mmsi, imo_number Pairs List (%fs)", time.time()-start)
        _upsert_imo_tuples(aisdb, cur, existing_tuples)

        # query for mmsi, imo_number, interval tuples from dirty db, and then upsert into
        # imo_list table.
        logging.info("Getting mmsi, imo_number Pairs from Dirty DB")
        start = time.time()
        cur.execute("SELECT mmsi, imo_number, MIN(complete_sys_date), MAX(complete_sys_date) FROM {} WHERE message_type = 5 GROUP BY mmsi, imo_number".format(aisdb.dirty.get_name()))
        logging.info("Got New mmsi, imo_number Pairs List (%fs)", time.time()-start)
        _upsert_imo_tuples(aisdb, cur, existing_tuples)

        aisdb.conn.commit()

def _upsert_imo_tuples(aisdb, result_cursor, existing_tuples):
    """Inserts or updates rows in the imo_list table depending on the mmsi, imo_number
    pair's presence in the table.

    Arguments
    ---------
    result_cursor :
        An iterator of (mmsi, imo_number, start, end) tuples.
    existing_tuples :
        A set of (mmsi, imo_number) pairs which should be updated rather than inserted.

    """

    with aisdb.conn.cursor() as insert_cur:
        start = time.time()
        insert_ctr = 0
        update_ctr = 0
        for mmsi, imo_number, min_time, max_time in result_cursor:
            if (mmsi, imo_number) in existing_tuples:
                insert_cur.execute("""UPDATE {} SET
                    first_seen = LEAST(first_seen, %s),
                    last_seen = GREATEST(last_seen, %s)
                    WHERE mmsi = %s AND imo_number = %s""".format(aisdb.imolist.get_name()), [min_time, max_time, mmsi, imo_number])
                update_ctr = update_ctr + insert_cur.rowcount
            else:
                insert_cur.execute("INSERT INTO {} (mmsi, imo_number, first_seen, last_seen) VALUES (%s,%s,%s,%s)".format(aisdb.imolist.get_name()), [mmsi, imo_number, min_time, max_time])
                insert_ctr = insert_ctr + 1
        logging.info("Inserted %d New Rows, Updated %d Rows (%f)", insert_ctr, update_ctr, time.time()-start)
