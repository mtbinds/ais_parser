
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

    # obtenir les données de tous les fichiers csv
    for csv_file in csv_files:
        # lit les données brutes avec les colonnes et le nombre de lignes spécifiés dans config.yaml
        nrows = options["max_rows"] if options["limit_rows"] else None
        usecols = ["Complete_Sys_Date", "MMSI", "Longitude", "Latitude"]
        ais_df = pd.read_csv(csv_file, converters={"Longitude": lambda x: x.replace(',', '.'), "Latitude": lambda x: x.replace(',', '.')}, usecols=usecols, nrows=nrows,
                             delimiter=";")
        ais_df = ais_df[usecols]

        # interprète les entrées de temps brutes comme des objets datetime et supprime la colonne d'origine
        ais_df["DateTime"] = pd.to_datetime( ais_df["Complete_Sys_Date"], format="%d/%m/%Y %H:%M:%S")
        ais_df.drop(columns="Complete_Sys_Date", inplace=True)

        ais_df["Longitude"] = pd.to_numeric(ais_df["Longitude"])
        ais_df["Latitude"] = pd.to_numeric(ais_df["Latitude"])

        # conserve uniquement les lignes dans les limites si spécifié
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

        # déduit les limites de la grille si aucune limite n'est spécifiée
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

        # ajoute le dataframe actuel à la liste de tous les dataframes
        ais_data.append(ais_df)

    # fusionne les dataframes de tous les CSV
    trajectories = pd.concat(ais_data, axis=0, ignore_index=True)

    # arrondit les limites de grille déduites au degré le plus proche pour fournir un peu de remplissage à chaque limite
    if not options["bound_lon"]:
        grid_params["min_lon"] = float(math.floor(grid_params["min_lon"]))
        grid_params["max_lon"] = float(math.ceil(grid_params["max_lon"]))
    if not options["bound_lat"]:
        grid_params["min_lat"] = float(math.floor(grid_params["min_lat"]))
        grid_params["max_lat"] = float(math.ceil(grid_params["max_lat"]))

    # nombre de colonnes dans la grille résultante
    grid_params["num_cols"] = math.ceil(
        (grid_params["max_lon"] - grid_params["min_lon"])
        / grid_params["grid_len"]
    )

    return trajectories, grid_params


