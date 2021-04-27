from ais_parser.repositories import sql
import psycopg2
import logging

try:
    import pandas as pd
except ImportError:
    logging.warn("No pandas found")
    pd = None

EXPORT_COMMANDS = [('status', 'Report Status of This Repository.'),
                   ('create', 'Create The Repository.'),
                   ('truncate', 'Delete All Data in This Repository.'),
                   ('update', 'Update The Database Schema')]


def load(options, readonly=False):
    return AISdb(options, readonly)


class AISdb(sql.PgsqlRepository):
    double_type = 'double precision'

    clean_db_spec = {
        'cols': [
            ('MMSI', 'integer'),
            ('Complete_Sys_Date', 'timestamp without time zone'),
            ('Message_Type', 'integer'),
            ('Navigation_Status', 'integer'),
            ('Speed_Over_Ground', double_type),
            ('Longitude', double_type),
            ('Latitude', double_type),
            ('Course_Over_Ground', double_type),
            ('True_Heading', double_type),
            ('IMO_Number', 'integer'),
            ('Draught', double_type),
            ('Destination', 'character varying(255)'),
            ('Vessel_Name', 'character varying(255)'),
            ('Ship_Type', 'integer'),
            ('ETA_Month', 'integer'),
            ('ETA_Day', 'integer'),
            ('ETA_Hour', 'integer'),
            ('ETA_Minute', 'integer'),
            ('source', 'smallint'),
            ('ID', 'BIGSERIAL PRIMARY KEY')
        ],
        'indices': [
            ('dt_idx', ['Complete_Sys_Date']),
            ('imo_idx', ['IMO_Number']),
            ('lonlat_idx', ['Longitude', 'Latitude']),
            ('mmsi_idx', ['MMSI']),
            ('msg_idx', ['Message_Type']),
            ('source_idx', ['source']),
            ('mmsi_imo_idx', ['MMSI', 'IMO_Number'])
        ]
    }

    dirty_db_spec = {
        'cols': [
            ('MMSI', 'bigint'),
            ('Complete_Sys_Date', 'timestamp without time zone'),
            ('Message_Type', 'integer'),
            ('Navigation_Status', 'integer'),
            ('Speed_Over_Ground', double_type),
            ('Longitude', double_type),
            ('Latitude', double_type),
            ('Course_Over_Ground', double_type),
            ('True_Heading', double_type),
            ('IMO_Number', 'integer null'),
            ('Draught', double_type),
            ('Destination', 'character varying(255)'),
            ('Vessel_Name', 'character varying(255)'),
            ('Ship_Type', 'integer'),
            ('ETA_Month', 'integer'),
            ('ETA_Day', 'integer'),
            ('ETA_Hour', 'integer'),
            ('ETA_Minute', 'integer'),
            ('source', 'smallint'),
            ('ID', 'BIGSERIAL PRIMARY KEY')
        ],
        'indices': [
            ('dt_idx', ['Complete_Sys_Date']),
            ('imo_idx', ['IMO_Number']),
            ('lonlat_idx', ['Longitude', 'Latitude']),
            ('mmsi_idx', ['MMSI']),
            ('msg_idx', ['Message_Type']),
            ('source_idx', ['source']),
            ('mmsi_imo_idx', ['MMSI', 'IMO_Number'])
        ]
    }

    sources_db_spec = {
        'cols': [
            ('ID', 'SERIAL PRIMARY KEY'),
            ('timestamp', 'timestamp without time zone DEFAULT now()'),
            ('filename', 'TEXT'),
            ('ext', 'TEXT'),
            ('invalid', 'integer'),
            ('clean', 'integer'),
            ('dirty', 'integer'),
            ('source', 'integer')
        ]
    }

    imolist_db_spec = {
        'cols': [
            ('mmsi', 'integer NOT NULL'),
            ('imo_number', 'integer NULL'),
            ('first_seen', 'timestamp without time zone'),
            ('last_seen', 'timestamp without time zone')
        ],
        'constraint': ['CONSTRAINT imo_list_key UNIQUE (mmsi, imo_number)']
    }

    clean_imo_list = {
        'cols': imolist_db_spec['cols'],
        'constraint': ['CONSTRAINT imo_list_pkey PRIMARY KEY (mmsi, imo_number)']
    }

    action_log_spec = {
        'cols': [
            ('timestamp', 'timestamp without time zone DEFAULT now()'),
            ('action', 'TEXT'),
            ('mmsi', 'integer NOT NULL'),
            ('ts_from', 'timestamp without time zone'),
            ('ts_to', 'timestamp without time zone'),
            ('count', 'integer NULL')
        ],
        'indices': [
            ('ts_idx', ['timestamp']),
            ('action_idx', ['action']),
            ('mmsi_idx', ['mmsi'])
        ],
        'constraint': ['CONSTRAINT action_log_pkey PRIMARY KEY (timestamp, action, mmsi)']
    }

    def __init__(self, options, readonly=False):
        super(AISdb, self).__init__(options, readonly)
        self.clean = sql.Table(self, 'ais_clean', self.clean_db_spec['cols'],
                               self.clean_db_spec['indices'])
        self.dirty = sql.Table(self, 'ais_dirty', self.dirty_db_spec['cols'],
                               self.dirty_db_spec['indices'])
        self.sources = sql.Table(self, 'ais_sources', self.sources_db_spec['cols'])
        self.imolist = sql.Table(self, 'imo_list', self.imolist_db_spec['cols'],
                                 constraint=self.imolist_db_spec['constraint'])
        if self.postgis == 'yes':
            self.extended = AISExtendedTable(self)

        self.clean_imolist = sql.Table(self, 'imo_list_clean', self.clean_imo_list['cols'],
                                       constraint=self.clean_imo_list['constraint'])
        self.action_log = sql.Table(self, 'action_log', self.action_log_spec['cols'], self.action_log_spec['indices'],
                                    constraint=self.action_log_spec['constraint'])
        if self.postgis == 'yes':
            self.tables = [self.clean, self.dirty, self.sources, self.imolist, self.extended, self.clean_imolist,
                           self.action_log]
        else:
            self.tables = [self.clean, self.dirty, self.sources, self.imolist, self.clean_imolist, self.action_log]

    def status(self):
        print("Status of PGSql Database " + self.db + ":")
        for tb in self.tables:
            s = tb.status()
            if s >= 0:
                print("Table {}: {} Rows.".format(tb.get_name(), s))
            else:
                print("Table {}: Not Yet Created.".format(tb.get_name()))

    def create(self):
        """Create the tables for the AIS data."""
        for tb in self.tables:
            tb.create()

    def truncate(self):
        """Delete all data in the AIS table."""
        for tb in self.tables:
            tb.truncate()

    def update(self):
        """Updates (non-destructively) existing tables to new schema
        """
        for db in [self.clean, self.dirty]:
            table_name = db.get_name()
            sql = """ALTER TABLE {} ALTER COLUMN id SET DATA TYPE BIGINT;""".format(table_name)
            with self.conn.cursor() as cur:
                logging.debug("Updating the Database Schema for Table {}".format(table_name))
                logging.debug(cur.mogrify(sql))
                try:
                    cur.execute(sql)
                    self.conn.commit()
                except psycopg2.ProgrammingError as error:
                    logging.error("Error Updating Database Schema for Table {}".format(table_name))
                    logging.error(error.pgerror)

    def ship_info(self, imo_number):
        with self.conn.cursor() as cur:
            cur.execute(
                "select vessel_name, MIN(complete_sys_date), MAX(complete_sys_date) from ais_clean where message_type = 5 and imo_number = %s GROUP BY vessel_name",
                [imo_number])
            for row in cur:
                print("Vessel: {} ({} - {})".format(*row))

            cur.execute("select mmsi, first_seen, last_seen from imo_list where imo_number = %s", [imo_number])
            for row in cur:
                print("MMSI = {} ({} - {})".format(*row))

    def get_messages_for_vessel(self, imo_number, from_ts=None, to_ts=None, use_clean_db=False, as_df=False):
        if use_clean_db:
            imo_list = self.imolist
        else:
            imo_list = self.clean_imolist

        where = ["imo_number = {}"]
        params = [imo_number]
        # Amended EOK - no complete_sys_date field in this table
        # if not from_ts is None:
        #     where.append("complete_sys_date >= {}")
        #     params.append(from_ts)
        # if not to_ts is None:
        #     where.append("complete_sys_date <= {}")
        #     params.append(to_ts)

        with self.conn.cursor() as cur:
            cur.execute(
                "select mmsi, first_seen, last_seen from {} where {}".format(imo_list.name, ' AND '.join(where)).format(
                    *params))
            msg_stream = None
            # get data for each of this ship's mmsi numbers, and concat
            for mmsi, first, last in cur:
                stream = self.get_message_stream(mmsi, from_ts=first, to_ts=last, use_clean_db=use_clean_db,
                                                 as_df=as_df)
                if msg_stream is None:
                    msg_stream = stream
                else:
                    msg_stream = msg_stream + stream
            return msg_stream

    def get_message_stream(self, mmsi, from_ts=None, to_ts=None, use_clean_db=False, as_df=False):
        """Gets the stream of messages for the given mmsi, ordered by timestamp ascending"""
        # construct db query
        if use_clean_db:
            db = self.clean
        else:
            db = self.extended
        where = ["mmsi = %s"]
        params = [mmsi]
        if not from_ts is None:
            where.append("complete_sys_date >= %s")
            params.append(from_ts)
        if not to_ts is None:
            where.append("complete_sys_date <= %s")
            params.append(to_ts)

        cols_list = ','.join([c[0].lower() for c in db.cols])
        where_clause = ' AND '.join(where)
        sql = "SELECT {} FROM {} WHERE {} ORDER BY complete_sys_date ASC".format(cols_list,
                                                                    db.get_name(), where_clause)

        if as_df:
            if pd is None:
                raise RuntimeError("Pandas not Found, Cannot Create Dataframe")
            # create pandas dataframe
            with self.conn.cursor() as cur:
                full_sql = cur.mogrify(sql, params).decode('ascii')
            return pd.read_sql(full_sql, self.conn, index_col='complete_sys_date', parse_dates=['complete_sys_date'])

        else:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                msg_stream = []
                # convert tuples from db cursor into dicts
                for row in cur:
                    message = {}
                    for i, col in enumerate(db.cols):
                        message[col[0]] = row[i]
                    msg_stream.append(message)

                return msg_stream


