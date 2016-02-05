import logging
import os
import sys
import yaml

from boltons.strutils import slugify

def species_filename(species):
    return slugify(species).lower()+'.json'

def get_config(config_filepath):
    """Creates a dictionary like object, preferably from config,
    else from environment variables"""

    mandatory_keys = [
        'DATAPAGES_VRTRACK_HOST',
        'DATAPAGES_VRTRACK_PORT',
        'DATAPAGES_VRTRACK_RO_USER',
        'DATAPAGES_SEQUENCESCAPE_HOST',
        'DATAPAGES_SEQUENCESCAPE_PORT',
        'DATAPAGES_SEQUENCESCAPE_RO_USER',
        'DATAPAGES_SEQUENCESCAPE_DATABASE'
    ]

    optional_keys = [
        'DATAPAGES_DATA_CACHE_PATH',
        'DATAPAGES_LOAD_DATA_CACHE',
        'DATAPAGES_SAVE_DATA_CACHE'
    ]

    try:
        with open(config_filepath, 'r') as config_file:
            config_from_file = yaml.load(config_file)
    except IOError:
        if config_filepath:
            logging.warn("Could not load config from %s, using environment variables" % config_filepath)
        config_from_file = {}
    except yaml.parser.ParserError:
        if config_filepath:
            logging.warn("%s doesn't look like valid YAML, using environment variables" % config_filepath)
        config_from_file = {}

    config = {}
    keys_missing = []
    all_keys = mandatory_keys + optional_keys
    for key in all_keys:
        if key in os.environ:
            config[key] = os.environ[key]
        elif key in config_from_file:
            config[key] = config_from_file[key]
        else:
            keys_missing.append(key)


    def format_missing(missing):
        head = ", ".join(missing[:-1])
        if head:
            return "%s and %s" % (head, missing[-1])
        else:
            return missing[-1]

    missing_mandatory_keys = list(set(keys_missing) & set(mandatory_keys))
    if missing_mandatory_keys:
        message = "Couldn't find the following mandatory keys in config: %s" % format_missing(missing_mandatory_keys)
        logging.error(message)
        sys.exit(1)

    return config

class SpeciesConfig(object):
    def __init__(self, path):
      with open(path, 'r') as config_file:
        self.data = yaml.load(config_file)
      self.species_list = sorted(self.data['species'].keys())
      self.databases = self.data['databases']

if __name__ == '__main__':
    default_config_file = os.path.join(os.path.expanduser('~'),
                                       '.datapages_config.yml')
    config = get_config(os.environ.get('DATAPAGES_CONFIG_FILE',
                                       default_config_file))
    import json
    print(json.dumps(config, sort_keys=True))
    e = {key: value for key, value in os.environ.items() if 'DATAPAGES' in key}
    print(json.dumps(e, sort_keys=True))
    config_filepath = os.environ.get('DATAPAGES_CONFIG_FILE', default_config_file)
    with open(config_filepath, 'r') as config_file:
        config_in_file = yaml.load(config_file)
    print(json.dumps(config_in_file, sort_keys=True))

    


