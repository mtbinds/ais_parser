import datetime
from typing import List

from geographiclib.geodesic import Geodesic
from geopy.distance import distance


def valid_mmsi(mmsi):

    return not mmsi is None and len(str(int(mmsi))) == 9


VALID_MESSAGE_TYPES = range(1, 28)


def valid_messagetype(message_type):
    return message_type in VALID_MESSAGE_TYPES


VALID_NAVIGATIONAL_STATUSES = set([0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 14, 15])


def valid_navigationalstatus(status):
    return status in VALID_NAVIGATIONAL_STATUSES


def valid_longitude(lon):

    return lon != None and lon >= -180 and lon <= 180


def valid_latitude(lat):

    return lat != None and lat >= -90 and lat <= 90


def valid_imo(imo=0):

    try:
        str_imo = str(int(imo))
        if len(str_imo) != 7:
            return False
        sum_val = 0
        for ii, chk in enumerate(range(7, 1, -1)):
            sum_val += chk * int(str_imo[ii])
        if str_imo[6] == str(sum_val)[len(str(sum_val)) - 1]:
            return True
    except:
        return False
    return False


def is_validsog(sog):

    return sog >= 0 and sog <= 102.2


def is_validcog(cog):

    return cog >= 0 and cog < 360


def is_validheading(heading):

    try:
        return (heading >= 0 and heading < 360) or heading == 511
    except:
        # obtention d'erreurs sur aucun type pour l'en-tête
        return False


def speed_calc(msg_stream, index1, index2):

    timediff = abs(msg_stream[index2]['Complete_Sys_Date'] - msg_stream[index1]['Complete_Sys_Date'])
    try:
        dist = distance((msg_stream[index1]['Latitude'], msg_stream[index1]['Longitude']),
                        (msg_stream[index2]['Latitude'], msg_stream[index2]['Longitude'])).m
    except ValueError:
        dist = Geodesic.WGS84.Inverse(msg_stream[index1]['Latitude'], msg_stream[index1]['Longitude'],
                                      msg_stream[index2]['Latitude'], msg_stream[index2]['Longitude'])[
            's12']  # en mètres
    if timediff > datetime.timedelta(0):
        convert_metres_to_nautical_miles = 0.0005399568
        speed = (dist * convert_metres_to_nautical_miles) / (timediff.days * 24 + timediff.seconds / 3600)
    else:
        speed = 102.2
    return timediff, dist, speed


def detect_locationoutliers(msg_stream, as_df=False):

    if as_df:
        raise NotImplementedError('msg_stream Cannot be DataFrame, as_df=True Does not Work Yet.')

    # 1) liste chaînée
    linked_rows = [None] * len(msg_stream)
    link = None
    has_location_count = 0
    for row_index in reversed(range(len(msg_stream))):
        if msg_stream[row_index]['Longitude'] is not None and msg_stream[row_index]['Latitude'] is not None:
            linked_rows[row_index] = link
            link = row_index
            has_location_count = has_location_count + 1
    # 2)
    outlier_rows = [False] * len(msg_stream)

    if has_location_count < 2:  # aucun message pouvant être aberrant disponible
        return outlier_rows

    index = next((i for i, j in enumerate(linked_rows) if j), None)
    at_start = True

    while linked_rows[index] is not None:
        # différence de temps, distance et vitesse entre les lignes d'index et le lien correspondant
        timediff, dist, speed = speed_calc(msg_stream, index, linked_rows[index])

        if timediff > datetime.timedelta(hours=215):
            index = linked_rows[index]
            at_start = True  # redémarrer
        elif dist < 100:
            index = linked_rows[index]  # sauter l'écart (at_start reste le même)
        elif speed > 50:
            if at_start is False:
                # pour l'instant, ignorer simplement les valeurs aberrantes, c'est-à-dire teste l'index actuel avec le suivant
                outlier_rows[linked_rows[index]] = True
                linked_rows[index] = linked_rows[linked_rows[index]]
            elif at_start is True and linked_rows[linked_rows[index]] is None:  # no subsequent message
                outlier_rows[index] = True
                outlier_rows[linked_rows[index]] = True
                index = linked_rows[index]
            else:  # explorez les trois premiers messages A, B, C (at_start est True)
                indexA = index
                indexB = linked_rows[index]
                indexC = linked_rows[indexB]

                timediffAC, distAC, speedAC = speed_calc(msg_stream, indexA, indexC)
                timediffBC, distBC, speedBC = speed_calc(msg_stream, indexB, indexC)

                # si le test de vitesse A-> C ok ou la distance est petite, alors B est aberrant, l'indice suivant est C
                if timediffAC <= datetime.timedelta(hours=215) and (distAC < 100 or speedAC <= 50):
                    outlier_rows[indexB] = True
                    index = indexC
                    at_start = False

                # elif speedtest B-> C ok ou distance, alors A est aberrante, l'indice suivant est C
                elif timediffBC <= datetime.timedelta(hours=215) and (distBC < 100 or speedBC <= 50):
                    outlier_rows[indexA] = True
                    index = indexC
                    at_start = False

                # sinon bot pas ok, dann A et B aberrants, définissez C sur un nouveau départ
                else:
                    outlier_rows[indexA] = True
                    outlier_rows[indexB] = True
                    index = indexC
                    at_start = True
        else:  # tout est bon
            index = linked_rows[index]
            at_start = False

    return outlier_rows


def interpolatepassages(msg_stream):

    artificial_messages = []

    return artificial_messages
