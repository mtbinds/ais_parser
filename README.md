## AIS_PARSER &mdash; l'environnement d'outils Python pour l'analyse/le traçage des données AIS.


AIS_PARSER est une suite d'algorithmes pour l'analyse de données AIS
provenant d'émetteurs-récepteurs embarqués et collectées par satellites
et récepteurs à terre.
Les différents outils s'engagent de manière efficace et modulable,
par conséquent, ils sont substituables et extensibles de manière dynamique.
L'objectif principal est de valider et de nettoyer l'ensemble de données,
extraire des informations sur les modes d'expédition et les itinéraires d'expédition.
Pour rendre les informations facilement identifiables, les données sont stockées dans une variété de
types et formats de bases de données.

### Caractéristiques:

* Basé sur Python (3.8 / 3.9).
* Nettoyage et écriture parallèles de gros fichiers de données (.csv, .xml) dans la base de données postgreSQL.
* Analyse / filtrage des données AIS dans la base de données postgreSQL.
* Insertion, mise à jour et troncature de bases de données postgreSQL.
* Manipulations multi-threads.
* Création d'un identifiant de navire et historique de l'identifiant du transpondeur pour l'identification du navire.
* Visualisation de l'activité d'expédition sur la carte à l'aide de (Jupyter Notebook).

### Exigences:

* AIS_PARSER nécessite une installation de Python 3.8/3.9 et Postgresql 9.2+.

### Installation:

#### Installation de l'environnement Python:

* Une fois dans le répertoire principal (ais_parser):
* Vous devez être connecté à internet.

  |           Environement Python           |                          Anaconda                          |
  |:---------------------------------------:|:----------------------------------------------------------:|
  | pip install -r requirements.txt         | conda create --name nom_environment --file requirements.txt|
                                 
#### Installation de l'environnement Python:

* Une fois dans le répertoire principal (ais_parser):
* Vous devez être connecté à internet.

  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  Python setup.py install                |
                                 
--> N'oublier pas de configurer l'interpreter Python si vous êtes sous PyCharm 
    
#### Configuration des paramètres (Répertoires & Base de Données): 

* Une fois dans le répertoire intérieur (ais_parser/ais_parser):

  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  ais_parser set_default                 |
  
* Cela va générer un fichier de configuration (ais_parser.conf), Vous devez éditer la section (ais_db) en metant vos paramètres de connexion, sachant qu'il faut garder le même nom de la base de donnée (test_aisdb) au moment de création, vu que ce nom est utilisé dans le programme, si vous souhaitez en modifier le nom rendez-vous dans le répertoire (repositories).
* Il faut savoir aussi qu'il faut mettre le même nom d'utilisateur dans (user & ro_user), aussi le même mot de passe dans (pass & ro_pass).

#### Configuration des paramètres (manipulations de la base de données):

* Création de la base de données avec toutes les tables nécessaires:

  |           nom de table                  |  rôle    |                     
  |:---------------------------------------:|:--------:|
  |  ais_clean              | Les messages filtrés satisfaisants les exigences de fichiers (utils.py)|
  |  ais_dirty              | Les messages filtrés ne satisfaisants pas les exigences de fichiers (utils.py)|
  |  imolist                | La liste des tuples (IMO,MMSI) qui représentes l'immatriculation des navires|
  |  imolist_clean          | La liste des tuples (IMO,MMSI) satisfaisant les exigences de fichier (utils.py)|
  |  ais_extended          | Un sous-ensemble de navires (navires propres)|
  |  ais_sources        | Liste des noms des fichiers AIS (.csv)|
  |  action_log | Le journal des opérations du programme |

  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  ais_parser aisdb create                |

* Mise à jour de la base de données:
  
  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  ais_parser aisdb update                |

* Supression des données des tables de la base de données:
  
  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  ais_parser aisdb truncate                |




### Utilisation:

* Ajoutez tous vos fichiers AIS (.csv ou .xml) dans le répertoire (aiscsv)
* Une fois dans le répertoire principal (ais_parser):
 
  |           TERMINAL                      |                         
  |:---------------------------------------:|
  |  ais_parser -h                 

* Les commandes les plus importantes:

  |           Commande                      |                          rôle                              |
  |:---------------------------------------:|:----------------------------------------------------------:|
  | ais_parser aisparser run | simplifie les fichiers (.csv) et les met dans la base de données (Tables ais_clean et ais_dirty) et les messages erronés les exporte et les écrit sous forme de (export.csv) dans le répertoire (baddata)|
  | ais_parser imolist run | permet d'extraire les tuples (MMSI,IMO) et les insérer dans la base de données (Tables imo_list et clean_imolist)|
  | ais_parser shipsimporter run | permet d'enregistrer un sous ensemble propre de navires dans la table (ais_extended)| 
  | ais_parser processplotter run | permet de simplifier les données AIS et en faire des données pour la représentation des trajectoires sur une carte géographique en utilisant Jupyter Notebook| 
    
* Le fichier (Jupyter Notebook) à exécuter pour la représentation se trouve dans (./filter_for_visualisations/AIS_demo_data.ipynb)

### Informations complémentaires:

Pour plus d'informations, veuillez contacter (madjid.taoualit@etu.univ-lehavre.fr)
