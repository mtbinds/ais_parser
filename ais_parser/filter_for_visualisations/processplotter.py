
import math
import os
import logging
import time
import numpy as np
import pandas as pd
import yaml

EXPORT_COMMANDS = [('run', 'Process Ais Data For Ploting on Map.')]


def run():

    # fichier contenant des options importantes, des répertoires, des paramètres, etc.
    config_file = "ais_parser/filter_for_visualisations/config.yml"

    # fichier pour écrire les dernières grid_params et les années, mois et jours respectifs des fichiers csv
    meta_file = "ais_parser/filter_for_visualisations/meta_data.yml"

    # récupère le dictionnaire de configuration et le décompresse
    config = get_config(config_file)
    options = config["options"]
    directories = config["directories"]
    meta_params = config["meta_params"]
    grid_params = config["grid_params"]

    # obtient les fichiers csv disponibles et leurs métadonnées
    start = time.time()

    csv_files, all_files_meta = collect_csv_files(
        options, directories, meta_params
    )

    # lit les fichiers csv collectés et assemble les trajectoires
    trajectories, grid_params = read_data(csv_files, options, grid_params)
    logging.info("Readind AIS Files and Meta Data Done.", time.time() - start)
    logging.info("Generating CSV Files For Map Plotting...")
    start = time.time()
    # traite (s'adapte à la grille) des trajectoires et écrit génère des séquences dans le fichier de sortie
    write_data(trajectories, options, directories, grid_params)

    logging.info("Data Writing Done (%fs)", time.time() - start)

    # écrit les métadonnées de fichier, les chemins et les paramètres de grille dans `` meta_file``
    directories_out = {
        "in_dir_path": directories["out_dir_path"],
        "in_dir_data": directories["out_dir_file"],
    }
    out_dict = {
        "all_files_meta": all_files_meta,
        "options": options,
        "directories": directories_out,
        "grid_params": grid_params,
    }
    with open(meta_file, "w") as outfile:
        yaml.dump(out_dict, outfile, default_flow_style=False)


def get_config(config_file):
    """Fonction d'aide pour obtenir le dictionnaire des paramètres de script.

    Principalement du code standard à lire dans `` config_file '' en tant que fichier `` .yaml '' qui spécifie des paramètres de script importants.
    En cas de succès, ce dictionnaire de configuration est renvoyé à main pour être décompressé.

    Args:
        config_file (str): Le nom du fichier `` .yaml`` contenant les paramètres de configuration du script, situé dans le
            répertoire dans lequel le script est exécuté.

    Retour:
        dict: les paramètres de configuration du script."""
    with open(config_file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)


def collect_csv_files(options, directories, meta_params):
    """Parcourt le répertoire contenant les données AIS décompressées pour obtenir les noms csv pour un traitement ultérieur.

    Utilise la bibliothèque `` os '' pour trouver tous les fichiers csv dans le répertoire défini par `` répertoires '', en remplissant le
    Liste `` csv_files`` pour une lecture ultérieure de tous les fichiers csv valides trouvés et des métadonnées du fichier de journalisation dans `` all_files_meta``.

    Args:
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        répertoires (dict): les chemins et fichiers d'entrée et de sortie spécifiés dans le fichier `` config_file ''.
        meta_params (dict): Les limites d'heure et de jour spécifiées dans le fichier `` config_file ''.

    Retour:
        tuple: une liste avec les chemins de tous les fichiers csv valides trouvés et un dictionnaire avec l'année, le mois et le jour
        correspondant à l'origine de chaque fichier csv."""

    # initialiser une liste qui sera remplie avec tous les noms de fichiers csv à partir de la racine
    csv_files = []
    all_files_meta = {}
    for root, dirs, files in os.walk(
            directories["in_dir_path"] + directories["in_dir_data"]
    ):
        for file in files:
            if file.endswith(".csv"):
                year, month, day = get_meta_data(
                    file
                ) # recherche l'année, le mois et le jour des données en fonction du nom du fichier

                # considère uniquement les années et les mois valides si le temps est limité et les jours valides si les jours sont limités
                if (
                        not options["bound_time"]
                        or (
                                meta_params["min_year"]
                                <= year
                                <= meta_params["max_year"]
                        )
                ) and (
                        not options["bound_time"]
                        or (
                                meta_params["min_day"]
                                <= day
                                <= meta_params["max_day"]
                        )
                ):
                    if (
                            not options["bound_time"]
                            or (
                                    not year == meta_params["min_year"]
                                    or month >= meta_params["min_month"]
                                    or day >= meta_params["min_day"]
                            )
                    ) and (
                            not options["bound_time"]
                            or (
                                    not year == meta_params["max_year"]
                                    or month <= meta_params["max_month"]
                                    or day <= meta_params["max_day"]
                            )
                    ):
                        # csv_files contiendra les emplacements des fichiers par rapport au répertoire courant
                        csv_files.append(os.path.join(root, file))

                        # créer un dictionnaire pour décrire les caractéristiques du fichier
                        file_meta = {
                            "year": year,
                            "month": month,
                            "day": day,
                        }
                        all_files_meta[file] = file_meta

    return csv_files, all_files_meta


