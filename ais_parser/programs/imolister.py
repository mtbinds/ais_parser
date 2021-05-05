
import logging
import time

EXPORT_COMMANDS = [('run', 'create or update the imo list table.')]
INPUTS = []
OUTPUTS = ["aisdb"]

def run(_, out):
    create_imolist(out['aisdb'])

def create_imolist(aisdb):

    with aisdb.conn.cursor() as cur:
        start = time.time()

        # collecter un ensemble existant de tuples mmsi, imo_number dans imo_list
        cur.execute("SELECT mmsi, imo_number FROM {}".format(aisdb.imolist.get_name()))
        existing_tuples = set(cur.fetchall())
        logging.info("Existing mmsi, imo_number Pairs = %d (%fs)", len(existing_tuples), time.time()-start)

        # requête pour mmsi, imo_number, tuples d'intervalle à partir de la base de données propre, puis les insérer dans la table imo_list.
        logging.info("Getting mmsi, imo_number Pairs from Clean DB")
        start = time.time()
        cur.execute("SELECT mmsi, imo_number, MIN(complete_sys_date), MAX(complete_sys_date) FROM {} GROUP BY mmsi, imo_number".format(aisdb.clean.get_name()))
        logging.info("Got New mmsi, imo_number Pairs List (%fs)", time.time()-start)
        _upsert_imo_tuples(aisdb, cur, existing_tuples)

        # requête pour mmsi, imo_number, tuples d'intervalle à partir de la base de données sale, puis les insérer dans la table imo_list.
        logging.info("Getting mmsi, imo_number Pairs from Dirty DB")
        start = time.time()
        cur.execute("SELECT mmsi, imo_number, MIN(complete_sys_date), MAX(complete_sys_date) FROM {} WHERE message_type = 5 GROUP BY mmsi, imo_number".format(aisdb.dirty.get_name()))
        logging.info("Got New mmsi, imo_number Pairs List (%fs)", time.time()-start)
        _upsert_imo_tuples(aisdb, cur, existing_tuples)

        aisdb.conn.commit()

def _upsert_imo_tuples(aisdb, result_cursor, existing_tuples):

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
