import os

from jinja2 import Environment, FileSystemLoader

from .common import species_filename, get_species_list, get_config

output_dir = 'site/'

def get_template():
    datapages_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(datapages_dir)
    templates_dir = os.path.join(parent_dir, 'templates')
    loader = FileSystemLoader(templates_dir)
    env = Environment(loader=loader)
    index_template = env.get_template('index.html')
    return index_template

def write_index(species_list, output_dir):
    def species_url(species):
        return "data/%s" % species_filename(species)
    species_urls = {species: species_url(species) for species in
                    species_list}
    with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
        print(get_template().render(species_urls=species_urls), file=index_file)

if __name__ == '__main__':
    default_config_file = os.path.join(os.path.expanduser('~'),
                                       '.datapages_config.yml')
    config = get_config(os.environ.get('DATAPAGES_CONFIG_FILE',
                                       default_config_file))
    species_list_filename = "Project_webpages_species_list_Prokaryotes.txt"
    species_list = get_species_list(species_list_filename)
    output_dir = config.get('DATAPAGES_SITE_DATA_DIR', 'tmp_site')
    write_index(species_list, output_dir)