def read_data(csv_files, options, grid_params):
    """Parcourez chaque fichier csv pour séparer chaque trajectoire par son identifiant mmsi.

    Lit chaque csv dans `` csv_files '' pour obtenir les coordonnées et les séries d'horodatage associées à chaque identifiant mmsi rencontré.

    En option, les limites de la grille spécifiées ultérieurement peuvent être déduites en calculant le minimum et le maximum
    longitudes et latitudes en définissant `` options ['bound_lon'] `` et `` options ['bound_lat'] '' sur `` False``, respectivement
    dans le `` fichier_config ''.

    Il peut également être spécifié de ne lire que les premières `` options ['max_rows'] '' de chaque fichier csv en définissant
    `` options ['limit_rows'] `` à True dans le `` config_file``.

    Args:
        csv_files (liste): chemins vers tous les fichiers csv valides trouvés.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        tuple: Un DataFrame pandas de toutes les entrées de données au format `` ['MMSI', 'LON', 'LAT', 'TIME'] `` et un
        dictionnaire qui spécifie les latitudes et longitudes minimales et maximales dans l'ensemble de données.
    """

    # écraser les limites strictes sur la longitude et la latitude si elles ne sont pas limitées dans config.yaml
    if not options["bound_lon"]:
        grid_params["min_lon"] = 180
        grid_params["max_lon"] = -180
    if not options["bound_lat"]:
        grid_params["min_lat"] = 90
        grid_params["max_lat"] = -90

    # contient toutes les données AIS, une trame de données par fichier csv
    ais_data = []

    # get data from all csv files
    for csv_file in csv_files:
        # reads in the raw data with columns and number of rows specified in config.yaml
        nrows = options["max_rows"] if options["limit_rows"] else None
        usecols = ["Complete_Sys_Date", "MMSI", "Longitude", "Latitude"]
        ais_df = pd.read_csv(csv_file, converters={"Longitude": lambda x: x.replace(',', '.'), "Latitude": lambda x: x.replace(',', '.')}, usecols=usecols, nrows=nrows,
                             delimiter=";")
        ais_df = ais_df[usecols]

        # interprets raw time entries as datetime objects and drops original column
        ais_df["DateTime"] = pd.to_datetime( ais_df["Complete_Sys_Date"], format="%d/%m/%Y %H:%M:%S")
        ais_df.drop(columns="Complete_Sys_Date", inplace=True)

        ais_df["Longitude"] = pd.to_numeric(ais_df["Longitude"])
        ais_df["Latitude"] = pd.to_numeric(ais_df["Latitude"])

        # keeps only rows in boundaries if specified
        if options["bound_lon"]:
            ais_df = ais_df.loc[
                (ais_df["Longitude"] >= grid_params["min_lon"])
                & (ais_df["Longitude"] <= grid_params["max_lon"])
                ]

        if options["bound_lat"]:
            ais_df = ais_df.loc[
                (ais_df["Latitude"] >= grid_params["min_lat"])
                & (ais_df["Latitude"] <= grid_params["max_lat"])
                ]

        # infers grid boundaries if no boundaries are specified
        if (
                not options["bound_lon"]
                and ais_df["Longitude"].min() < grid_params["min_lon"]
        ):
            grid_params["min_lon"] = ais_df["Longitude"].min()
        if (
                not options["bound_lon"]
                and ais_df["Longitude"].max() > grid_params["max_lon"]
        ):
            grid_params["max_lon"] = ais_df["Longitude"].max()
        if (
                not options["bound_lat"]
                and ais_df["Latitude"].min() < grid_params["min_lat"]
        ):
            grid_params["min_lat"] = ais_df["Latitude"].min()
        if (
                not options["bound_lat"]
                and ais_df["Latitude"].max() > grid_params["max_lat"]
        ):
            grid_params["max_lat"] = ais_df["Latitude"].max()

        # appends current dataframe to list of all dataframes
        ais_data.append(ais_df)

    # merges dataframes from all csvs
    trajectories = pd.concat(ais_data, axis=0, ignore_index=True)

    # rounds inferred grid boundaries to nearest degree to provide some padding to each boundary
    if not options["bound_lon"]:
        grid_params["min_lon"] = float(math.floor(grid_params["min_lon"]))
        grid_params["max_lon"] = float(math.ceil(grid_params["max_lon"]))
    if not options["bound_lat"]:
        grid_params["min_lat"] = float(math.floor(grid_params["min_lat"]))
        grid_params["max_lat"] = float(math.ceil(grid_params["max_lat"]))

    # number of columns in the resulting grid
    grid_params["num_cols"] = math.ceil(
        (grid_params["max_lon"] - grid_params["min_lon"])
        / grid_params["grid_len"]
    )

    return trajectories, grid_params


