## AIS_PARSER &mdash; the Python AIS Tools Environment for parsing/plotting AIS data.


AIS_PARSER is a software architecture and suite of algorithms for parsing AIS_data (http://en.wikipedia.org/wiki/Automatic_Identification_System).

### Features

* Python-based (3.8/3.9).
* Parallel cleaning and writing of large data files (.csv, .xml) into postgreSQL database.
* AIS data parsing/filtering into postgreSQL database.
* postgreSQL database inserting, updating and truncating.
* Multi-Threading manipulations.
* Building of a ship ID&ndash;transponder ID history for ship identification.
* Visualisation of shipping activity on map using (Jupyter Notebook).

### Usage/requirements

* AIS_PARSER requires an installation of Python 3, Postgresql 9.2+  and optionally Neo4j 2.1.7.
* AIS_PARSER requires an installation of Anaconda and creating an environment using (environment.yml) file.

### Installation

* Once in the (ais_parser) main directory :
    
    TERMINAL:

    Python setup.py install
    
    
### Usage

* Once in the (ais_parser) main directory :

    TERMINAL:
    
    ais_parser -h
    
    
### Further information

For further information please contact (madjid.taoualit@etu.univ-lehavre.fr)
