import collections
import logging
import os
import pandas as pd
import pickle
import yaml

from datetime import datetime

from .vrtrack import Vrtrack
from .enametadata import ENADetails
from .sequencescape import Sfind

DbDetails = collections.namedtuple('DbDetails', 'host, port, database, user')
logger = logging.getLogger(__name__)

def get_vrtrack_db_details_list(config, databases_list):
    return [DbDetails(
        config['DATAPAGES_VRTRACK_HOST'],
        int(config['DATAPAGES_VRTRACK_PORT']),
        database,
        config['DATAPAGES_VRTRACK_RO_USER']
    ) for database in databases_list]

def get_sequencescape_db_details(config):
    return DbDetails(
        config['DATAPAGES_SEQUENCESCAPE_HOST'],
        int(config['DATAPAGES_SEQUENCESCAPE_PORT']),
        config['DATAPAGES_SEQUENCESCAPE_DATABASE'],
        config['DATAPAGES_SEQUENCESCAPE_RO_USER']
    )

def get_all_data(vrtrack_db_details_list, sequencescape_db_details):
    lane_details = []
    for vrtrack_db_details in vrtrack_db_details_list:
      vrtrack = Vrtrack(vrtrack_db_details.host, vrtrack_db_details.port,
                        vrtrack_db_details.database, vrtrack_db_details.user)
      lane_details += vrtrack.get_lanes()
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

def cache_data(cache_path, domain_name, project_ssids, ena_run_details, lane_details, studies):
    """Just for testing"""
    try:
        with open(cache_path, 'rb') as cache_file:
            cache = pickle.load(cache_file)
    except EOFError:
        cache={}
    except FileNotFoundError:
        cache={}

    cache[domain_name] = {
        'project_ssids': project_ssids,
        'ena_run_details': ena_run_details,
        'lane_details': lane_details,
        'ss_studies': studies
    }
    with open(cache_path, 'wb') as cache_file:
        pickle.dump(cache, cache_file)

def reload_cache_data(cache_path, domain_name):
    with open(cache_path, 'rb') as cache_file:
        cache = pickle.load(cache_file)
    try:
        project_ssids = cache[domain_name]['project_ssids']
        ena_run_details = cache[domain_name]['ena_run_details']
        lane_details = cache[domain_name]['lane_details']
        studies = cache[domain_name]['ss_studies']
    except KeyError:
        raise ValueError("Could not load %s from %s" % (domain_name, cache_path))
    return project_ssids, ena_run_details, lane_details, studies

def join_vrtrack_sequencescape(vrtrack, sequencescape):
    logger.info("Joining vrtrack and sequencescape data")
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

def _get_default_columns(joint_data, column, default_columns, otherwise='Unknown'):
    default_column = default_columns[0]
    mask = joint_data[default_column].notnull() & (joint_data[default_column] != '')
    joint_data.loc[mask, column] = joint_data.loc[mask, default_column].values
    for default_column in default_columns[1:]:
        done = joint_data[column].notnull() & (joint_data[column] != '')
        mask = (done != True) & joint_data[default_column].notnull() & (joint_data[default_column] != '')
        joint_data.loc[mask, column] = joint_data.loc[mask, default_column].values
    done = joint_data[column].notnull() & (joint_data[column] != '')
    unknown = (done == False)
    joint_data.loc[unknown, column] = otherwise

def add_canonical_data(joint_data):
    logger.info("Finding canonical names for things")
    _get_default_columns(joint_data, 'canonical_study_name',
                         ['study_title', 'study_name', 'internal_project_name'])
    _get_default_columns(joint_data, 'canonical_sample_name',
                         ['sample_public_name', 'sample_supplier_name', 'internal_sample_name'])
    _get_default_columns(joint_data, 'canonical_strain',
                         ['sample_strain'])

def merge_ena_status(joint_data, ena_details):
    logger.info("Comparing with the details in the ENA")
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
    logger.info("Starting to merge vrtrack, sequencescape and ena data")
    vrtrack_details = pd.DataFrame(lane_details)
    vrtrack_details['withdrawn'] = vrtrack_details['withdrawn'] == 1
    ena_details = pd.DataFrame(ena_run_details)
    ss_details = pd.DataFrame(studies)
    joint_data = join_vrtrack_sequencescape(vrtrack_details, ss_details)
    add_canonical_data(joint_data)
    joint_data = merge_ena_status(joint_data, ena_details)
    return joint_data

def generate_empty_data(domain_config):
    logger.info("Building empty species data")
    now = datetime.now()
    prefered_column_names = [
        'Species',
        'Study Name',
        'Study Accession',
        'Sample Name',
        'Strain',
        'Run Accession',
        'Sample Accession'
    ]
    for species in domain_config.species_list:
        if not domain_config.is_visible(species):
            continue
        yield (species, {
            'columns': prefered_column_names,
            'count': 0,
            'data': [],
            'description': domain_config.render_description(species),
            'published_data_description': domain_config.render_published_data_description(species),
            'pubmed_ids': domain_config.pubmed_ids(species),
            'links': domain_config.render_links(species),
            'species': species,
            'updated': now.isoformat()
        })

def build_relevant_data(joint_data, domain_config):
    logger.info("Reformatting data for export")
    now = datetime.now()
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
    for species in domain_config.species_list:
        # Species can be temporarily hidden by setting
        # show: false
        # in their config
        if not domain_config.is_visible(species):
            continue

        mask = lowercase_cache.map(lambda el: el.startswith(species.lower()))
        # Some species have common names which they
        # may also be referred to by.
        for alias in domain_config.aliases(species):
            alias_mask = lowercase_cache.map(lambda el:
                                             el.startswith(alias.lower()))
            mask = mask | alias_mask
        species_data = tmp[mask]
        yield (species, {
            'columns': prefered_column_names,
            'count': len(species_data.index),
            'data': species_data.values.tolist(),
            'description': domain_config.render_description(species),
            'published_data_description': domain_config.render_published_data_description(species),
            'pubmed_ids': domain_config.pubmed_ids(species),
            'links': domain_config.render_links(species),
            'species': species,
            'updated': now.isoformat()
        })

def generate_data(global_config, domain_config):
    if global_config.get('DATAPAGES_LOAD_CACHE_PATH'):
        cache_path = global_config.get('DATAPAGES_LOAD_CACHE_PATH')
        logging.warn("Loading cached data from %s" % cache_path)
        cache = reload_cache_data(cache_path, domain_config.domain_name)
        project_ssids, ena_run_details, lane_details, studies = cache
    else:
        logging.info("Loading data from databases")
        vrtrack_db_details_list = get_vrtrack_db_details_list(global_config,
                                                         domain_config.databases)
        sequencescape_db_details = get_sequencescape_db_details(global_config)
        lane_details, ena_run_details, studies = get_all_data(vrtrack_db_details_list,
                                                              sequencescape_db_details)

    if global_config.get('DATAPAGES_SAVE_CACHE_PATH'):
        cache_path = global_config.get('DATAPAGES_SAVE_CACHE_PATH')
        logging.warn("Saving data to cache in %s" % cache_path)
        project_ssids = list({lane['project_ssid'] for lane in lane_details})
        cache_data(cache_path, domain_config.domain_name, project_ssids, ena_run_details, lane_details, studies)

    joint_data = merge_data(lane_details, ena_run_details, studies)

    relevant_data = build_relevant_data(joint_data, domain_config)
    return relevant_data
