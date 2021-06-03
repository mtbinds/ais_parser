
import logging
import time
import threading
import psycopg2
import queue
from ais_parser.utils import interpolatepassages, valid_imo, detect_locationoutliers

EXPORT_COMMANDS = [('run', 'Extract a Subset of Clean Ships into ais_extended Tables')]
INPUTS = []
OUTPUTS = ['aisdb']


def run(inp, out, n_threads=2, dropindices=False):
    aisdb = out['aisdb']
    valid_imos, imo_mmsi_intervals = filter_good_ships(aisdb)
    logging.info("Got %d Valid IMO Numbers, Using %d MMSI Numbers", len(valid_imos), len(imo_mmsi_intervals))

    # pre filter intervals
    def filter_intervals(interval):
        remain = get_remaining_interval(aisdb, *interval)
        if not remain is None:
            return [interval[0], interval[1], remain[0], remain[1]]
        else:
            return None

    filtered_intervals = map(filter_intervals, imo_mmsi_intervals)
    # sorting intervals by MMSI improves performance on a clustered table
    sorted_intervals = sorted(filter(None, filtered_intervals), key=lambda x: x[0])
    logging.info("%d Intervals to Import", len(sorted_intervals))
    # insert ships into extended table.
    if len(sorted_intervals) > 0:
        if dropindices:
            aisdb.extended.drop_indices()
        generate_extended_table(aisdb, sorted_intervals, n_threads=n_threads)
        if dropindices:
            aisdb.extended.create_indices()
    logging.info("Vessel Importer Done.")


def filter_good_ships(aisdb):

    with aisdb.conn.cursor() as cur:
        cur.execute("SELECT distinct imo_number from {}".format(aisdb.imolist.get_name()))
        imo_list = [row[0] for row in cur.fetchall() if valid_imo(row[0])]
        logging.info("Checking %d IMOs", len(imo_list))

        valid_imos = []
        imo_mmsi_intervals = []

        for imo_number in imo_list:
            cur.execute("""select a.mmsi, a.imo_number, (a.first_seen, a.last_seen) overlaps (b.first_seen, b.last_seen), LEAST(a.first_seen, b.first_seen), GREATEST(a.last_seen, b.last_seen)
                    from imo_list as a
                    join imo_list as b on a.mmsi = b.mmsi and b.imo_number is null
                    where a.imo_number = %s
                    ORDER BY LEAST(a.first_seen, b.first_seen) ASC""", [imo_number])
            mmsi_ranges = cur.fetchall()
            if len(mmsi_ranges) == 0:
                # logging.info("No MMSI numbers for IMO_Number %s", imo_number)
                continue

            valid = True
            last_end = None
            for mmsi, _, overlap, start, end in mmsi_ranges:
                if not overlap:
                    valid = False
                    # logging.info("(%s, %s) does not overlap (%s, _)", mmsi, imo_number, mmsi)
                    break
                if last_end != None and start < last_end:
                    valid = False
                    # logging.info("IMO: %s, overlapping MMSI intervals", imo_number)
                    break
                last_end = end

            if valid:
                # check for other users of this mmsi number
                mmsi_list = [row[0] for row in mmsi_ranges]
                cur.execute("""select a.mmsi, a.imo_number, b.imo_number
                    from imo_list as a
                    join imo_list as b on a.mmsi = b.mmsi and a.imo_number < b.imo_number
                    where a.mmsi IN ({})""".format(','.join(['%s' for i in mmsi_list])), mmsi_list)
                if cur.rowcount == 0:
                    # yay its valid!
                    valid_imos.append(imo_number)
                    for mmsi, _, _, start, end in mmsi_ranges:
                        imo_mmsi_intervals.append([mmsi, imo_number, start, end])
                else:
                    pass
                    # logging.info("IMO_Number: %s, reuse of MMSI", imo_number)

        return valid_imos, imo_mmsi_intervals


def cluster_table(aisdb, table):

    with aisdb.conn.cursor() as cur:
        index_name = table.name.lower() + "_mmsi_idx"
        logging.info("Clustering Table %s on Index %s. This May Take a While...",
                     table.name, index_name)
        cur.execute("CLUSTER {} USING {}".format(table.name, index_name))


