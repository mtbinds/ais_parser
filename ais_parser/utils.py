import datetime
from typing import List

from geographiclib.geodesic import Geodesic
from geopy.distance import distance


def valid_mmsi(mmsi):
    """Checks if a given MMSI number is valid.

    Arguments
    ---------
    mmsi : int
        An MMSI number

    Returns
    -------
    Returns True if the MMSI number is 9 digits long.
    """
    return not mmsi is None and len(str(int(mmsi))) == 9


VALID_MESSAGE_TYPES = range(1, 28)


def valid_message_type(message_type):
    return message_type in VALID_MESSAGE_TYPES


VALID_NAVIGATIONAL_STATUSES = set([0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 14, 15])


def valid_navigational_status(status):
    return status in VALID_NAVIGATIONAL_STATUSES


def valid_longitude(lon):
    """Check valid longitude.

    Arguments
    ---------
    lon : integer
        A longitude

    Returns
    -------
    True if the longitude is valid
    """
    return lon != None and lon >= -180 and lon <= 180


def valid_latitude(lat):
    """Check valid latitude.

    Arguments
    ---------
    lon : integer
        A latitude

    Returns
    -------
    True if the latitude is valid
    """
    return lat != None and lat >= -90 and lat <= 90


def valid_imo(imo=0):
    """Check valid IMO using checksum.

    Arguments
    ---------
    imo : integer
        An IMO ship identifier

    Returns
    -------
    True if the IMO number is valid

    Notes
    -----
    Taken from Eoin O'Keeffe's `checksum_valid` function in pyAIS
    """
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


def is_valid_sog(sog):
    """Validates speed over ground

    Arguments
    ---------
    sog : float
        Speed over ground

    Returns
    -------
    True if speed over ground is greater than zero and less than 102.2

    """
    return sog >= 0 and sog <= 102.2


def is_valid_cog(cog):
    """Validates course over ground

    Arguments
    ---------
    cog : float
        Course over ground

    Returns
    -------
    True if course over ground is greater than zero and less than 360 degrees

    """
    return cog >= 0 and cog < 360


def is_valid_heading(heading):
    """Validates heading

    Arguments
    ---------
    heading : float
        The heading of the ship in degrees

    Returns
    -------
    True if heading is greater than zero and less than 360 degrees
    """
    try:
        return (heading >= 0 and heading < 360) or heading == 511
    except:
        # getting errors on none type for heading
        return False


def speed_calc(msg_stream, index1, index2):
    """Computes the speed between two messages in the message stream

    Parameters
    ----------
    msg_stream :
        A list of dictionaries representing AIS messages for a single MMSI
        number. Dictionary keys correspond to the column names from the
        `ais_clean` table. The list of messages should be ordered by
        timestamp in ascending order.
    index1 : int
        The index of the first message
    index2 : int
        The index of the second message

    Returns
    -------
    timediff : datetime
        The difference in time between the two messages in datetime
    dist : float
        The distance between messages in nautical miles
    speed : float
        The speed in knots
    """
    timediff = abs(msg_stream[index2]['Complete_Sys_Date'] - msg_stream[index1]['Complete_Sys_Date'])
    try:
        dist = distance((msg_stream[index1]['Latitude'], msg_stream[index1]['Longitude']),
                        (msg_stream[index2]['Latitude'], msg_stream[index2]['Longitude'])).m
    except ValueError:
        dist = Geodesic.WGS84.Inverse(msg_stream[index1]['Latitude'], msg_stream[index1]['Longitude'],
                                      msg_stream[index2]['Latitude'], msg_stream[index2]['Longitude'])[
            's12']  # in metres
    if timediff > datetime.timedelta(0):
        convert_metres_to_nautical_miles = 0.0005399568
        speed = (dist * convert_metres_to_nautical_miles) / (timediff.days * 24 + timediff.seconds / 3600)
    else:
        speed = 102.2
    return timediff, dist, speed


