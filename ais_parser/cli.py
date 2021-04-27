"""Provides a command line interface to the ais_parser library

The command line interface (CLI) expects that a configuration file named
'aistool.conf' is located in the current folder.

If the config file is not present, a runtime error is raised, and the commands
`set_default` can be used to generate a default configuration file.

"""
import argparse
import logging
import os
from configparser import ConfigParser
from ais_parser import loader
from ais_parser import get_resource_filename
from ais_parser.config_setter import gen_default_config

def main():
    """ The command line inteface

    Type `ais_parser --help` for help on how to use the command line interface
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # load tool components
    config = ConfigParser()
    configfilepath = 'aistool.conf'
    l = None
    if os.path.exists(configfilepath):
        config.read(configfilepath)
        logger.debug(configfilepath)
        l = loader.Loader(config)
    else:
        logger.warn("The Expected Configuration File 'aistool.conf' is Not Present in This Folder. "
                    "Please Move to The Correct Folder, or Run set_default to Initialise "
                    "The Current Directory.")
        # return

    def list_components(args):
        print("{} Repositories:".format(len(l.get_data_repositories())))
        for repository in l.get_data_repositories():
            print("\t" + repository)

        print("{} Algorithms:".format(len(l.get_algorithms())))
        for algorithm in l.get_algorithms():
            print("\t" + algorithm)

        print("{} Visualisations:".format(len(l.get_filter_for_visualisations())))
        for filter_for_visualisation in l.get_filter_for_visualisations():
            print("\t" + filter_for_visualisation)


    def execute_repo_command(args):
        l.execute_repository_command(args.repo, args.cmd)

    def execute_algorithm(args):
        l.execute_algorithm_command(args.alg, args.cmd)

    def execute_filter_for_visualisation(args):
        l.execute_filter_for_visualisation_command(args.vis, args.cmd)


    # set up command line parser

    parser = argparse.ArgumentParser(description="************** Welcome to (AIS-PARSER TOOLS) By Madjid Taoualit (MASTER-1-IWOCS-UNIVERSITY-LE-HAVRE-NORMANDY 2021) **************")

    subparsers = parser.add_subparsers(help='Available Commands')

    parser_list = subparsers.add_parser('set_default',
                                        help='Setup Default Config File and Folder Structure')
    parser_list.set_defaults(func=gen_default_config)

    parser_list = subparsers.add_parser('list',
                                        help='List Loaded Data Repositories and Algorithms')
    parser_list.set_defaults(func=list_components)

    if l is not None:
        for r in l.get_data_repositories():
            repo_parser = subparsers.add_parser(r, help='Commands for ' + r + ' Repository')
            repo_subparser = repo_parser.add_subparsers(help=r + ' Repository Commands.')
            for cmd, desc in l.get_repository_commands(r):
                cmd_parser = repo_subparser.add_parser(cmd, help=desc)
                cmd_parser.set_defaults(func=execute_repo_command, cmd=cmd, repo=r)

        for a in l.get_algorithms():
            alg_parser = subparsers.add_parser(a, help='Commands for Algorithm ' + a + '')
            alg_subparser = alg_parser.add_subparsers(help=a + ' Algorithm Commands.')
            for cmd, desc in l.get_algorithm_commands(a):
                alg_parser = alg_subparser.add_parser(cmd, help=desc)
                alg_parser.set_defaults(func=execute_algorithm, cmd=cmd, alg=a)

        for v in l.get_filter_for_visualisations():
            vis_parser = subparsers.add_parser(v, help='Commands for Visualisation ' + v + '')
            vis_subparser = vis_parser.add_subparsers(help=v + ' Visualisation Commands.')
            for cmd, desc in l.get_filter_for_visualisation_commands(v):
                vis_parser = vis_subparser.add_parser(cmd, help=desc)
                vis_parser.set_defaults(func=execute_filter_for_visualisation, cmd=cmd, vis=v)


    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
