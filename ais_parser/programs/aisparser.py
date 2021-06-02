
import os
import csv
import logging
import queue
import threading
import time
import sys
from datetime import datetime
from xml.etree import ElementTree
from ais_parser import utils

EXPORT_COMMANDS = [('run', 'Parse Messages From CSV into The PGSql Database.')]
# Répertoire utilisé pour l'entrée dans le programme
INPUTS = ["aiscsv"]
# Répertoires utilisés pour la sortie du programme
OUTPUTS = ["aisdb", "baddata"]


def analyze_timestamp(s):
    return datetime.strptime(s, '%d/%m/%Y %H:%M:%S')


def int_or_null(s):
    if len(s) == 0:
        return None
    else:
        return int(s)


def float_or_null(s):
    if len(s) == 0 or s == 'None':
        return None
    else:
        return float(s.replace(',', '.'))


def imostring(s):
    if len(s) > 20:
        return None
    return s


def longstring(s):
    if len(s) > 255:
        return s[0:255]
    return s


def set_to_null_on_fail(row, col, test):

    if not row[col] is None and not test(row[col]):
        row[col] = None


def verify_imo(imo):
    return imo is None or utils.valid_imo(imo)


# constantes de nom de colonnes.
MMSI = 'MMSI'
TIME = 'Complete_Sys_Date'
MESSAGE_TYPE = 'Message_Type'
NAV_STATUS = 'Navigation_Status'
SOG = 'Speed_Over_Ground'
LONGITUDE = 'Longitude'
LATITUDE = 'Latitude'
COG = 'Course_Over_Ground'
HEADING = 'True_Heading'
IMO = 'IMO_Number'
DRAUGHT = 'Draught'
DEST = 'Destination'
VESSEL_NAME = 'Vessel_Name'
SHIP_TYPE = 'Ship_Type'
ETA_MONTH = 'ETA_Month'
ETA_DAY = 'ETA_Day'
ETA_HOUR = 'ETA_Hour'
ETA_MINUTE = 'ETA_Minute'

# spécifie les colonnes à extraire des données brutes et les fonctions pour les convertir en type approprié pour la base de données.
AIS_CSV_COLUMNS = [MMSI,
                   TIME,
                   MESSAGE_TYPE,
                   NAV_STATUS,
                   SOG,
                   LONGITUDE,
                   LATITUDE,
                   COG,
                   HEADING,
                   IMO,
                   DRAUGHT,
                   DEST,
                   VESSEL_NAME,
                   SHIP_TYPE,
                   ETA_MONTH,
                   ETA_DAY,
                   ETA_HOUR,
                   ETA_MINUTE]

# ce tableau décrit les noms de ce fichier qui correspond aux noms de colonne csv
AIS_XML_COLNAMES = [
    'mmsi',
    'date_time',
    'msg_type',
    'nav_status',
    'sog',
    'lon',
    'lat',
    'cog',
    'heading',
    'imo',
    'draught',
    'destination',
    'vessel_name',
    'ship_type',
    'eta_month',
    'eta_day',
    'eta_hour',
    'eta_minute']


def xml_to_csv(name):

    return AIS_CSV_COLUMNS[AIS_XML_COLNAMES.index(name)]


def analyze_raw_row(row):

    converted_row = {}
    converted_row[MMSI] = int_or_null(row[MMSI])
    converted_row[TIME] = analyze_timestamp(row[TIME])
    converted_row[MESSAGE_TYPE] = int_or_null(row[MESSAGE_TYPE])
    converted_row[NAV_STATUS] = int_or_null(row[NAV_STATUS])
    converted_row[SOG] = float_or_null(row[SOG])
    converted_row[LONGITUDE] = float_or_null(row[LONGITUDE])
    converted_row[LATITUDE] = float_or_null(row[LATITUDE])
    converted_row[COG] = float_or_null(row[COG])
    converted_row[HEADING] = float_or_null(row[HEADING])
    converted_row[IMO] = int_or_null(row[IMO])
    converted_row[DRAUGHT] = float_or_null(row[DRAUGHT])
    converted_row[DEST] = longstring(row[DEST])
    converted_row[VESSEL_NAME] = longstring(row[VESSEL_NAME])
    converted_row[SHIP_TYPE] = int_or_null(row[SHIP_TYPE])
    converted_row[ETA_MONTH] = int_or_null(row[ETA_MONTH])
    converted_row[ETA_DAY] = int_or_null(row[ETA_DAY])
    converted_row[ETA_HOUR] = int_or_null(row[ETA_HOUR])
    converted_row[ETA_MINUTE] = int_or_null(row[ETA_MINUTE])
    return converted_row


