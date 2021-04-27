"""Classes for connection to and management of database tables

PgsqlRepository
---------------
Sets up a connection to a ais_parser database repository

Table
-----
Used to encapsulate a ais_parser database table

"""
import logging

import psycopg2


def load(options, readonly=False):
    return PgsqlRepository(options)


class PgsqlRepository(object):

    def __init__(self, options, readonly=False):
        self.options = options
        self.host = options['host']
        self.db = options['db']
        if 'postgis' in options.keys():
            self.postgis = options['postgis']
        else:
            self.postgis = 'yes'
        if readonly:
            self.user = options['ro_user']
            self.password = options['ro_pass']
        else:
            self.user = options['user']
            self.password = options['pass']
        self.conn = None

    def connection(self):
        return psycopg2.connect(host=self.host, database=self.db, user=self.user, password=self.password, connect_timeout=3)

    def __enter__(self):
        self.conn = self.connection()

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()


class Table(object):
    """A database table
    """

    def __init__(self, db, name, cols, indices=None, constraint=None,
                 foreign_keys=None):
        self.db = db
        self.name = name
        self.cols = cols
        self.indices = indices
        self.foreign_keys = foreign_keys
        if self.foreign_keys is None:
            self.foreign_keys = []
        if self.indices is None:
            self.indices = []
        self.constraint = constraint
        if self.constraint is None:
            self.constraint = []

    def get_name(self):
        return self.name

    def create(self):
        """ Creates tables in the database
        """
        with self.db.conn.cursor() as cur:
            logging.info("CREATING " + self.name + " table")
            columns = []
            fks = [x[0] for x in self.foreign_keys]
            for c in self.cols:
                if c[0].lower() not in fks:
                    columns.append("\"{}\" {}".format(c[0].lower(), c[1]))
                else:
                    fk = [x for x in self.foreign_keys if x[0] == c[0]]
                    columns.append("\"{0}\" {1} REFERENCES {2} (\"{3}\")".format(
                        c[0].lower(), c[1], fk[0][1], fk[0][2]))
            # columns = ["\"{}\" {}".format(c[0].lower(),
            # c[1]) for c in self.cols]
            sql = "CREATE TABLE IF NOT EXISTS \"" + self.name + \
                "\" (" + ','.join(columns + self.constraint) + ")"
            # logging.debug(cur.mogrify(sql))
            cur.execute(sql)
            self.db.conn.commit()

        self.create_indices()

    def create_indices(self):
        with self.db.conn.cursor() as cur:
            tbl = self.name
            for idx, cols in self.indices:
                idxn = tbl.lower() + "_" + idx
                try:
                    logging.info("CREATING INDEX " + idxn + " on Table " + tbl)
                    cur.execute("CREATE INDEX \"" + idxn + "\" ON \"" + tbl + "\" USING btree (" +
                                ','.join(["\"{}\"".format(s.lower()) for s in cols]) + ")")
                except psycopg2.ProgrammingError:
                    logging.info("Index " + idxn + " Already Exists")
                    self.db.conn.rollback()
            self.db.conn.commit()

    def drop_indices(self):
        with self.db.conn.cursor() as cur:
            tbl = self.name
            for idx, _ in self.indices:
                idxn = tbl.lower() + "_" + idx
                logging.info("Dropping Index: " + idxn + " on Table " + tbl)
                cur.execute("DROP INDEX IF EXISTS \"" + idxn + "\"")
            self.db.conn.commit()

    def truncate(self):
        """Delete all data in the table."""
        with self.db.conn.cursor() as cur:
            logging.info("Truncating Table " + self.name)
            cur.execute("TRUNCATE TABLE \"" + self.name + "\" CASCADE")
            self.db.conn.commit()

    def status(self):
        """ Returns the approximate number of records in the table

        Returns
        -------
        integer

        """
        with self.db.conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) FROM \"" + self.name + "\"")
                self.db.conn.commit()
                return int(cur.fetchone()[0])
            except psycopg2.ProgrammingError:
                self.db.conn.rollback()
                return -1

    def insert_row(self, data):
        """ Inserts one row into the table
        """
        with self.db.conn.cursor() as cur:
            columnlist = self._get_list_of_columns(data)
            tuplestr = "(" + ",".join("%({})s".format(i)
                                      for i in data.keys()) + ")"
            # logging.debug(cur.mogrify("INSERT INTO " + self.name + " "+ columnlist + " VALUES "+ tuplestr, data))
            cur.execute("INSERT INTO " + self.name + " " +
                        columnlist + " VALUES " + tuplestr, data)

    def _get_list_of_columns(self, row):
        """ Gets a list of the columns from a row dictionary

        Arguments
        ---------
        row : dict
            A dictionary of (field, value) pairs

        Returns
        -------
        columnslist : str
            A str of column names in lower case, wrapped in brackets '()'

        """
        columnlist = '(' + ','.join([c.lower() for c in row.keys()]) + ')'
        return columnlist

    def insert_rows_batch(self, rows):
        """ Inserts a number of rows into the table

        Arguments
        ---------
        rows : list
            A list of dicts of (column, value) pairs
        """
        # check there are rows in insert
        if len(rows) == 0:
            return
        # logging.debug("Row to insert: {}".format(rows[0]))
        with self.db.conn.cursor() as cur:
            columnlist = self._get_list_of_columns(rows[0])
            # logging.debug("Using columns: {}".format(columnlist))
            tuplestr = "(" + ",".join("%({})s".format(i)
                                      for i in rows[0]) + ")"
            # create a single query to insert list of tuples
            # note that mogrify generates a binary string which we must first
            # decode to ascii.
            args = ','.join([cur.mogrify(tuplestr, x).decode('utf-8')
                             for x in rows])
            cur.execute("INSERT INTO " + self.name + " " +
                        columnlist + " VALUES " + args)

    def copy_from_file(self, fname, columns):
        with self.db.conn.cursor() as cur:
            cur.execute("COPY " + self.name + " (" + ','.join(c.lower()
                                                              for c in columns) + ") FROM %s DELIMITER ',' CSV HEADER", [fname])
