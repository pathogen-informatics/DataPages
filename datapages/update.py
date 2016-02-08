import logging
import os
import pickle

from .common import get_config, SpeciesConfig
from .write_data import write_site_data_files
from .regenerate_data import generate_data
from .update_html import write_index

logger = logging.getLogger('datapages')

if __name__ == '__main__':
    logger.setLevel(logging.INFO)
    default_config_file = os.path.join(os.path.expanduser('~'),
                                       '.datapages_global_config.yml')
    config = get_config(os.environ.get('DATAPAGES_GLOBAL_CONFIG',
                                       default_config_file))
    default_cache_path = os.path.join(os.path.expanduser('~'),
                                      ".datapages_cache.pkl")
    config.setdefault('DATAPAGES_DATA_CACHE_PATH', default_cache_path)

    species_config_filename = os.environ['DATAPAGES_SPECIES_CONFIG']
    species_config = SpeciesConfig(species_config_filename)

    data = generate_data(config, species_config)

    site_dir = config.get('DATAPAGES_SITE_DATA_DIR', 'site')
    write_site_data_files(data, site_dir, species_config.name)
    write_index(species_config.species_list, site_dir, species_config.name)
