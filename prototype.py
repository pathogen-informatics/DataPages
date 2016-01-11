#!/usr/bin/env python3

import json
import os
import pymysql

from boltons.strutils import slugify
from jinja2 import Environment, FileSystemLoader

db_host = os.environ['VRTRACK_HOST']
db_port = int(os.environ['VRTRACK_PORT'])
db_user = os.environ['VRTRACK_RO_USER']

db_db = 'pathogen_prok_track'

query = """\
SELECT DISTINCT latest_project.name as internal_project_name,
                latest_sample.name as internal_sample_name,
                latest_lane.name as lane_name,
                latest_lane.acc as lane_accession,
                latest_lane.withdrawn as withdrawn,
                latest_project.ssid as project_ssid,
                individual.acc as sample_accession,
                study.acc as study_accession,
                species.name as species_name
FROM            species,
                individual,
                latest_sample,
                library,
                latest_project,
                latest_lane,
                study
WHERE           latest_lane.library_id = library.library_id AND
                library.sample_id = latest_sample.sample_id AND
                latest_sample.individual_id = individual.individual_id AND
                latest_sample.project_id = latest_project.project_id AND
                species.species_id = individual.species_id AND
                study.study_id = latest_project.study_id"""

output_dir = 'site/'

def get_all_details(species_list):
    # TODO: Remove the DB caching from this function
    try:
        with open('details.cache', 'r') as cache_file:
            details = json.load(cache_file)
            print("Reading cache")
            return details
    except:
        print("Cache miss, going to DB")
    connection = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        db=db_db
    )
    with connection.cursor() as cursor:
        cursor.execute(query)
        details_list = cursor.fetchall()
    details_lookup = {}
    for detail in details_list:
        species_name = detail[7].lower()
        details_lookup.setdefault(species_name, []).append(detail)
    details = {species: details_lookup.get(species.lower(), []) for species in species_list}
    with open('details.cache', 'w') as cache_file:
        print("Writing cache")
        json.dump(details, cache_file)
    return details

def get_species_names(path):
    with open(path, 'r') as species_file:
        species = [line.strip() for line in species_file]
    return species

def output_filename(species):
    return slugify(species).lower()+'.json'

def output_filepath(species, output_dir):
    return os.path.join(output_dir, output_filename(species))

def write_details(details, output_dir):
    for name, sub_details in details.items():
        outpath = output_filepath(name, output_dir)
        with open(outpath, 'w') as outfile:
            json.dump({'data': sub_details}, outfile)

def get_template():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    templates_dir = os.path.join(script_dir, 'templates')
    loader = FileSystemLoader(templates_dir)
    env = Environment(loader=loader)
    index_template = env.get_template('index.html')
    return index_template

def write_index(details, output_dir):
    species_urls = {name: output_filename(name) for name in details.keys()}
    with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
        print(get_template().render(species_urls=species_urls), file=index_file)

if __name__ == '__main__':
  # TODO: FIXME
  #species = get_species_names('/nfs/pathogen/project_pages/Project_webpages_species_list_Prokaryotes.txt')
  species = get_species_names('Project_webpages_species_list_Prokaryotes.txt')
  details = get_all_details(species)
  write_details(details, output_dir)
  write_index(details, output_dir)
