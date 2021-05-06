## AIS_PARSER &mdash; l'environnement d'outils Python pour l'analyse/le traçage des données AIS.


AIS-PARSER est une suite d'algorithmes pour l'analyse de données
`AIS <http://en.wikipedia.org/wiki/Automatic_Identification_System>`_
provenant d'émetteurs-récepteurs embarqués et collectées par satellites
et récepteurs à terre.
Les différents outils s'engagent de manière efficace et modulable,
par conséquent, ils sont substituables et extensibles de manière dynamique.
L'objectif principal est de valider et de nettoyer l'ensemble de données,
extraire des informations sur les modes d'expédition et les itinéraires d'expédition.
Pour rendre les informations facilement identifiables, les données sont stockées dans une variété de
types et formats de bases de données.

### Caractéristiques

* Basé sur Python (3.8 / 3.9).
* Nettoyage et écriture parallèles de gros fichiers de données (.csv, .xml) dans la base de données postgreSQL.
* Analyse / filtrage des données AIS dans la base de données postgreSQL.
* Insertion, mise à jour et troncature de bases de données postgreSQL.
* Manipulations multi-threads.
* Création d'un identifiant de navire et historique de l'identifiant du transpondeur pour l'identification du navire.
* Visualisation de l'activité d'expédition sur la carte à l'aide de (Jupyter Notebook).

### Exigences

* AIS_PARSER nécessite une installation de Python 3 et Postgresql 9.2+.
* AIS_PARSER nécessite une installation d'Anaconda et la création d'un environnement à l'aide du fichier (environment.yml).

### Installation

* Une fois dans le répertoire principal (ais_parser):
    
    TERMINAL:

    Python setup.py install
    
    
### Utilisation

* Ajoutez tous vos fichiers AIS (.csv ou .xml) dans le répertoire (aiscsv)
* Une fois dans le répertoire principal (ais_parser):

    TERMINAL:
    
    ais_parser -h
    
    
### Informations complémentaires

Pour plus d'informations, veuillez contacter (madjid.taoualit@etu.univ-lehavre.fr)