def write_data(trajectories, options, directories, grid_params):
    """Écrit toutes les trajectoires dans un fichier csv de sortie à l'aide d'un état discrétisé et d'une grille d'actions.

    Utilise la variable trajectoires pour regarder chaque transition id-état-action-état pour discrétiser tous les états et pour
    interpoler les actions si spécifié. Ces états discrétisés avec des actions interpolées ou arbitraires sont alors écrits
    à la sortie csv spécifiée par `` options ['out_dir'] + options ['out_file'] ``. Chaque trajectoire est également triée par
    son horodatage.

    Les trajectoires ont leurs identifiants aliasés par une variable de compteur qui ne s'incrémente que lorsqu'une trajectoire est
    va apparaître dans le csv final. Les auto-transitions sont ignorées et, en raison de la grande taille de la grille, la plupart
    les trajectoires seront ignorées puisqu'elles ne feront jamais la transition entre les carrés de la grille.

    Args:
        trajectoires (pandas.DataFrame): Toutes les entrées de données avec les colonnes `` ['MMSI', 'Longitude', 'Latitude', 'Complete_Sys_Date'] ``.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        répertoires (dict): les chemins et fichiers d'entrée et de sortie spécifiés dans le fichier `` config_file ''.
        grid_params (dict): les paramètres de grille spécifiés dans le fichier `` con
        fig_file ''."""
    # trie en fonction du MMSI, puis trie par horodatage dans les groupes MMSI, supprime la colonne d'heure

    trajectories.sort_values(["MMSI", "DateTime"], inplace=True)
    trajectories.drop(columns="DateTime", inplace=True)

    # crée une nouvelle colonne d'états discrétisés basée sur des paires de coordonnées
    trajectories["STATE"] = get_state(
        trajectories["Longitude"].values, trajectories["Latitude"].values,
        grid_params
    )

    # examine les différences d'état dans les trajectoires MMSI et ne conserve que les états avec des différences non nulles
    # les trajectoires avec un seul état sont conservées car elles auront une première ligne avec 'nan' pour diff
    non_self_transitions = (
        trajectories["STATE"].groupby(trajectories["MMSI"]).diff().ne(0)
    )
    trajectories = trajectories.loc[non_self_transitions]

    # arrondit la latitude et la longitude à la précision spécifiée
    trajectories = trajectories.round(
        {"Longitude": options["prec_coords"], "Latitude": options["prec_coords"]}
    )

    # supprime les trajectoires avec moins d'états que `` options ['min_states'] ``
    traj_lengths = trajectories["MMSI"].value_counts()
    traj_keep = traj_lengths[
        traj_lengths > options["min_states"] - 1
        ].index.values
    trajectories = trajectories.loc[trajectories["MMSI"].isin(traj_keep)]

    # alias la colonne MMSI en nombres entiers ascendants pour énumérer les trajectoires et faciliter la lecture
    alias = {
        mmsi: ind for ind, mmsi in enumerate(trajectories["MMSI"].unique())
    }
    trajectories["MMSI"] = trajectories["MMSI"].map(alias)

    # réinitialise l'index maintenant que la manipulation de ce dataframe est terminée
    trajectories.reset_index(drop=True, inplace=True)
    # crée une série de dataframes empilées, chaque dataframe représentant une transition d'état interpolée
    sas = trajectories.groupby("MMSI").apply(
        lambda x: get_action(x, options, grid_params)
    )

    if isinstance(
            sas, pd.DataFrame
    ):  # devient un DataFrame lorsque chaque trajectoire n'a qu'un seul triplet sas
        print(sas)
        sas = sas[0]

    # merge Série de dictionnaires
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

    # préparer le dictionnaire final avec des listes construites et un nom de titre approprié
    sas_data = {
        "sequence_id": ids,
        "from_state_id": prevs,
        "action_id": acts,
        "to_state_id": curs,
    }
    if options["append_coords"]:
        sas_data["longitude"] = lons
        sas_data["latitude"] = lats

    # écrit une nouvelle trame de données dans le fichier CSV final
    sas = pd.DataFrame(sas_data)
    sas.to_csv(
        directories["out_dir_path"] + directories["out_dir_file"], index=False
    )


def get_bounds(day):
    """Fonction d'aide pour obtenir les limites de longitude correspondant au jour.

    Calcule les longitudes minimum et maximum correspondant à un jour entier
    représentant un jour du système de coordonnées transversales universelles de Mercator. Chaque jour est
    6 degrés de large, divisant la Terre en 60 jours, en commençant par le jour 1 à 180 degrés W. Cette fonction
    encapsule également la journée avec un opérateur modulo, donc le jour -1 serait mappé au jour 58.

    Args:
        day (int): jour du système de coordonnées transversales universelles de Mercator.

    Retour:
        tuple: Les longitudes minimum et maximum du jour passé."""
    min_lon = (
                      6.0 * ((day - 1) % 60)
              ) - 180.0  # counts 6 degrees per day, offset by -180

    return min_lon, (min_lon + 6.0)


def get_meta_data(file_name):
    """Fonction d'assistance pour récupérer l'année, le mois et le jour d'un nom de fichier donné.

    Prend une chaîne file_name formatée comme `` 'AIS_yyyy_mm_day ##. Csv' 'et renvoie le numérique
    valeurs de `` aaaa, mm, ## '' correspondant à l'année, au mois et au numéro du jour sous forme de tuple.

    Args:
        file_name (str): Le nom du fichier à analyser au format `` 'AIS_yyyy_mm_day ##. csv' '.

    Retour:
        tuple: l'année, le mois et le jour correspondant au nom de fichier transmis.
    """
    meta_file_data = file_name.split("-")  # diviser le fichier csv sur le caractère '/', qui sépare les informations de fichier pertinentes

    year = int(meta_file_data[2][0:4])  # le deuxième élément du fichier est l'année

    month = int(meta_file_data[2][4:6])  # le deuxième élément du fichier est l'année

    day = int(meta_file_data[2][6:8])  # le deuxième élément du fichier est l'année §XS

    return year, month, day