def write_data(trajectories, options, directories, grid_params):
    """Writes all trajectories to an output csv file using a discretized state and action grid.

    Uses the trajectories variable to look at each id-state-action-state transition to discretize all states and to
    interpolate actions if specified. These discretized states with interpolated or arbitrary actions are then written
    to the output csv specified by ``options['out_dir'] + options['out_file']``. Each trajectory is also sorted by
    its timestamp.

    The trajectories have their ids aliased by a counter variable that only increments whenever a trajectory is
    going to appear in the final csv. Self-transitions are discarded, and because of the huge grid size, most
    trajectories will be discarded since they will never transition between grid squares.

    Args:
        trajectories (pandas.DataFrame): All data entries with columns ``['MMSI', 'Longitude', 'Latitude', 'Complete_Sys_Date']``.
        options (dict): The script options specified in the ``config_file``.
        directories (dict): The input and output paths and files specified in the  ``config_file``.
        grid_params (dict): The grid parameters specified in the ``con
        fig_file``.
    """
    # sorts based on MMSI, then sorts by timestamps within MMSI groups, drops the time column

    trajectories.sort_values(["MMSI", "DateTime"], inplace=True)
    trajectories.drop(columns="DateTime", inplace=True)

    # creates a new column of discretized states based on coordinate pairs
    trajectories["STATE"] = get_state(
        trajectories["Longitude"].values, trajectories["Latitude"].values,
        grid_params
    )

    # looks at state differences within MMSI trajectories and only keeps the states with nonzero differences
    # trajectories with only one state are kept because they will have a first row with 'nan' for diff
    non_self_transitions = (
        trajectories["STATE"].groupby(trajectories["MMSI"]).diff().ne(0)
    )
    trajectories = trajectories.loc[non_self_transitions]

    # rounds latitude and longitude to specified precision
    trajectories = trajectories.round(
        {"Longitude": options["prec_coords"], "Latitude": options["prec_coords"]}
    )

    # drops the trajectories with fewer states than ``options['min_states']``
    traj_lengths = trajectories["MMSI"].value_counts()
    traj_keep = traj_lengths[
        traj_lengths > options["min_states"] - 1
        ].index.values
    trajectories = trajectories.loc[trajectories["MMSI"].isin(traj_keep)]

    # aliases the MMSI column to ascending integers to enumerate trajectories and make easier to read
    alias = {
        mmsi: ind for ind, mmsi in enumerate(trajectories["MMSI"].unique())
    }
    trajectories["MMSI"] = trajectories["MMSI"].map(alias)

    # resets index now that manipulation of this dataframe has finished
    trajectories.reset_index(drop=True, inplace=True)
    # creates a series of stacked dataframes, each dataframe representing an interpolated state transition
    sas = trajectories.groupby("MMSI").apply(
        lambda x: get_action(x, options, grid_params)
    )

    if isinstance(
            sas, pd.DataFrame
    ):  # becomes a DataFrame when every trajectory has only one sas triplet
        print(sas)
        sas = sas[0]

    # merge Series of dictionaries
    ids = []
    prevs = []
    acts = []
    curs = []
    lons = []
    lats = []

    for traj in sas:
        ids += traj["ID"]
        prevs += traj["PREV"]
        acts += traj["ACT"]
        curs += traj["CUR"]
        if options["append_coords"]:
            lons += traj["Longitude"]
            lats += traj["Latitude"]

    # prepare final dictionary with built lists and proper heading name
    sas_data = {
        "sequence_id": ids,
        "from_state_id": prevs,
        "action_id": acts,
        "to_state_id": curs,
    }
    if options["append_coords"]:
        sas_data["longitude"] = lons
        sas_data["latitude"] = lats

    # writes new dataframe to final csv
    sas = pd.DataFrame(sas_data)
    sas.to_csv(
        directories["out_dir_path"] + directories["out_dir_file"], index=False
    )


