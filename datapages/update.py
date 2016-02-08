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

    from .common import get_config, SpeciesConfig
    from .write_data import write_site_data_files
    from .regenerate_data import generate_data
    from .update_html import write_index

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
        args.save_cache.close()
        config['DATAPAGES_SAVE_CACHE_PATH'] = args.save_cache
    else:
        config.setdefault('DATAPAGES_SAVE_CACHE_PATH', None)

    if args.load_cache:
        args.load_cache.close()
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
    species_config_file, *others = args.domain_config # FIXME: use others

    species_config = SpeciesConfig(species_config_file)
    data = generate_data(config, species_config)

    write_site_data_files(data, site_dir, species_config.name)
    write_index(species_config.species_list, site_dir, species_config.name)

if __name__ == '__main__':
    main()