def get_state(cur_lon, cur_lat, grid_params):
    """Discrétise une paire de coordonnées dans sa représentation d'espace d'états dans une grille euclidienne.


    Prend une paire de coordonnées `` cur_lon '', `` cur_lat '' et des paramètres de grille pour calculer l'état entier représentant
    la paire de coordonnées donnée. Cette grille de coordonnées est toujours la ligne principale. `` (min_lon, min_lat) `` représente le
    coin inférieur gauche de la grille.

    Exemple:
        Une grille 3 x 4 aurait le modèle d'énumération d'état suivant:

            8 9 10 11
            4 5 6 7
            0 1 2 3

        Avec la zone de chaque carré de la grille délimitée de la manière suivante:

            (min_lon, min_lat + grid_len) (min_lon + grid_len, min_lat + grid_len)
                      |
             (min_lon, min_lat) ---------------------- (min_lon + grid_len, min_lon)

        Dans cet exemple, le coin inférieur gauche des limites de l'état 0 serait le point `` min_lon, min_lat '' et le total
        le mappage de la zone à l'état 0 serait le carré avec `` min_lon, min_lat '' comme coin inférieur gauche et de chaque côté de
        le carré de longueur `` grid_len ''. Les parties inclusives des limites du carré mappées à zéro sont pleines
        lignes.

    Args:
        cur_lon (float): La longitude du point de données.
        cur_lat (float): La latitude du point de données.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        int: Un état correspondant à la représentation discrétisée de `` cur_lon``, `` cur_lat``.
    """
    # normaliser lat et lon aux valeurs minimales
    norm_lon = cur_lon - grid_params["min_lon"]
    norm_lat = cur_lat - grid_params["min_lat"]

    # trouver la position de la ligne et de la colonne en fonction de grid_len
    col = norm_lon // grid_params["grid_len"]
    row = norm_lat // grid_params["grid_len"]

    # trouver l'état total basé sur num_cols dans la grille finale
    return (row * grid_params["num_cols"] + col).astype(int)


def get_action(traj, options, grid_params):
    """Fonction wrapper pour les autres fonctions `` get_action ''.

    Appelle la variante correcte `` get_action '' en fonction de l'entrée d'options et renvoie la sortie résultante avec
    actions interpolées pour toutes les entrées de la série.

    Args:
        traj (pandas.DataFrame): Un pandas DataFrame avec tous les états rencontrés dans une trajectoire avec leur
            coordonnées respectives.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        dict: La séquence des triplets état-action-état pour la trajectoire passée.
    """
    # récupère les données de trajectoire
    traj_num = traj.name
    states = traj["STATE"]
    last_state = states.iloc[-1]
    lon = traj["Longitude"]
    lat = traj["Latitude"]
    # prépare un dictionnaire de transitions d'état à alimenter ligne par ligne en tant que DataFrame aux fonctions d'interpolation
    data = {
        "ID": [traj_num] * (len(states) - 1),
        "PREV": states.iloc[:-1].values,
        "CUR": states.iloc[1:].values,
    }

    # si spécifié, ajoute les coordonnées d'entrée d'origine (non discrétisées) pour chaque entrée 'PREV'
    if options["append_coords"]:
        data["Longitude"] = lon.iloc[:-1].values
        data["Latitude"] = lat.iloc[:-1].values

    # met en forme le dictionnaire de données final en tant que DataFrame
    traj_df = pd.DataFrame(data)

    # sélectionne la fonction d'interpolation spécifiée et l'applique par ligne à `` traj_df``
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

    # fusionne la série de dictionnaires
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

    # ajoute l'état final à chaque trajectoire comme sa propre ligne pour permettre un traçage plus facile des trajectoires
    if options["append_coords"]:
        states_out.append(-1)
        acts_out.append(-1)
        lon_out.append(lon.iloc[-1])
        lat_out.append(lat.iloc[-1])

    # instancie le dictionnaire final prêt pour le dataframe avec des triplets état-action-état
    data_out = {
        "ID": [traj_num] * len(acts_out),
        "PREV": states_out[:-1],
        "ACT": acts_out,
        "CUR": states_out[1:],
    }

    # ajoute des champs de coordonnées pour la sortie finale si spécifié dans les options
    if options["append_coords"]:
        data_out["Longitude"] = lon_out
        data_out["Latitude"] = lat_out

    return data_out


