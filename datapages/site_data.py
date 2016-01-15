import collections
import json
import logging
import os
import pandas as pd
import pickle
import shutil
import sys
import yaml

from datetime import datetime

from .common import species_filename, get_config, get_species_list
from .vrtrack import Vrtrack
from .enametadata import ENADetails
from .sequencescape import Sfind

DbDetails = collections.namedtuple('DbDetails', 'host, port, database, user')

def get_vrtrack_db_details(config):
    return DbDetails(
        config['DATAPAGES_VRTRACK_HOST'],
        int(config['DATAPAGES_VRTRACK_PORT']),
        config['DATAPAGES_VRTRACK_RO_USER'],
        config['DATAPAGES_VRTRACK_DATABASE']
    )

def get_sequencescape_db_details(config):
    return DbDetails(
        config['DATAPAGES_SEQUENCESCAPE_HOST'],
        int(config['DATAPAGES_SEQUENCESCAPE_PORT']),
        config['DATAPAGES_SEQUENCESCAPE_RO_USER'],
        config['DATAPAGES_SEQUENCESCAPE_DATABASE']
    )

def get_all_data(vrtrack_db_details, sequencescape_db_details):
    vrtrack = Vrtrack(vrtrack_db_details.host, vrtrack_db_details.port,
                      vrtrack_db_details.database, vrtrack_db_details.user)   
    lane_details = vrtrack.get_lanes()
    project_ssids = list({lane['project_ssid'] for lane in lane_details})
    study_accessions = list({lane['study_accession'] for lane in lane_details}) 
    ena = ENADetails()
    ena_run_details = ena.get_run_accessions(study_accessions)
    sfind = Sfind(sequencescape_db_details.host,
                  sequencescape_db_details.port,
                  sequencescape_db_details.database,
                  sequencescape_db_details.user)
    studies = sfind.get_studies(project_ssids)
    return lane_details, ena_run_details, studies
    
def cache_data(cache_path, project_ssids, ena_run_details, lane_details, studies):
    """Just for testing"""
    with open(cache_path, 'wb') as cache:
        pickle.dump({
                'project_ssids': project_ssids,
                'ena_run_details': ena_run_details,
                'lane_details': lane_details,
                'ss_studies': studies
            }, cache)

def reload_cache_data(cache_path):
    with open(cache_path, 'rb') as cache:
        all_data = pickle.load(cache)
        project_ssids = all_data['project_ssids']
        ena_run_details = all_data['ena_run_details']
        lane_details = all_data['lane_details']
        studies = all_data['ss_studies']
    del(all_data)
    return project_ssids, ena_run_details, lane_details, studies

def join_vrtrack_sequencescape(vrtrack, sequencescape):
    # Sequencescape has our 'public' names for things, like the study title
    # We want to use these in preference to the details in the vrtrack database
    sequencescape_study_data = sequencescape[['project_ssid', 'study_title', 'study_name']].drop_duplicates()
    joint_data = pd.merge(vrtrack, sequencescape_study_data, how='left',
                          on='project_ssid', sort=False, suffixes=('_v', '_ss'))
    del(sequencescape_study_data)
    
    sequencescape_sample_data = sequencescape[['sample_name', 'sample_accession', 'sample_common_name',
                                               'sample_organism', 'sample_public_name', 'sample_strain',
                                               'sample_supplier_name']].drop_duplicates()
    
    # Many entries in sequencescape share an ERS number with their entry in vrtrack
    # Use this as the joining key
    data_joined_by_sample_accession = pd.merge(joint_data.reset_index(),
                                               sequencescape_sample_data[sequencescape_sample_data['sample_accession'].notnull()],
                                               how='left',
                                               on='sample_accession',
                                               sort=False, suffixes=('_v', '_ss'))
    data_joined_by_sample_accession.set_index('index', inplace=True)
    data_joined_by_sample_accession.rename(columns={'sample_accession': 'sample_accession_v'}, inplace=True)
    data_joined_by_sample_accession['sample_accession_ss'] = data_joined_by_sample_accession['sample_accession_v']

    # Sometimes sequencescape doesn't know the ERS number, in those cases we have to use the sample_name
    data_joined_by_sample_name = pd.merge(joint_data.reset_index(), sequencescape_sample_data,
                                          how='inner',
                                          left_on='internal_sample_name',
                                          right_on='sample_name',
                                          sort=False, suffixes=('_v', '_ss'))
    data_joined_by_sample_name.set_index('index', inplace=True)
    
    # Merge the two matches, by default keeping the match based on ERS number
    assert sorted(data_joined_by_sample_accession.columns) == sorted(data_joined_by_sample_name.columns),             "Weird things happen if these don't have the same columns"   
    joint_data = data_joined_by_sample_accession.combine_first(data_joined_by_sample_name)
    return joint_data.reset_index(drop=True)

def add_canonical_data(joint_data):
    joint_data['canonical_study_name'] = joint_data.apply(lambda row: row['study_title'] or row['study_name'] or row['internal_project_name'], axis=1)
    joint_data['canonical_sample_name'] = joint_data.apply(lambda row: row['sample_public_name'] or row['sample_supplier_name'] or row['internal_sample_name'], axis=1)
    joint_data['canonical_strain'] = joint_data.apply(lambda row: row['sample_strain'] or 'Unknown', axis=1)

def merge_ena_status(joint_data, ena_details):
    run_ena_status = ena_details[['run_accession',]]
    run_ena_status['run_in_ena'] = True
    joint_data = pd.merge(joint_data, run_ena_status, on=['run_accession'], how='left', sort=False)
    joint_data['run_in_ena'] = joint_data['run_in_ena'] == True
    study_ena_status = ena_details[['study_accession',]]
    study_ena_status['study_in_ena'] = True
    study_ena_status.drop_duplicates(inplace=True)
    joint_data = pd.merge(joint_data, study_ena_status, on='study_accession', how='left', sort=False)
    return joint_data