def get_bounds(day):
    """Helper function to get longitude boundaries corresponding to day.

    Calculates the minimum and maximum longitudes corresponding to an integer day
    representing a Universal Transverse Mercator coordinate system day. Each day is
    6 degrees wide, dividing the Earth into 60 days, starting with day 1 at 180 deg W. This function
    also wraps the day with a modulo operator, so day -1 would map to day 58.

    Args:
        day (int): The Universal Transverse Mercator coordinate system day.

    Returns:
        tuple: The minimum and maximum longitudes of the day passed in.
    """
    min_lon = (
                      6.0 * ((day - 1) % 60)
              ) - 180.0  # counts 6 degrees per day, offset by -180

    return min_lon, (min_lon + 6.0)


def get_meta_data(file_name):
    """Helper function to retrieve a given file name's year, month, and day.

    Takes a string file_name formatted as ``'AIS_yyyy_mm_day##.csv'`` and returns the numerical
    values of ``yyyy, mm, ##`` corresponding to year, month, and day number as a tuple.

    Args:
        file_name (str): The file name to be parsed in format ``'AIS_yyyy_mm_day##.csv'``.

    Returns:
        tuple: The year, month, and day corresponding to the filename passed in.
    """
    meta_file_data = file_name.split("-")  # splits csv file on '/' character, which separates relevant file info

    year = int(meta_file_data[2][0:4])  # second element of file is the year

    month = int(meta_file_data[2][4:6])  # second element of file is the year

    day = int(meta_file_data[2][6:8])  # second element of file is the year §XS

    return year, month, day


def get_state(cur_lon, cur_lat, grid_params):
    """Discretizes a coordinate pair into its state space representation in a Euclidean grid.


    Takes in a coordinate pair ``cur_lon``, ``cur_lat`` and grid parameters to calculate the integer state representing
    the given coordinate pair. This coordinate grid is always row-major. ``(min_lon, min_lat)`` represent the
    bottom-left corner of the grid.

    Example:
        A 3 x 4 grid would have the following state enumeration pattern::

            8 9 10 11
            4 5 6 7
            0 1 2 3

        With each grid square's area bounded in the following way::

            (min_lon, min_lat + grid_len)              (min_lon + grid_len, min_lat + grid_len)
                      |
             (min_lon, min_lat) ---------------------- (min_lon + grid_len, min_lon)

        In this example, the bottom left of state 0's boundaries would be the point ``min_lon, min_lat``, and the total
        area mapping to state 0 would be the square with ``min_lon, min_lat`` as the bottom left corner and each side of
        the square with length ``grid_len``. The inclusive parts of the square's boundaries mapping to zero are solid
        lines.

    Args:
        cur_lon (float): The longitude of the data point.
        cur_lat (float): The latitude of the data point.
        grid_params (dict): The grid parameters specified in the ``config_file``.

    Returns:
        int: A state corresponding to the discretized representation of ``cur_lon``, ``cur_lat``.
    """
    # normalize lat and lon to the minimum values
    norm_lon = cur_lon - grid_params["min_lon"]
    norm_lat = cur_lat - grid_params["min_lat"]

    # find the row and column position based on grid_len
    col = norm_lon // grid_params["grid_len"]
    row = norm_lat // grid_params["grid_len"]

    # find total state based on num_cols in final grid
    return (row * grid_params["num_cols"] + col).astype(int)


