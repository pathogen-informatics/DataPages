#!/usr/bin/env python3

import json
import os
import pymysql

from pprint import pprint
from boltons.strutils import slugify

db_host = os.environ['VRTRACK_HOST']
db_port = int(os.environ['VRTRACK_PORT'])
db_user = os.environ['VRTRACK_RO_USER']

db_db = 'pathogen_prok_track'

connection = pymysql.connect(
    host=db_host,
    port=db_port,
    user=db_user,
    db=db_db
)

query = """\
SELECT DISTINCT latest_project.name,
                latest_sample.name,
                latest_lane.name,
                latest_lane.acc,
                latest_project.ssid,
                individual.acc,
                study.acc,
                species.name
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
    with connection.cursor() as cursor:
        cursor.execute(query)
        details_list = cursor.fetchall()
    details_lookup = {}
    for detail in details_list:
        species_name = detail[7].lower()
        details_lookup.setdefault(species_name, []).append(detail)
    return {species: details_lookup.get(species.lower(), []) for species in species_list}

def get_species_names(path):
    with open(path, 'r') as species_file:
        species = [line.strip() for line in species_file]
    return species

def output_filename(species, output_dir):
    return os.path.join(output_dir, slugify(species).lower()+'.json')

def write_details(details, output_dir):
    for name, sub_details in details.items():
        outpath = output_filename(name, output_dir)
        with open(outpath, 'w') as outfile:
            json.dump({name: sub_details}, outfile)

def write_index(details, output_dir):
    with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
        print("""\
<html>
    <head>
        <script src="//code.jquery.com/jquery-1.11.3.min.js"></script>
    </head>
    <body>
        <ul>
""", file=index_file)

        for name in sorted(details.keys()):
            species_path=output_filename(name, output_dir)
            species_relative_path=species_path.replace(output_dir, '')
            print("            <li><a href='%s'>%s</a></li>" % (species_relative_path,
                                                    name), file=index_file)
        print("        </ul>\n    <body>", file=index_file)

#species = get_species_names('/nfs/pathogen/project_pages/Project_webpages_species_list_Prokaryotes.txt')
species = get_species_names('Project_webpages_species_list_Prokaryotes.txt')
details = get_all_details(species)
write_details(details, output_dir)
write_index(details, output_dir)