def get_action_arb(row, options, grid_params):
    """Calcule une action arbitraire de l'état précédent à l'état actuel par rapport à l'état précédent.

    Tout d'abord, le décalage relatif entre l'état actuel et l'état précédent dans les lignes et les colonnes est calculé.
    L'action est ensuite calculée selon une règle en spirale commençant par l'état précédent, donc auto-transitions
    sont définis comme `` 0 '' comme condition initiale. Spirale inspirée de la fonction polaire `` r = theta ''.

    Exemple:
        Par exemple, si `` prev_state = 5 '', `` cur_state = 7 '' et `` num_cols = 4 '', alors notre grille d'état est remplie
        comme suit::

            8 9 10 11
            4 p 6 c
            0 1 2 3

        Où p représente l'emplacement de l'état précédent et c représente l'emplacement de l'état actuel.
        Ensuite, la position de l'état actuel par rapport à l'état précédent est `` rel_row = 0 '', `` rel_col = 2 ''. Notre action
        spirale ressemble alors à ceci:

            15 14 13 12 11      15 14 13 12 11
            16 4  3  2  10      16 4  3  2  10
            17 5  0  1  9   ->  17 5  p  1  c
            18 6  7  8  24      18 6  7  8  24
            19 20 21 22 23      19 20 21 22 23

        Ainsi, cet algorithme renverra `` 9 '' comme action.

    Args:
        row (pandas.Series): une ligne du DataFrame auquel la fonction est appliquée, contenant le numéro de trajectoire,
            état précédent, état actuel, longitude et latitude.
        options (dict): les options de script spécifiées dans le fichier `` config_file ''.
        grid_params (dict): Les paramètres de grille spécifiés dans le `` config_file ''.

    Retour:
        dict: triplets état-action-état qui interpolent entre `` prev_state '' et `` cur_state ''.
    """
    # récupère les données de transition
    traj_num = row["ID"].astype(int)
    prev_state = row["PREV"].astype(int)
    cur_state = row["CUR"].astype(int)
    num_cols = grid_params["num_cols"]

    # obtient la décomposition des lignes et des colonnes pour les états précédents et actuels
    prev_row = prev_state // num_cols
    prev_col = prev_state % num_cols
    cur_row = cur_state // num_cols
    cur_col = cur_state % num_cols
    # calcule la position de l'état actuel par rapport à l'état précédent
    rel_row = cur_row - prev_row
    rel_col = cur_col - prev_col

    # routine simple pour calculer un ensemble d'actions en spirale
    # la séquence définie par calque correspond au nombre total de carrés de grille dans chaque calque en spirale
    action_num = x = y = i = 0
    layer = (2 * i + 1) ** 2  # sets breakpoint for when to increment i
    while not (x == rel_col and y == rel_row):
        if action_num == layer - 1:
            i += 1  # passer à la spirale suivante
            x = i
            layer = (2 * i + 1) ** 2  # calculer le point d'arrêt pour la prochaine spirale
        elif (
                x == i and y < i
        ):  # traverse du début du calque au coin supérieur droit
            y += 1
        elif x > -i and y == i:  # traverse du coin supérieur droit au coin supérieur gauche
            x -= 1
        elif (
                x == -i and y > -i
        ): # traverse du coin supérieur gauche au coin inférieur gauche
            y -= 1
        elif (
                x < i and y == -i
        ):  # traverse du coin inférieur gauche au coin inférieur droit
            x += 1
        elif (
                x == i and y < 0
        ):  # traverse du coin inférieur gauche à la fin du calque (Layer)
            y += 1
        action_num += 1

    # prépare le dictionnaire de données final pour construire DataFrame
    out_data = {
        "ID": [traj_num],
        "PREV": [prev_state],
        "ACT": [action_num],
        "CUR": [cur_state],
    }

    # écrase les coordonnées du premier état dans les transitions interpolées pour être des valeurs brutes d'origine
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
            4 p 6  c
            0 1 2  3

        Extrait de sortie ::

            pd.DataFrame ({})

        Où p représente l'emplacement de l'état précédent et c représente l'emplacement de l'état actuel.
        Ensuite, la position de l'état actuel par rapport à l'état précédent est `` rel_row = 0 '', `` rel_col = 2 ''. Notre
        la spirale d'action ressemble alors à ceci:

            4 3 2    4 3 2
            5 0 1 -> 5 p 1 c
            7 8 9    6 7 8

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
    # récupère les données de transition
    traj_num = int(row["ID"])
    prev_state = int(row["PREV"])
    cur_state = int(row["CUR"])
    num_cols = grid_params["num_cols"]

    # instancier des listes pour contenir les valeurs de colonne pour la sortie finale de DataFrame
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
    # out_rows = []
    while not (rel_row == 0 and rel_col == 0):
        # sélectionne une action pour minimiser rel_row et rel_col
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

        # déplace rel_row et rel_col dans les directions opposées de leurs signes
        row_diff = -np.sign(rel_row)
        col_diff = -np.sign(rel_col)

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
        "ID": [traj_num] * len(prevs),
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