def get_action(traj, options, grid_params):
    """Wrapper function for other ``get_action`` functions.

    Calls the correct ``get_action`` variant based on the options input and returns the resulting output with
    interpolated actions for all entries in the series.

    Args:
        traj (pandas.DataFrame): A pandas DataFrame with all the states encountered in a trajectory with their
            respective coordinates.
        options (dict): The script options specified in the ``config_file``.
        grid_params (dict): The grid parameters specified in the ``config_file``.

    Returns:
        dict: The sequence of state-action-state triplets for the passed in trajectory.
    """
    # retrieves trajectory data
    traj_num = traj.name
    states = traj["STATE"]
    last_state = states.iloc[-1]
    lon = traj["Longitude"]
    lat = traj["Latitude"]
    # prepares a dictionary of state transitions to be fed row-by-row as a DataFrame to the interpolation functions
    data = {
        "ID": [traj_num] * (len(states) - 1),
        "PREV": states.iloc[:-1].values,
        "CUR": states.iloc[1:].values,
    }

    # if specified, appends the original entry coordinates (not discretized) for each 'PREV' entry
    if options["append_coords"]:
        data["Longitude"] = lon.iloc[:-1].values
        data["Latitude"] = lat.iloc[:-1].values

    # formats the final data dictionary as a DataFrame
    traj_df = pd.DataFrame(data)

    # selects specified interpolation function and applies it row-wise to ``traj_df``
    if not options["interp_actions"]:
        traj_df = traj_df.apply(
            lambda x: get_action_arb(x, options, grid_params), axis=1
        )
    else:
        if options["allow_diag"]:
            traj_df = traj_df.apply(
                lambda x: get_action_interp_with_diag(x, options, grid_params),
                axis=1,
            )
        else:
            traj_df = traj_df.apply(
                lambda x: get_action_interp_reg(x, options, grid_params),
                axis=1,
            )

    # merges the dictionary series
    states_out = []
    acts_out = []
    lon_out = []
    lat_out = []
    for traj in traj_df:
        states_out += traj["PREV"]
        acts_out += traj["ACT"]
        if options["append_coords"]:
            lon_out += traj["Longitude"]
            lat_out += traj["Latitude"]
    states_out.append(last_state)

    # appends the final state to each trajectory as its own row to allow for easier plotting of trajectories
    if options["append_coords"]:
        states_out.append(-1)
        acts_out.append(-1)
        lon_out.append(lon.iloc[-1])
        lat_out.append(lat.iloc[-1])

    # instantiates final dataframe-ready dictionary with state-action-state triplets
    data_out = {
        "ID": [traj_num] * len(acts_out),
        "PREV": states_out[:-1],
        "ACT": acts_out,
        "CUR": states_out[1:],
    }

    # adds coordinate fields for final output if specified in options
    if options["append_coords"]:
        data_out["Longitude"] = lon_out
        data_out["Latitude"] = lat_out

    return data_out


def get_action_arb(row, options, grid_params):
    """Calculates an arbitrary action from the previous state to current state relative to the previous state.

    First, the relative offset between the current and previous state in rows and columns is calculated.
    The action is then calculated according to a spiral rule beginning with the previous state, so self-transitions
    are defined as ``0`` as an initial condition. Spiral inspired by the polar function ``r = theta``.

    Example:
        For example, if ``prev_state = 5``, ``cur_state = 7``, and ``num_cols = 4``, then our state grid is populated
        as follows::

            8  9 10 11
            4  p  6  c
            0  1  2  3

        Where p represents the location of the previous state, and c represents the location of the current state.
        Then the current state's position relative to the previous state is ``rel_row = 0``, ``rel_col = 2``. Our action
        spiral then looks like this::

            15 14 13 12 11      15 14 13 12 11
            16  4  3  2 10      16  4  3  2 10
            17  5  0  1  9  ->  17  5  p  1  c
            18  6  7  8 24      18  6  7  8 24
            19 20 21 22 23      19 20 21 22 23

        Thus, this algorithm will return ``9`` as the action.

    Args:
        row (pandas.Series): One row of the DataFrame the function is applied to, containing the trajectory number,
            previous state, current state, longitude, and latitude.
        options (dict): The script options specified in the ``config_file``.
        grid_params (dict): The grid parameters specified in the ``config_file``.

    Returns:
        dict: State-action-state triplets that interpolate between ``prev_state`` and ``cur_state``.
    """
    # retrieves transition data
    traj_num = row["ID"].astype(int)
    prev_state = row["PREV"].astype(int)
    cur_state = row["CUR"].astype(int)
    num_cols = grid_params["num_cols"]

    # gets row, column decomposition for previous and current states
    prev_row = prev_state // num_cols
    prev_col = prev_state % num_cols
    cur_row = cur_state // num_cols
    cur_col = cur_state % num_cols
    # calculates current state's position relative to previous state
    rel_row = cur_row - prev_row
    rel_col = cur_col - prev_col

    # simple routine to calculate a spiral set of actions
    # the sequence defined by layer corresponds to the total number of grid squares in each spiral layer
    action_num = x = y = i = 0
    layer = (2 * i + 1) ** 2  # sets breakpoint for when to increment i
    while not (x == rel_col and y == rel_row):
        if action_num == layer - 1:
            i += 1  # move to next spiral
            x = i
            layer = (2 * i + 1) ** 2  # calculate breakpoint for next spiral
        elif (
                x == i and y < i
        ):  # traverses from beginning of layer to top right corner
            y += 1
        elif x > -i and y == i:  # traverses from top right to top left corner
            x -= 1
        elif (
                x == -i and y > -i
        ):  # traverses from top left to bottom left corner
            y -= 1
        elif (
                x < i and y == -i
        ):  # traverses from bottom left to bottom right corner
            x += 1
        elif (
                x == i and y < 0
        ):  # traverses from bottom left corner to end of layer
            y += 1
        action_num += 1

    # prepares final data dictionary to build DataFrame
    out_data = {
        "ID": [traj_num],
        "PREV": [prev_state],
        "ACT": [action_num],
        "CUR": [cur_state],
    }

    # overwrites the coordinates of the first state in interpolated transitions to be original raw values
    if options["append_coords"]:
        out_data["Longitude"] = [row["Longitude"]]
        out_data["Latitude"] = [row["Latitude"]]

    return out_data