CONTAINS_LAT_LON = set([1, 2, 3, 4, 9, 11, 17, 18, 19, 21, 27])


def validate_row(row):
    # valider MMSI, message_type et IMO_Number
    if not utils.valid_mmsi(row[MMSI]) \
            or not utils.valid_messagetype(row[MESSAGE_TYPE]) \
            or not verify_imo(row[IMO]):
        raise ValueError("Row Invalid")
    # vérifier (lat) (long) pour les messages qui devraient le contenir
    if row[MESSAGE_TYPE] in CONTAINS_LAT_LON:
        if not (utils.valid_longitude(row[LONGITUDE]) and
                utils.valid_latitude(row[LATITUDE])):
            raise ValueError("Row Invalid (lat,lon)")
    # sinon les définir sur None
    else:

        row[LONGITUDE] = None
        row[LATITUDE] = None

    # valider les autres colonnes
    set_to_null_on_fail(row, NAV_STATUS, utils.valid_navigationalstatus)
    set_to_null_on_fail(row, SOG, utils.is_validsog)
    set_to_null_on_fail(row, COG, utils.is_validcog)
    set_to_null_on_fail(row, HEADING, utils.is_validheading)
    return row


def get_data_source(name):

    if name.find('terr') != -1:
        # terrestre
        return 1
    else:
        # satellite
        return 0


def run(inp, out, dropindices=True, source=0):

    files = inp['aiscsv']
    db = out['aisdb']
    log = out['baddata']

    # supprimer des index pour une insertion plus rapide
    if dropindices:
        db.clean.drop_indices()
        db.dirty.drop_indices()

    def sqlworker(q, table):

        while True:
            msgs = [q.get()]
            while not q.empty():

                msgs.append(q.get(timeout=0.5))

            n = len(msgs)
            if n > 0:
                try:
                    table.insert_rowsbatch(msgs)
                except Exception as e:
                    logging.warning("Error Executing Query: " + repr(e))
            # marquer cette tâche comme terminée
            for _ in range(n):
                q.task_done()

    # file d'attente pour les messages à insérer dans la base de données
    dirtyq = queue.Queue(maxsize=1000000)
    cleanq = queue.Queue(maxsize=1000000)
    # configurer les threads de pipeline de traitement
    clean_thread = threading.Thread(target=sqlworker, daemon=True,
                                    args=(cleanq, db.clean))
    dirty_thread = threading.Thread(target=sqlworker, daemon=True,
                                    args=(dirtyq, db.dirty))
    dirty_thread.start()
    clean_thread.start()

    start = time.time()

    for fp, name, ext in files.iterfiles():
        # vérifier si nous avons déjà analysé ce fichier
        with db.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM " + db.sources.name +
                        " WHERE filename = %s AND source = %s",
                        [name, source])
            if cur.fetchone()[0] > 0:
                logging.info("Already Parsed " + name + ", Skipping...")
                continue

        # analyser le fichier
        try:
            log_path = os.path.join(log.root, os.path.basename(name))
            invalid_ctr, clean_ctr, dirty_ctr, duration = analyze_file(fp, name, ext, log_path, cleanq, dirtyq,
                                                                       source=source)
            dirtyq.join()
            cleanq.join()
            db.sources.insert_row({'filename': name,
                                   'ext': ext,
                                   'invalid': invalid_ctr,
                                   'clean': clean_ctr,
                                   'dirty': dirty_ctr,
                                   'source': source})
            db.conn.commit()
            logging.info("Completed " + name +
                         ": %d Clean, %d Dirty, %d Invalid Messages, %fs",
                         clean_ctr, dirty_ctr, invalid_ctr, duration)
        except RuntimeError as error:
            logging.warn("Error Parsing File %s: %s", name, repr(error))
            db.conn.rollback()

    # attendre la fin des tâches en file d'attente
    dirtyq.join()
    cleanq.join()
    db.conn.commit()

    logging.info("Parsing Complete, Time Elapsed = %fs", time.time() - start)

    if dropindices:
        start = time.time()
        logging.info("Rebuilding Table Indices...")
        db.clean.create_indices()
        db.dirty.create_indices()
        logging.info("Finished Building Indices, Time Elapsed = %fs",
                     time.time() - start)


