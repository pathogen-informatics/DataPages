#!/usr/bin/env python3

import os
import pymysql

from pprint import pprint

db_host = os.environ['VRTRACK_HOST']
db_port = os.environ['VRTRACK_PORT']
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
                study.study_id = latest_project.study_id AND
                species.name LIKE %s"""

def get_species_details(name):
    with connection.cursor() as cursor:
        cursor.execute(query, (name,))
    return cursor.fetchall()

def get_species_names(path):
    with open(path, 'r') as species_file:
        species = [line.strip() for line in species_file]
    return species

species = get_species_names('/nfs/pathogen/project_pages/Project_webpages_species_list_Prokaryotes.txt')
details = {name: get_species_details(name) for name in species}

pprint(details)