def get_action_interp_with_diag(row, options, grid_params):
    """Calcule les actions prises à partir de l'état précédent pour atteindre l'état actuel, en interpolant si nécessaire.

    Tout d'abord, le décalage relatif entre l'état actuel et l'état précédent dans les lignes et les colonnes est calculé.
    Ensuite, le signe `` rel_row '' et `` rel_col '' sont ensuite utilisés pour décrire itérativement une séquence d'actions
    de l'état précédent à l'état actuel, interrompant les transitions d'état avec plusieurs actions si
    les états ne sont pas adjacents (y compris les diagonales, ce qui donne 9 actions possibles). Cette interpolation
    suppose un système déterministe.

    Exemple:
        Par exemple, si `` prev_state = 5 '', `` cur_state = 7 '' et `` num_cols = 4 '', alors notre grille d'état est remplie
        comme suit::

            8 9 10 11
            4 p 6 c
            0 1 2 3

        Extrait de sortie ::

            pd.DataFrame ({})

        Où p représente l'emplacement de l'état précédent et c représente l'emplacement de l'état actuel.
        Ensuite, la position de l'état actuel par rapport à l'état précédent est `` rel_row = 0 '', `` rel_col = 2 ''. Notre
        la spirale d'action ressemble alors à ceci:

            4 3 2 4 3 2
            5 0 1 -> 5 p 1 c
            7 8 9 6 7 8

        Extrait de sortie ::

            pd.DataFrame ({
                            'ID': [traj_num,],
                            'PREV': [état_précédent,],
                            'ACTE 1, ],
                            "CUR": [état_prév + 1,]
                        })

        Comme l'état actuel n'est pas adjacent (y compris les diagonales), nous interpolons en prenant l'action qui
        nous rapproche de l'état actuel: l'action `` 1 '', résultant en une nouvelle spirale d'action et un nouveau précédent
        Etat::

            4 3 2    4 3 2
            5 0 1 -> 5 p c
            7 8 9    6 7 8

        Sortie finale ::

            pd.DataFrame ({
                            'ID': [traj_num] * 2,
                            'PREV': [état_prév, état_prév + 1],
                            'ACT': [1, 1],
                            'CUR': [état_prév + 1, état_cur]
                        })

        Maintenant, notre nouvel état précédent est adjacent à l'état actuel, nous pouvons donc prendre l'action `` 1 '', qui met à jour notre
        état précédent pour correspondre exactement à l'état actuel, de sorte que l'algorithme se termine et renvoie la liste des
        transitions état-action-état.

    Args:
        row (pandas.Series): une ligne du DataFrame auquel la fonction est appliquée, contenant le numéro de trajectoire,
            état précédent, état actuel, longitude et latitude.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        dict: triplets état-action-état qui interpolent entre `` prev_state '' et `` cur_state ''.
    "" """
    # retrieves transition data
    traj_num = int(row["ID"])
    prev_state = int(row["PREV"])
    cur_state = int(row["CUR"])
    num_cols = grid_params["num_cols"]

    # instantiate lists to hold column values for final DataFrame output
    prevs = []
    acts = []
    curs = []
    lons = []
    lats = []

    # gets row, column decomposition for previous and current states
    prev_row = prev_state // num_cols
    prev_col = prev_state % num_cols
    cur_row = cur_state // num_cols
    cur_col = cur_state % num_cols
    # calculates current state's position relative to previous state
    rel_row = cur_row - prev_row
    rel_col = cur_col - prev_col

    # write output rows until rel_row and rel_col are both zero
    # out_rows = []
    while not (rel_row == 0 and rel_col == 0):
        # selects action to minimize rel_row and rel_col
        action = -1
        if rel_row > 0 and rel_col > 0:
            action = 2
        elif rel_row > 0 and rel_col == 0:
            action = 3
        elif rel_row > 0 and rel_col < 0:
            action = 4
        elif rel_row == 0 and rel_col > 0:
            action = 1
        elif rel_row == 0 and rel_col < 0:
            action = 5
        elif rel_row < 0 and rel_col > 0:
            action = 8
        elif rel_row < 0 and rel_col == 0:
            action = 7
        elif rel_row < 0 and rel_col < 0:
            action = 6

        # moves rel_row and rel_col in the opposite directions of their signs
        row_diff = -np.sign(rel_row)
        col_diff = -np.sign(rel_col)

        # updates states and relative row, column based on action selected
        rel_row += row_diff
        rel_col += col_diff
        temp_row = prev_row - row_diff
        temp_col = prev_col - col_diff
        temp_state = temp_row * num_cols + temp_col
        prev_state = prev_row * num_cols + prev_col

        # records an interpolated state-action-state transition
        prevs.append(prev_state)
        acts.append(action)
        curs.append(temp_state)

        # gets the coordinates of the interpolated state - will be the coordinates of the middle of the state
        if options["append_coords"]:
            lon, lat = state_to_coord(prev_state, options, grid_params)
            lons.append(lon)
            lats.append(lat)

        prev_row = temp_row
        prev_col = temp_col

    # prepares final data dictionary to build DataFrame
    out_data = {
        "ID": [traj_num] * len(prevs),
        "PREV": prevs,
        "ACT": acts,
        "CUR": curs,
    }

    # overwrites the coordinates of the first state in interpolated transitions to be original raw values
    if options["append_coords"]:
        lons[0] = row["Longitude"]
        lats[0] = row["Latitude"]
        out_data["Longitude"] = lons
        out_data["Latitude"] = lats

    return out_data