def generate_extended_table(aisdb, intervals, n_threads=2):
    logging.info("Inserting %d Squeaky Clean MMSIs", len(intervals))

    start = time.time()

    interval_q = queue.Queue()
    for interval in sorted(intervals, key=lambda x: x[0]):
        interval_q.put(interval)

    pool = [threading.Thread(target=interval_copier, daemon=True, args=(aisdb.options, interval_q)) for i in
            range(n_threads)]
    [t.start() for t in pool]

    total = len(intervals)
    remain = total
    start = time.time()
    while not interval_q.empty():
        q_size = interval_q.qsize()
        if remain > q_size:
            logging.info("%d/%d MMSIs Completed, %f/s.", total - q_size, total,
                         (total - q_size) / (time.time() - start))
            remain = q_size
        time.sleep(5)
    interval_q.join()


def interval_copier(db_options, interval_q):
    from ais_parser.repositories import aisdb as db
    aisdb = db.load(db_options)
    logging.debug("Start Interval Copier Task")
    with aisdb:
        while not interval_q.empty():
            interval = interval_q.get()
            process_interval_series(aisdb, interval)
            interval_q.task_done()


def process_interval_series(aisdb, interval):
    mmsi, imo_number, start, end = interval
    t_start = time.time()
    # constrain interval based on previous import
    remaining_work = get_remaining_interval(aisdb, mmsi, imo_number, start, end)
    if remaining_work is None:
        # logging.info("Interval was already inserted: (%s, %s, %s, %s)", mmsi, imo, start, end)
        return 0
    else:
        start, end = remaining_work

    # get data for this interval range
    msg_stream = aisdb.get_message_stream(mmsi, from_ts=start, to_ts=end, use_clean_db=True)
    row_count = len(msg_stream)
    if row_count == 0:
        logging.warning("No Rows to Insert for Interval %s", interval)
        return 0

    insert_message_stream(aisdb, [mmsi, imo_number, start, end], msg_stream)

    # finished, commit
    aisdb.conn.commit()
    logging.debug("Inserted %d Rows for MMSI %d. (%fs)", row_count, mmsi, time.time() - t_start)
    return row_count


def insert_message_stream(aisdb, interval, msg_stream):

    mmsi, imo_number, start, end = interval

    valid = []
    invalid = []

    # call the message filter
    k = 0
    i = 0
    j = 0

    for val in detect_locationoutliers(msg_stream):

        if val is False:

            valid.insert(i, msg_stream[k])
            i = i+1
            k = k+1

        else:

            invalid.insert(j, msg_stream.get[k])
            j = j + 1
            k = k+1

    artificial = interpolatepassages(valid)

    aisdb.extended.insert_rowsbatch(valid + list(artificial))

    # mark the work we've done
    aisdb.action_log.insert_row({'action': "import",
                                 'mmsi': mmsi,
                                 'ts_from': start,
                                 'ts_to': end,
                                 'count': len(valid)})

    aisdb.action_log.insert_row({'action': "outlier detection (noop)",
                                 'mmsi': mmsi,
                                 'ts_from': start,
                                 'ts_to': end,
                                 'count': len(invalid)})

    aisdb.action_log.insert_row({'action': "interpolation (noop)",
                                 'mmsi': mmsi,
                                 'ts_from': start,
                                 'ts_to': end,
                                 'count': len(artificial)})

    upsert_interval_to_imolist(aisdb, mmsi, imo_number, start, end)


def get_remaining_interval(aisdb, mmsi, imo_number, start, end):
    with aisdb.conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT tsrange(%s, %s) - tsrange(%s, %s) * tsrange(first_seen - interval '1 second', last_seen + interval '1 second') FROM {} WHERE mmsi = %s AND imo_number = %s".format(
                    aisdb.clean_imolist.name),
                [start, end, start, end, mmsi, imo_number])
            row = cur.fetchone()
            if not row is None:
                sub_interval = row[0]
                if sub_interval.isempty:
                    return None
                else:
                    return sub_interval.lower, sub_interval.upper
            else:
                return (start, end)
        except psycopg2.Error as e:
            logging.warning("Error Calculating timetamp Intersection for MMSI %d: %s", mmsi, e)
            return None


def upsert_interval_to_imolist(aisdb, mmsi, imo_number, start, end):
    with aisdb.conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM {} WHERE mmsi = %s AND imo_number = %s"
                    .format(aisdb.clean_imolist.name),
                    [mmsi, imo_number])
        count = cur.fetchone()[0]
        if count == 1:
            cur.execute("""UPDATE {} SET
                        first_seen = LEAST(first_seen, %s),
                        last_seen = GREATEST(last_seen, %s)
                        WHERE mmsi = %s AND imo_number = %s""".format(aisdb.clean_imolist.name),
                        [start, end, mmsi, imo_number])
        elif count == 0:
            aisdb.clean_imolist.insert_row({'mmsi': mmsi, 'imo_number': imo_number, 'first_seen': start,
                                            'last_seen': end})