def get_action_interp_reg(row, options, grid_params):
    """Calcule les actions prises à partir de l'état précédent pour atteindre l'état actuel, en interpolant si nécessaire.

    Tout d'abord, le décalage relatif entre l'état actuel et l'état précédent dans les lignes et les colonnes est calculé.
    Ensuite, le signe `` rel_row '' et `` rel_col '' sont ensuite utilisés pour décrire itérativement une séquence d'actions
    de l'état précédent à l'état actuel, interrompant les transitions d'état avec plusieurs actions si
    les états ne sont pas adjacents (seules les actions sont à droite, à gauche, en haut, en bas et aucune). Cette interpolation
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
        Ensuite, la position de l'état actuel par rapport à l'état précédent est `` rel_row = 0 '', `` rel_col = 2 ''. Notre action
        spirale ressemble alors à ceci:

              2        2
            3 0 1 -> 3 p 1 c
              4        4

        Extrait de sortie ::

            sortie: pd.DataFrame ({
                                    'ID': [traj_num,],
                                    'PREV': [état_précédent,],
                                    'ACTE 1, ],
                                    "CUR": [état_prév + 1,]
                                })

        Comme l'état actuel n'est pas adjacent, nous interpolons en prenant l'action qui nous rapproche le plus de
        l'état actuel: action `` 1 '', résultant en une nouvelle spirale d'action et un nouvel état précédent:

              2        1
            3 0 1 -> 2 p c
              4        4

        Sortie finale ::

            pd.DataFrame ({
                            'ID': [traj_num] * 2,
                            'PREV': [prev_state, prev_state + 1],
                            'ACT': [1, 1],
                            'CUR': [prev_state + 1, cur_state]
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
        dict: triplets state-action-state qui interpolent entre `` prev_state '' et `` cur_state ''.
    """
    # récupère les données de transition
    traj_num = row["ID"].astype(int)
    prev_state = row["PREV"].astype(int)
    cur_state = row["CUR"].astype(int)
    num_cols = grid_params["num_cols"]

    # instancier des listes pour contenir les valeurs de colonne pour la sortie finale de DataFrame
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
        tuple: La longitude et la latitude représentant le milieu de l'état transmis.
    """
    # calcule la représentation des lignes et des colonnes de l'état entier dans la grille
    state_col = state % grid_params["num_cols"]
    state_row = state // grid_params["num_cols"]

    # calcule la latitude et la longitude correspondant au milieu du carré de la grille
    state_lon = round(
        grid_params["min_lon"] + grid_params["grid_len"] * (state_col + 0.5),
        options["prec_coords"],
    )
    state_lat = round(
        grid_params["min_lat"] + grid_params["grid_len"] * (state_row + 0.5),
        options["prec_coords"],
    )

    return state_lon, state_lat