def get_action_interp_reg(row, options, grid_params):
    """Calculates the actions taken from the previous state to reach the current state, interpolating if necessary.

    First, the relative offset between the current and previous state in rows and columns is calculated.
    Then the sign of ``rel_row`` and ``rel_col`` are then used to iteratively describe a sequence of actions
    from the previous state to current state, breaking up state transitions with multiple actions if
    the states are not adjacent (only actions are right, left, up, down, and none). This interpolation
    assumes a deterministic system.

    Example:
        For example, if ``prev_state = 5``, ``cur_state = 7``, and ``num_cols = 4``, then our state grid is populated
        as follows::

            8  9 10 11
            4  p  6  c
            0  1  2  3

        Output snippet::

            pd.DataFrame({})

        Where p represents the location of the previous state, and c represents the location of the current state.
        Then the current state's position relative to the previous state is ``rel_row = 0``, ``rel_col = 2``. Our action
        spiral then looks like this::

               2            2
            3  0  1  ->  3  p  1  c
               4            4

        Output snippet::

            output: pd.DataFrame({
                                    'ID': [traj_num, ],
                                    'PREV': [prev_state, ],
                                    'ACT': [1, ],
                                    'CUR': [prev_state + 1, ]
                                })

        Because the current state is not adjacent, we interpolate by taking the action that brings us closest to
        the current state: action ``1``, resulting in a new action spiral and a new previous state::

               2            1
            3  0  1  ->  2  p  c
               4            4

        Final output::

            pd.DataFrame({
                            'ID': [traj_num] * 2,
                            'PREV': [prev_state, prev_state + 1],
                            'ACT': [1, 1],
                            'CUR': [prev_state + 1, cur_state]
                        })

        Now, our new previous state is adjacent to the current state, so we can take action ``1``, which updates our
        previous state to exactly match the current state, so the algorithm terminates and returns the list of
        state-action-state transitions.

    Args:
        row (pandas.Series): One row of the DataFrame the function is applied to, containing the trajectory number,
            previous state, current state, longitude, and latitude.
        options (dict): The script options specified in the ``config_file``.
        grid_params (dict): The grid parameters specified in the ``config_file``.

    Returns:
        dict: State-action-state triplets that interpolate between ``prev_state`` and ``cur_state``.
    """
    # retrieves transition data
    traj_num = row["ID"].astype(int)
    prev_state = row["PREV"].astype(int)
    cur_state = row["CUR"].astype(int)
    num_cols = grid_params["num_cols"]

    # instantiate lists to hold column values for final DataFrame output
    prevs = []
    acts = []
    curs = []
    lons = []
    lats = []

    # obtient la décomposition des lignes et des colonnes pour les états précédents et actuels
    prev_row = prev_state // num_cols
    prev_col = prev_state % num_cols
    cur_row = cur_state // num_cols
    cur_col = cur_state % num_cols
    # calcule la position de l'état actuel par rapport à l'état précédent
    rel_row = cur_row - prev_row
    rel_col = cur_col - prev_col

    # écrire les lignes de sortie jusqu'à ce que rel_row et rel_col soient tous les deux à zéro
    while not (rel_row == 0 and rel_col == 0):
        # sélectionne l'action pour réduire le plus grand de rel_row et rel_col
        action = -1
        if rel_row > 0 and rel_col > 0:
            action = 2 if rel_row > rel_col else 1
        elif rel_row > 0 and rel_col == 0:
            action = 2
        elif rel_row > 0 and rel_col < 0:
            action = 2 if rel_row > -rel_col else 3
        elif rel_row == 0 and rel_col > 0:
            action = 1
        elif rel_row == 0 and rel_col < 0:
            action = 3
        elif rel_row < 0 and rel_col > 0:
            action = 4 if -rel_row > rel_col else 1
        elif rel_row < 0 and rel_col == 0:
            action = 4
        elif rel_row < 0 and rel_col < 0:
            action = 4 if -rel_row > -rel_col else 3

        # déplace rel_row et rel_col dans les directions opposées de leurs signes
        row_diff = -np.sign(rel_row) if (action == 2 or action == 4) else 0
        col_diff = -np.sign(rel_col) if (action == 1 or action == 3) else 0

        # met à jour les états et la ligne relative, la colonne en fonction de l'action sélectionnée
        rel_row += row_diff
        rel_col += col_diff
        temp_row = prev_row - row_diff
        temp_col = prev_col - col_diff
        temp_state = temp_row * num_cols + temp_col
        prev_state = prev_row * num_cols + prev_col

        # enregistre une transition état-action-état interpolée
        prevs.append(prev_state)
        acts.append(action)
        curs.append(temp_state)

        # obtient les coordonnées de l'état interpolé - seront les coordonnées du milieu de l'état
        if options["append_coords"]:
            lon, lat = state_to_coord(prev_state, options, grid_params)
            lons.append(lon)
            lats.append(lat)

        prev_row = temp_row
        prev_col = temp_col

    # prépare le dictionnaire de données final pour construire DataFrame
    out_data = {
        "ID": [traj_num] * len(acts),
        "PREV": prevs,
        "ACT": acts,
        "CUR": curs,
    }

    # écrase les coordonnées du premier état dans les transitions interpolées en valeurs brutes d'origine
    if options["append_coords"]:
        lons[0] = row["Longitude"]
        lats[0] = row["Latitude"]
        out_data["Longitude"] = lons
        out_data["Latitude"] = lats

    return out_data


def state_to_coord(state, options, grid_params):
    """Fonction inverse pour `` get_state ''.

    Calcule les coordonnées du milieu de l'état passé dans la grille spécifiée transmise.

    Args:
        state (int): Le carré de la grille discrétisé renvoyé par `` get_state ''.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        tuple: La longitude et la latitude représentant le milieu de l'état transmis. """
    # calculates the integer state's row and column representation in the grid
    state_col = state % grid_params["num_cols"]
    state_row = state // grid_params["num_cols"]

    # calculates the latitude and longitude corresponding to the middle of the grid square
    state_lon = round(
        grid_params["min_lon"] + grid_params["grid_len"] * (state_col + 0.5),
        options["prec_coords"],
    )
    state_lat = round(
        grid_params["min_lat"] + grid_params["grid_len"] * (state_row + 0.5),
        options["prec_coords"],
    )

    return state_lon, state_lat