class AISExtendedTable(sql.Table):

    def __init__(self, db):
        super(AISExtendedTable, self).__init__(db, 'ais_extended',
                                               AISdb.clean_db_spec['cols'] + [('location', 'geography(POINT, 4326)')],
                                               AISdb.clean_db_spec['indices'])

    def create(self):
        with self.db.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        super(AISExtendedTable, self).create()
        with self.db.conn.cursor() as cur:
            # trigger for GIS location generation
            try:
                cur.execute("""CREATE OR REPLACE FUNCTION location_insert() RETURNS trigger AS '
                        BEGIN
                            NEW."location" := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude),4326);
                            RETURN NEW;
                        END;
                        ' LANGUAGE plpgsql;
                        CREATE TRIGGER {0}_gis_insert
                        BEFORE INSERT OR UPDATE ON {0} FOR EACH ROW EXECUTE PROCEDURE location_insert();
                        """.format(self.name))
            except psycopg2.ProgrammingError:
                logging.info("{}_gis_insert Already Exists".format(self.name))
                self.db.conn.rollback()
        self.db.conn.commit()

    def create_indices(self):
        with self.db.conn.cursor() as cur:
            idxn = self.name.lower() + "_location_idx"
            try:
                logging.info("CREATING GIST INDEX " + idxn + " on table " + self.name)
                cur.execute("CREATE INDEX \"" + idxn + "\" ON \"" + self.name + "\" USING GIST(\"location\")")
            except psycopg2.ProgrammingError:
                logging.info("Index " + idxn + " Already Exists")
                self.db.conn.rollback()
        super(AISExtendedTable, self).create_indices()

    def drop_indices(self):
        with self.db.conn.cursor() as cur:
            tbl = self.name
            idxn = tbl.lower() + "_location_idx"
            logging.info("Dropping Index: " + idxn + " on Table " + tbl)
            cur.execute("DROP INDEX IF EXISTS \"" + idxn + "\"")
        super(AISExtendedTable, self).drop_indices()
