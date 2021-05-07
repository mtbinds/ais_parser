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

  |           Environement Python           |                          Anaconda                          |
  |:---------------------------------------:|:----------------------------------------------------------:|
  | pip install -r requirements.txt         | conda create --name nom_environment --file requirements.txt|
                                 
#### Installation de l'environnement Python:

* Une fois dans le répertoire principal (ais_parser):

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

![alt text](img/Screen Shot 2021-05-07 at 12.47.56.png)



### Utilisation:

* Ajoutez tous vos fichiers AIS (.csv ou .xml) dans le répertoire (aiscsv)
* Une fois dans le répertoire principal (ais_parser):

    TERMINAL:
    
    ais_parser -h
    
    
### Informations complémentaires:

Pour plus d'informations, veuillez contacter (madjid.taoualit@etu.univ-lehavre.fr)
