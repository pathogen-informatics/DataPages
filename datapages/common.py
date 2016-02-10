import logging
import markdown
import os
import sys
import yaml

from boltons.strutils import slugify
from jinja2 import Template

def species_filename(species):
    return slugify(species).lower()+'.json'

def cache_data(cache_path, name, data):
    """Just for testing"""
    try:
        with open(cache_path, 'rb') as cache_file:
            cache = pickle.load(cache_file)
    except EOFError:
        cache={}
    except FileNotFoundError:
        cache={}

    cache[name] = data
    with open(cache_path, 'wb') as cache_file:
        pickle.dump(cache, cache_file)

def reload_cache_data(cache_path, name):
    with open(cache_path, 'rb') as cache_file:
        cache = pickle.load(cache_file)
    try:
        data = cache[name]
    except KeyError:
        raise ValueError("Could not load %s from %s" % (name, cache_path))
    return data

def get_config(config_file):
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
        'DATAPAGES_LOAD_CACHE_PATH',
        'DATAPAGES_SAVE_CACHE_PATH'
    ]

    try:
        config_file.seek(0)
        config_from_file = yaml.load(config_file)
    except IOError:
        logging.warn("Could not load config from %s, using environment variables" % config_file.name)
        config_from_file = {}
    except yaml.parser.ParserError:
        logging.warn("%s doesn't look like valid YAML, using environment variables" % config_file.name)
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

class DomainConfig(object):
    def __init__(self, config_file):
        self.data = yaml.load(config_file)
        self.type = self.data['metadata'].get('type', 'unknown')
        self.species_list = sorted(self.data['species'].keys())
        self.databases = self.data['databases']
        self.list_data = self.data['metadata'].get('list_data', False)
        self.domain_name = self.data['metadata']['name']
        self.domain_title = self.data['metadata']['title']

    def is_visible(self, species):
        species_data = self.data['species'].get(species, {})
        return species_data.get('show', True)

    def aliases(self, species):
        species_data = self.data['species'].get(species, {})
        return species_data.get('aliases', [])

    def render_domain_description(self):
        description = self.data['metadata']['description']
        html = markdown.markdown(description,
                                 extensions=['markdown.extensions.tables'])
        return html

    def render_description(self, species):
        species_data = self.data['species'].get(species, {})
        markdown_content = species_data.get('description', '')
        html = markdown.markdown(markdown_content,
                                 extensions=['markdown.extensions.tables'])
        return html

    def render_published_data_description(self, species):
        species_data = self.data['species'].get(species, {})
        markdown_content = species_data.get('published_data_description', '')
        html = markdown.markdown(markdown_content,
                                 extensions=['markdown.extensions.tables'])
        return html

    def pubmed_ids(self, species):
        species_data = self.data['species'].get(species, {})
        return species_data.get('pubmed_ids', [])

    def render_links(self, species):
        species_data = self.data['species'].get(species, {})
        links = species_data.get('links', [])
        template = Template("""\
{% if links -%}
<h4>Relevant Links</h4>
<ul>
  {%- for link in links %}
  <li><a href="{{ link['url'] }}">{{ link['text'] }}</a></li>
  {%- endfor %}
</ul>
{%- endif %}""")
        html = template.render(links=links)
        return html
