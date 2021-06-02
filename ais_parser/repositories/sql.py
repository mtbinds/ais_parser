"""Classes de connexion et de gestion des tables de base de données

Dépôt Pgsql
---------------
Configure une connexion à un référentiel de base de données ais_parser

Tableau
-----
Utilisé pour encapsuler une table de base de données ais_parser

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
    """Table de base de données
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
        """ Création d'une table dans la base de données
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
        """Supprimez toutes les données du tableau."""
        with self.db.conn.cursor() as cur:
            logging.info("Truncating Table " + self.name)
            cur.execute("TRUNCATE TABLE \"" + self.name + "\" CASCADE")
            self.db.conn.commit()

    def status(self):
        """ Renvoie le nombre approximatif d'enregistrements dans la table

        Retourne
        -------
        entier

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
        """ Insère une ligne dans le tableau
        """
        with self.db.conn.cursor() as cur:
            columnlist = self._get_list_of_columns(data)
            tuplestr = "(" + ",".join("%({})s".format(i)
                                      for i in data.keys()) + ")"
            # logging.debug(cur.mogrify("INSERT INTO " + self.name + " "+ columnlist + " VALUES "+ tuplestr, data))
            cur.execute("INSERT INTO " + self.name + " " +
                        columnlist + " VALUES " + tuplestr, data)

    def _get_list_of_columns(self, row):
        """ Obtient une liste des colonnes d'un dictionnaire de lignes

        Arguments
        ---------
        ligne: dict
            Un dictionnaire de paires (champ, valeur)

        Retourne
        -------
        liste de colonnes: str
            Une chaîne de noms de colonnes en minuscules, entre crochets '()'
        """

        columnlist = '(' + ','.join([c.lower() for c in row.keys()]) + ')'
        return columnlist

    def insert_rowsbatch(self, rows):
        """ Insère un certain nombre de lignes dans le tableau

        Arguments
        ---------
        lignes: liste
            Une liste de dictionnaires de paires (colonne, valeur)
        """
        # vérifiez qu'il y a des lignes dans l'insertion
        if len(rows) == 0:
            return
        # logging.debug("Ligne à insérer: {}". format (lignes [0]))
        with self.db.conn.cursor() as cur:
            columnlist = self._get_list_of_columns(rows[0])
            # logging.debug("Utilisation des colonnes: {}". format (liste des colonnes))
            tuplestr = "(" + ",".join("%({})s".format(i)
                                      for i in rows[0]) + ")"
            # créer une seule requête pour insérer une liste de tuples
            # notez que mogrify génère une chaîne binaire qu'il faut d'abord
            # décoder en ascii.
            args = ','.join([cur.mogrify(tuplestr, x).decode('utf-8')
                             for x in rows])
            cur.execute("INSERT INTO " + self.name + " " +
                        columnlist + " VALUES " + args)

    def copy_from_file(self, fname, columns):
        with self.db.conn.cursor() as cur:
            cur.execute("COPY " + self.name + " (" + ','.join(c.lower()
                                                              for c in columns) + ") FROM %s DELIMITER ',' CSV HEADER", [fname])