def detect_location_outliers(msg_stream, as_df=False):
    """Detects outlier messages by submitting messages to a speed tests

    The algorithm proceeds as follows:

    #.  Create a linked list of all messages with non-null locations
        (pointing to next message)
    #.  Loop through linked list and check for location outliers:

        * A location outlier is who does not pass the speed tests (<= 50kn;
          link is 'discarded' when not reached in time)
        * No speed tests is performed when:

            * distance too small (< 0.054nm ~ 100m; catches most positioning
              inaccuracies) => no outlier
            * time gap too big (>= 215h ~ 9d; time it takes to get anywhere on
              the globe at 50kn not respecting land) =>  next message is new 'start'

        If an alledged outlier is found its link is set to be the current
        message's link

    #.  The start of a linked list becomes special attention: if speed check
        fails, the subsequent link is tested

    Line of thinking is: Can I get to the next message in time? If not 'next'
    must be an outlier, go to next but one.

    Parameters
    ----------

    msg_stream :
        A list of dictionaries representing AIS messages for a single MMSI
        number. Dictionary keys correspond to the column names from the
        `ais_clean` table. The list of messages should be ordered by
        timestamp in ascending order.
    as_df : bool, optional
        Set to True if `msg_stream` are passed as a pandas DataFrame

    Returns
    -------
    outlier_rows :
        The rows in the message stream which are outliers

    """
    if as_df:
        raise NotImplementedError('msg_stream Cannot be DataFrame, as_df=True Does not Work Yet.')

    # 1) linked list
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

    if has_location_count < 2:  # no messages that could be outliers available
        return outlier_rows

    index = next((i for i, j in enumerate(linked_rows) if j), None)
    at_start = True

    while linked_rows[index] is not None:
        # time difference, distance and speed beetween rows of index and corresponding link
        timediff, dist, speed = speed_calc(msg_stream, index, linked_rows[index])

        if timediff > datetime.timedelta(hours=215):
            index = linked_rows[index]
            at_start = True  # restart
        elif dist < 100:
            index = linked_rows[index]  # skip over gap (at_start remains same)
        elif speed > 50:
            if at_start is False:
                # for now just skip single outliers, i.e. tests current index with next but one
                outlier_rows[linked_rows[index]] = True
                linked_rows[index] = linked_rows[linked_rows[index]]
            elif at_start is True and linked_rows[linked_rows[index]] is None:  # no subsequent message
                outlier_rows[index] = True
                outlier_rows[linked_rows[index]] = True
                index = linked_rows[index]
            else:  # explore first three messages A, B, C (at_start is True)
                indexA = index
                indexB = linked_rows[index]
                indexC = linked_rows[indexB]

                timediffAC, distAC, speedAC = speed_calc(msg_stream, indexA, indexC)
                timediffBC, distBC, speedBC = speed_calc(msg_stream, indexB, indexC)

                # if speedtest A->C ok or distance small, then B is outlier, next index is C
                if timediffAC <= datetime.timedelta(hours=215) and (distAC < 100 or speedAC <= 50):
                    outlier_rows[indexB] = True
                    index = indexC
                    at_start = False

                # elif speedtest B->C ok or distance, then A is outlier, next index is C
                elif timediffBC <= datetime.timedelta(hours=215) and (distBC < 100 or speedBC <= 50):
                    outlier_rows[indexA] = True
                    index = indexC
                    at_start = False

                # else bot not ok, dann A and B outlier, set C to new start
                else:
                    outlier_rows[indexA] = True
                    outlier_rows[indexB] = True
                    index = indexC
                    at_start = True
        else:  # all good
            index = linked_rows[index]
            at_start = False

    return outlier_rows


def interpolate_passages(msg_stream):
    """Interpolate far apart points in an ordered stream of messages.

    Parameters
    ----------
    msg_stream :
        A list of dictionaries representing AIS messages for a single MMSI
        number. Dictionary keys correspond to the column names from the
        `ais_clean` table. The list of messages should be ordered by
        timestamp in ascending order.

    Returns
    -------
    artificial_messages : list
        A list of artificial messages to fill in gaps/navigate around land.


    """
    artificial_messages = []

    return artificial_messages