def merge_data(lane_details, ena_run_details, studies):
    vrtrack_details = pd.DataFrame(lane_details)
    vrtrack_details['withdrawn'] = vrtrack_details['withdrawn'] == 1
    ena_details = pd.DataFrame(ena_run_details)
    ss_details = pd.DataFrame(studies)
    joint_data = join_vrtrack_sequencescape(vrtrack_details, ss_details)
    add_canonical_data(joint_data)
    joint_data = merge_ena_status(joint_data, ena_details)
    return joint_data

def build_relevant_data(joint_data, species_list):
    column_name_map = collections.OrderedDict([
        ('species_name', 'Species'),
        ('canonical_study_name', 'Study Name'),
        ('study_accession', 'Study Accession'),
        ('canonical_sample_name', 'Sample Name'),
        ('canonical_strain', 'Strain'),
        ('run_accession', 'Run Accession'),
        ('sample_accession_v', 'Sample Accession')
    ])
    original_column_names = list(column_name_map.keys())
    prefered_column_names = [column_name_map[key] for key in
                             original_column_names]

    tmp = joint_data[(joint_data['withdrawn'] == False) & 
                     joint_data['run_in_ena'] & 
                     joint_data['study_in_ena']]
    tmp = tmp[original_column_names]
    tmp.columns = prefered_column_names
    lowercase_cache = tmp.apply(lambda row: row['Species'].lower(), axis=1)
    for species in species_list:
        species_data = tmp[lowercase_cache.map(lambda el: el.startswith(species.lower()))]
        yield (species, {
            'columns': prefered_column_names,
            'data': species_data.values.tolist(),
            'species': species,
            'count': len(species_data.index)
        })

def _make_temp_dir(data_dir_temp):
    os.makedirs(data_dir_temp, mode=0o755) 

def _remove_old_backup(output_dir_backup):
    try:
        shutil.rmtree(output_dir_backup)
    except FileNotFoundError:
        pass

def _backup(output_dir_root, output_dir_backup):
    try:
        shutil.copytree(output_dir_root, output_dir_backup)
    except FileNotFoundError:
        pass

def _update_data(output_dir_temp, data_dir_temp, data_dir):
    try:
        shutil.rmtree(data_dir)
    except FileNotFoundError:
        pass
    shutil.move(data_dir_temp, data_dir)
    shutil.rmtree(output_dir_temp)

def _write_species_to_folder(data_dir_temp, species, data):
    output_filename = species_filename(species)
    output_filepath = os.path.join(data_dir_temp, output_filename)
    with open(output_filepath, 'w') as output_file:
        json.dump(data, output_file)
    return output_filename

def write_site_data_files(relevant_data, output_dir_root):
    now = datetime.now()
    summary = {'species': {},
               'created': now.isoformat()}
    timestamp = now.strftime("%Y%m%d%H%M%S")
    output_dir_temp = "%s_%s_temp" % (output_dir, timestamp)
    data_dir_temp = os.path.join(output_dir_temp, 'data')
    data_dir = os.path.join(output_dir_root, 'data')
    output_dir_backup = "%s_backup" % output_dir_root
    _make_temp_dir(data_dir_temp) 
    for species, data in relevant_data:
        output_filename = _write_species_to_folder(data_dir_temp, species, data)
        summary['species'][species] = {'filename': output_filename,
                                       'count': data['count']}
    summary_path = os.path.join(data_dir_temp, '_data_summary.json')
    with open(summary_path, 'w') as summary_file:
        json.dump(summary, summary_file)
    _remove_old_backup(output_dir_backup)
    _backup(output_dir_root, output_dir_backup)
    _update_data(output_dir_temp, data_dir_temp, data_dir)

if __name__ == '__main__':
    default_config_file = os.path.join(os.path.expanduser('~'),
                                       '.datapages_config.yml')
    config = get_config(os.environ.get('DATAPAGES_CONFIG_FILE',
                                       default_config_file))
    default_cache_path = os.path.join(os.path.expanduser('~'),
                                      ".datapages_cache.pkl")
    cache_path = config.get('DATAPAGES_DATA_CACHE_PATH', default_cache_path)

    if config.get('DATAPAGES_LOAD_DATA_CACHE') is None:
        logging.info("Loading data from databases")
        vrtrack_db_details = get_vrtrack_db_details(config)
        sequencescape_db_details = get_sequencescape_db_details(config)
        lane_details, ena_run_details, studies = get_all_data(vrtrack_db_details,
                                                              sequencescape_db_details)
    else:
        logging.warn("Loading cached data from %s" % cache_path)
        project_ssids, ena_run_details, lane_details, studies = reload_cache_data(cache_path)

    if not config.get('DATAPAGES_SAVE_DATA_CACHE') is None:
        logging.warn("Saving data to cache in %s" % cache_path)
        project_ssids = list({lane['project_ssid'] for lane in lane_details})
        cache_data(cache_path, project_ssids, ena_run_details, lane_details, studies)

    joint_data = merge_data(lane_details, ena_run_details, studies)

    species_list_filename = "Project_webpages_species_list_Prokaryotes.txt"
    species_list = get_species_list(species_list_filename)
    relevant_data = build_relevant_data(joint_data, species_list)
    output_dir = config.get('DATAPAGES_SITE_DATA_DIR', 'tmp_site')
    write_site_data_files(relevant_data, output_dir)