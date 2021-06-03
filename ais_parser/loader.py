
import logging
import imp
import pkgutil
import inspect
import contextlib
from configparser import ConfigParser
from ais_parser import get_resource_filename


def load_module(name, paths):
    """Chargez le nom du module en utilisant les chemins de recherche donnés."""
    handle, pathname, description = imp.find_module(name, paths)
    if handle is not None:
        return imp.load_module(name, handle, pathname, description)
    else:
        return None


def load_all_modules(paths):
    """Chargez tous les modules sur les chemins indiqués."""
    modules = {}
    for _, name, _ in pkgutil.walk_packages(paths):
        try:
            modules[name] = load_module(name, paths)
        except ImportError as error:
            logging.warn("Error Importing Module " + name + ": {}".format(error))
    return modules


class Loader:
    """Le Loader réunit des référentiels de données et des programmes,
    et exécute des opérations sur eux."""

    def __init__(self, config=None):
        # charger à partir du fichier si le chemin est fourni
        loaded_conf = ConfigParser()
        if config is None:
            raise RuntimeError("No Config File Defined.")
        else:
            if isinstance(config, str):
                loaded_conf.read(config)
                config = loaded_conf

        if 'globals' in config:
            repopaths = str(config.get('globals', 'repos'))
            repopaths = repopaths.split(',')
            repopaths.extend([get_resource_filename('repositories')])
        else:
            repopaths = [get_resource_filename('repositories')]

        logging.debug("Paths to repositories: {}".format(repopaths))

        # load repo drivers from repopaths
        repo_drivers = load_all_modules(repopaths)

        # get repo configurations from config
        if 'globals' in config:
            repo_config = set(config.sections()) - set(['globals'])
        else:
            repo_config = set(config.sections())

        # check which repos we have drivers for
        repo_conf_dict = {}
        for repo_name in repo_config:
            conf = config[repo_name]
            if not 'type' in conf:
                logging.warning("Repository " + repo_name + " Does not Specify a Type in The config File.")
            elif not conf['type'] in repo_drivers:
                logging.warning("Driver of Type " + conf['type'] + " for Repository " + repo_name + " Not Found.")
            else:
                repo_conf_dict[repo_name] = conf

        if 'globals' in config:
            progpaths = str(config.get('globals', 'progs'))
            progpaths = progpaths.split(',')
            progpaths.extend([get_resource_filename('programs')])
            vispaths = str(config.get('globals', 'visos'))
            vispaths = vispaths.split(',')
            vispaths.extend([get_resource_filename('filter_for_visualisations')])
        else:
            progpaths = [get_resource_filename('programs')]
            vispaths = [get_resource_filename('filter_for_visualisations')]
            expaths = [get_resource_filename('exports')]

        # charger des programmes à partir de progpaths
        logging.debug("Paths to Programs: {}".format(progpaths))
        programs = load_all_modules(progpaths)

        # charger des visualisations à partir de vispaths
        logging.debug("Paths to Visualisations: {}".format(vispaths))
        filter_for_visualisations = load_all_modules(vispaths)

        self.repo_drivers = repo_drivers
        self.repo_config = repo_conf_dict
        self.programs = programs
        self.filter_for_visualisations = filter_for_visualisations


    def get_datarepositories(self):
        """Renvoie un ensemble de noms de répertoires de données disponibles"""
        return self.repo_config.keys()

    def get_repositorycommands(self, repo_name):
        """Renvoie une liste des commandes disponibles pour le référentiel spécifié"""
        try:
            return self.repo_drivers[self.repo_config[repo_name]['type']].EXPORT_COMMANDS
        except AttributeError:
            return []

    def get_programcommands(self, progname):
        """Renvoie une liste des commandes disponibles pour le programme spécifié"""
        try:
            return self.programs[progname].EXPORT_COMMANDS
        except AttributeError:
            return []

    def get_filterforvisualisationcommands(self, visname):
        """Renvoie une liste des commandes disponibles pour la visualisation"""
        try:
            return self.filter_for_visualisations[visname].EXPORT_COMMANDS
        except AttributeError:
            return []

    def get_programs(self):
        """Renvoie un ensemble de noms de programmes disponibles"""
        return self.programs.keys()

    def get_filterforvisualisations(self):
        """Renvoie un ensemble de noms de visulaisations disponibles"""
        return self.filter_for_visualisations.keys()

    def execute_repositorycommand(self, reponame, command, **args):
        """Exécutez la commande spécifiée sur le référentiel spécifié."""
        if not command in [c[0] for c in self.get_repositorycommands(reponame)]:
            raise ValueError("Invalid command {} for repository {}".format(command, reponame))
        # classe de répertoire de chargement
        repo = self.get_datarepository(reponame)
        fns = inspect.getmembers(repo, lambda x: inspect.ismethod(x) and x.__name__ == command)
        if len(fns) != 1:
            raise RuntimeError("Unable to find method {} in repository {}: {}".format(command, reponame, repo))
        with repo:
            # appel de commande
            fns[0][1](**args)

    def execute_programcommand(self, progname, command, **args):
        """Exécuter la commande spécifiée sur le programme spécifié"""
        prog = self.get_program(progname)
        fns = inspect.getmembers(prog, lambda x: inspect.isfunction(x) and x.__name__ == command)
        if len(fns) != 1:
            raise RuntimeError("Unable to find function {} in program {}: {}".format(command, progname, prog))

        # obtenir des entrées et des sorties
        inputs = {}
        outputs = {}

        for inp in prog.INPUTS:
            inputs[inp] = self.get_datarepository(inp, readonly=True)
        for out in prog.OUTPUTS:
            outputs[out] = self.get_datarepository(out)

        with contextlib.ExitStack() as stack:
            # préparer les référentiels
            for i in inputs:
                stack.enter_context(inputs[i])
            for i in outputs:
                stack.enter_context(outputs[i])
            fns[0][1](inputs, outputs, **args)

    def execute_filterforvisualisationcommand(self, visname, command, **args):
        """Exécuter la commande spécifiée sur la visualisation spécifiée"""
        vis = self.get_filterforvisualisation(visname)
        fns = inspect.getmembers(vis, lambda x: inspect.isfunction(x) and x.__name__ == command)
        if len(fns) != 1:
            raise RuntimeError("Unable to find function {} in visualisation {}: {}".format(command, visname, vis))
        fns[0][1](**args)


    def get_datarepository(self, name, readonly=False):
        """Renvoie une instance chargée du référentiel de données spécifié."""
        return self.repo_drivers[self.repo_config[name]['type']].load(self.repo_config[name], readonly=readonly)

    def get_program(self, name):
        """Renvoie le module de programme spécifié."""
        return self.programs[name]

    def get_filterforvisualisation(self, name):
        """Renvoie le module de visualisation spécifié."""
        return self.filter_for_visualisations[name]

