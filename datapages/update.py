import argparse
import logging
import os
import pickle

from argparse import ArgumentTypeError, FileType

logger = logging.getLogger('datapages')

def _is_dir(path):
    if not os.path.isdir(path):
        raise ArgumentTypeError("Expected %s to be a directory" % path)
    return path

def _could_write(path):
    try:
        f = open(path, 'ab')
        f.close()
    except PermissionError:
        raise ArgumentTypeError("Permission denied: cannot open %s for writing" % path)
    except FileNotFoundError:
        raise ArgumentTypeError("Bad path to %s" % path)
    return os.path.abspath(path)

def _could_read(path):
    try:
        f = open(path, 'rb')
        f.close()
    except PermissionError:
        raise ArgumentTypeError("Permission denied: cannot open %s for reading" % path)
    except FileNotFoundError:
        raise ArgumentTypeError("Bad path to %s" % path)
    return os.path.abspath(path)

def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--global-config', type=FileType(mode='r'),
                        help="Overide config (e.g. database hosts, users)")
    parser.add_argument('-q', '--quiet', action='store_true', default=False,
                        help="Only output warnings and errors")
    site_dir_arg = parser.add_argument('-d', '--site-directory',
                        help="Directory to update", type=_is_dir)
    parser.add_argument('--save-cache', type=_could_write,
                        help="Cache database results to this file")
    parser.add_argument('--load-cache', type=_could_read,
                        help="Load cached database results from this file")
    parser.add_argument('domain_config', type=FileType(mode='r'), nargs='+',
                        help="One or more domain config files (e.g. viruses.yml)")


    return parser.parse_args()

def main():
    """Load config and update data and index.html files

    Config is loaded from the following sources in decreasing priority:
        commandline arguments
        environment variables
        a global config file

    Domain specific config is always loaded from a config file"""
    args = parse()
    if args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    from .common import get_config, DomainConfig
    from .write_data import write_domain_data_files
    from .regenerate_data import generate_data, generate_empty_data
    from .update_html import write_domain_index

    if args.global_config:
        config_file = args.global_config
    else:
        default_config_path = os.path.join(os.path.expanduser('~'),
                                          ".datapages_global_config.yml")
        config_path = os.environ.get('DATAPAGES_GLOBAL_CONFIG',
                                     default_config_path)
        config_file = open(config_path, 'r')
    logger.info("Loading global config from %s" % config_file.name)
    config = get_config(config_file)
    config_file.close()

    if args.save_cache:
        config['DATAPAGES_SAVE_CACHE_PATH'] = args.save_cache
    else:
        config.setdefault('DATAPAGES_SAVE_CACHE_PATH', None)

    if args.load_cache:
        config['DATAPAGES_LOAD_CACHE_PATH'] = args.load_cache
    else:
        config.setdefault('DATAPAGES_LOAD_CACHE_PATH', None)

    if args.site_directory:
        config['DATAPAGES_SITE_DATA_DIR'] = args.site_directory
    else:
        default_site_directory = os.path.join(os.getcwd, 'site')
        config.setdefault('DATAPAGES_SITE_DATA_DIR', default_site_directory)

    site_dir = config['DATAPAGES_SITE_DATA_DIR']
    logging.info("Preparing updates to %s" % site_dir)

    for domain_config_file in args.domain_config:
        domain_config = DomainConfig(domain_config_file)
        logger.info("Processing %s from %s" % (domain_config.domain_name,
                                               domain_config_file.name))

        if domain_config.list_data:
            data = generate_data(config, domain_config)
        else:
            data = generate_empty_data(domain_config)
        write_domain_data_files(data, site_dir, domain_config.domain_name)
        species_list = [species for species in domain_config.species_list if
                        domain_config.is_visible(species)]
        write_domain_index(species_list, site_dir, domain_config.domain_name)

if __name__ == '__main__':
    main()