def analyze_file(fp, name, ext, baddata_logfile, cleanq, dirtyq, source=0):

    filestart = time.time()
    logging.info("Parsing " + name)

    # ouvrir le fichier csv du journal des erreurs et écrire l'en-tête
    with open(baddata_logfile, 'w') as errorlog:
        logwriter = csv.writer(errorlog, delimiter=';', quotechar='"')

        # compteurs de messages
        clean_ctr = 0
        dirty_ctr = 0
        invalid_ctr = 0

        # Sélectionnez un itérateur de fichier basé sur l'extension de fichier
        if ext == '.csv':
            iterator = readcsv
        elif ext == '.xml':
            iterator = readxml
        else:
            raise RuntimeError("Cannot Parse File With Extension %s" % ext)

        # déduire la source de données à partir du nom de fichier
        # source = get_data_source(name)

        # analyser et itérer les lignes du fichier courant
        for row in iterator(fp):
            converted_row = {}
            try:
                # analyser les données brutes
                converted_row = analyze_raw_row(row)
                converted_row['source'] = source
            except ValueError as e:
                # données non valides dans la ligne. Écriture dans le journal des erreurs
                if not 'raw' in row:
                    row['raw'] = [row[c] for c in AIS_CSV_COLUMNS]
                logwriter.writerow(row['raw'] + ["{}".format(e)])
                invalid_ctr = invalid_ctr + 1
                continue
            except KeyError:
                # données manquantes dans la ligne.
                if not 'raw' in row:
                    row['raw'] = [row[c] for c in AIS_CSV_COLUMNS]
                logwriter.writerow(row['raw'] + ["Bad Row Length"])
                invalid_ctr = invalid_ctr + 1
                continue

            # valider la ligne analysée et l'ajouter à la file d'attente appropriée
            try:
                validated_row = validate_row(converted_row)
                cleanq.put(validated_row)
                clean_ctr = clean_ctr + 1
            except ValueError:
                dirtyq.put(converted_row)
                dirty_ctr = dirty_ctr + 1

    if invalid_ctr == 0:
        os.remove(baddata_logfile)

    return (invalid_ctr, clean_ctr, dirty_ctr, time.time() - filestart)


def readcsv(fp):
    # correctif pour une erreur de grand champ. Spécifiez la taille maximale du champ à la valeur int convertible maximale.
    # source: http://stackoverflow.com/questions/15063936/csv-error-field-larger-than-field-limit-131072
    max_int = sys.maxsize
    decrement = True
    while decrement:
        # diminuer la valeur max_int d'un facteur 10
        # tant que l'OverflowError se produit.
        decrement = False
        try:
            csv.field_size_limit(max_int)
        except OverflowError:
            max_int = int(max_int / 10)
            decrement = True

    # Les lignes correspondent aux en-têtes de colonnes.
    # Utilisées pour extraire les index des colonnes que nous extrayons
    cols = fp.readline().rstrip('').split(';')
    indices = {}
    n_cols = len(cols)
    try:
        for col in AIS_CSV_COLUMNS:
            indices[col] = cols.index(col)
    except Exception as e:
        raise RuntimeError("Missing Columns in File Header: {}".format(e))

    try:
        for row in csv.reader(fp, delimiter=';', quotechar='"'):
            rowsubset = {}
            rowsubset['raw'] = row
            if len(row) == n_cols:
                for col in AIS_CSV_COLUMNS:
                    try:
                        rowsubset[col] = row[indices[col]]  # données de colonne brutes
                    except IndexError:
                        # pas assez de colonnes, juste vider les données manquantes.
                        rowsubset[col] = ''
            yield rowsubset
    except UnicodeDecodeError as e:
        raise RuntimeError(e)
    except csv.Error as e:
        raise RuntimeError(e)


def readxml(fp):
    current = _empty_row()
    # itérer les événements XML 'end'
    for _, elem in ElementTree.iterparse(fp):
        # fin d'aismessage
        if elem.tag == 'aismessage':
            yield current
            current = _empty_row()
        else:
            if elem.tag in AIS_XML_COLNAMES and elem.text != None:
                current[xml_to_csv(elem.tag)] = elem.text


def _empty_row():
    row = {}
    for col in AIS_CSV_COLUMNS:
        row[col] = ''
    return row
