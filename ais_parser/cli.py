
import argparse
import logging
import os
from configparser import ConfigParser
from ais_parser import loader
from ais_parser import get_resource_filename
from ais_parser.config_setter import gen_default_config

def main():

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # load tool components
    config = ConfigParser()
    configfilepath = 'ais_parser.conf'
    l = None
    if os.path.exists(configfilepath):
        config.read(configfilepath)
        logger.debug(configfilepath)
        l = loader.Loader(config)
    else:
        logger.warn("Le fichier de configuration attendu 'ais_parser.conf' n'est pas présent dans ce dossier. "
                    "Veuillez vous déplacer vers le bon dossier ou exécuter set_default pour initialiser"
                    "Le répertoire actuel.")
        # return

    def list_components(args):
        print("{} Repositories:".format(len(l.get_datarepositories())))
        for repository in l.get_datarepositories():
            print("\t" + repository)

        print("{} Programs:".format(len(l.get_programs())))
        for program in l.get_programs():
            print("\t" + program)

        print("{} Visualisations:".format(len(l.get_filterforvisualisations())))
        for filter_for_visualisation in l.get_filterforvisualisations():
            print("\t" + filter_for_visualisation)


    def execute_repocommand(args):
        l.execute_repositorycommand(args.repo, args.cmd)

    def execute_program(args):
        l.execute_programcommand(args.prog, args.cmd)

    def execute_filterforvisualisation(args):
        l.execute_filterforvisualisationcommand(args.vis, args.cmd)


    # configurer l'analyseur de ligne de commande

    parser = argparse.ArgumentParser(description="************** Welcome to (AIS-PARSER TOOLS) By Madjid Taoualit (MASTER-1-IWOCS-UNIVERSITY-LE-HAVRE-NORMANDY 2021) **************")

    subparsers = parser.add_subparsers(help='Available Commands')

    parser_list = subparsers.add_parser('set_default',
                                        help='Setup Default Config File and Folder Structure')
    parser_list.set_defaults(func=gen_default_config)

    parser_list = subparsers.add_parser('list',
                                        help='List Loaded Data Repositories and Programs')
    parser_list.set_defaults(func=list_components)

    if l is not None:
        for r in l.get_datarepositories():
            repo_parser = subparsers.add_parser(r, help='Commands for ' + r + ' Repository')
            repo_subparser = repo_parser.add_subparsers(help=r + ' Repository Commands.')
            for cmd, desc in l.get_repositorycommands(r):
                cmd_parser = repo_subparser.add_parser(cmd, help=desc)
                cmd_parser.set_defaults(func=execute_repocommand, cmd=cmd, repo=r)

        for a in l.get_programs():
            prog_parser = subparsers.add_parser(a, help='Commands for Program ' + a + '')
            prog_subparser = prog_parser.add_subparsers(help=a + ' Program Commands.')
            for cmd, desc in l.get_programcommands(a):
                prog_parser = prog_subparser.add_parser(cmd, help=desc)
                prog_parser.set_defaults(func=execute_program, cmd=cmd, prog=a)

        for v in l.get_filterforvisualisations():
            vis_parser = subparsers.add_parser(v, help='Commands for Visualisation ' + v + '')
            vis_subparser = vis_parser.add_subparsers(help=v + ' Visualisation Commands.')
            for cmd, desc in l.get_filter_for_visualisation_commands(v):
                vis_parser = vis_subparser.add_parser(cmd, help=desc)
                vis_parser.set_defaults(func=execute_filterforvisualisation, cmd=cmd, vis=v)


    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
