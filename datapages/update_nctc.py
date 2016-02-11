import argparse
import logging
import os
import pandas as pd
import pickle
import re
import yaml

from argparse import ArgumentTypeError, FileType

from .common import cache_data, reload_cache_data, \
                    _is_dir, _could_write, _could_read, \
                    get_config
from .update_projects_html import get_template
from .regenerate_data import get_vrtrack_db_details_list, get_sequencescape_db_details, \
                             get_all_data, _get_default_columns

logger = logging.getLogger('datapages')

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
    parser.add_argument('nctc_config', type=FileType(mode='r'),
                        help="Config for the nctc project in YAML")


    return parser.parse_args()

def _file_to_ftp_url(path, ftp_root_dir, ftp_root_url):
    root_dir = os.path.abspath(ftp_root_dir)
    abspath = os.path.abspath(path)
    re.sub(root_dir, ftp_root_url, abspath)

def get_all_paths(root_dir):
    logger.info("Finding all the files in %s" % root_dir)
    all_files = []
    abs_root_dir = os.path.abspath(root_dir)
    for root, dirnames, filenames in os.walk(abs_root_dir):
        all_files += [os.path.join(root, fn) for fn in filenames]
    logger.info("Found %s files in %s" % (len(all_files), root_dir))
    return all_files

def _parse_automatic_gffs(all_paths, root_dir, root_url):
    logger.info("Getting details of automatic gff files")
    lookup = []
    file_regex = "([^/]+).gff$"
    path_regex = re.compile(os.path.join(root_dir, file_regex))
    for path, match in ((path, path_regex.match(path)) for path in all_paths):
        if match:
            sample_accession, = match.groups()
            url = _file_to_ftp_url(path, root_dir, root_url)
            lookup.append({
                'url': url,
                'path': path,
                'sample_accession': sample_accession
            })
    return lookup

def _gff_stats(gff_path):
    def _is_chromosome(line):
        if ('sequence-region' in line and 'chromosome' in line):
            return True
        if ('sequence-region' in line and 'contig' in line):
            return True
        return False
    def _is_plasmid(line):
        if ('sequence-region' in line and 'plasmid' in line):
            return True
        return False
    chromosome_count = 0
    plasmid_count = 0
    with open(gff_path, 'r') as gff_file:
        for line in gff_file:
            if _is_chromosome(line):
                chromosome_count += 1
            if _is_plasmid(line):
                plasmid_count += 1
    return {
        'chromosomes': chromosome_count,
        'plasmids': plasmid_count
    }

def _parse_manual_gffs(all_paths, root_dir, root_url):
    logger.info("Getting details of manual gff files")
    lookup = []
    file_regex = "([^/]+).gff$"
    path_regex = re.compile(os.path.join(root_dir, file_regex))
    for path, match in ((path, path_regex.match(path)) for path in all_paths):
        if match:
            sample_accession, = match.groups()
            url = _file_to_ftp_url(path, root_dir, root_url)
            data = {
                'url': url,
                'path': path,
                'sample_accession': sample_accession
            }
            data.update(_gff_stats(path))
            lookup.append(data)
    return lookup


def _embl_stats(embl_path):
    def _is_chromosome(line):
        if 'label=chrom' in line:
            return True
        return False
    def _is_plasmid(line):
        if 'label=plasmid' in line:
            return True
        return False
    chromosome_count = 0
    plasmid_count = 0
    with open(embl_path, 'r') as embl_file:
        for line in embl_file:
            if _is_chromosome(line):
                chromosome_count += 1
            if _is_plasmid(line):
                plasmid_count += 1
    return {
        'chromosomes': chromosome_count,
        'plasmids': plasmid_count
    }

def _parse_manual_embls(all_paths, root_dir, root_url):
    logger.info("Getting details of manual embl files")
    lookup = []
    file_regex = "([^/]+).embl$"
    path_regex = re.compile(os.path.join(root_dir, file_regex))
    for path, match in ((path, path_regex.match(path)) for path in all_paths):
        if match:
            sample_accession, = match.groups()
            url = _file_to_ftp_url(path, root_dir, root_url)
            data = {
                'url': url,
                'path': path,
                'sample_accession': sample_accession
            }
            data.update(_embl_stats(path))
            lookup.append(data)
    return lookup

def file_mappings(all_paths, nctc_config):
    logger.info("Mapping files in %s to successful assemblies" % nctc_config.ftp_root_dir)
    automatic_gffs = _parse_automatic_gffs(all_paths,
                                           nctc_config.automatic_gffs_dir,
                                           nctc_config.automatic_gffs_url)
    manual_embls = _parse_manual_embls(all_paths,
                                       nctc_config.manual_embls_dir,
                                       nctc_config.manual_embls_url)
    manual_gffs = _parse_manual_gffs(all_paths,
                                     nctc_config.manual_gffs_dir,
                                     nctc_config.manual_gffs_url)
    return (
        pd.DataFrame(automatic_gffs),
        pd.DataFrame(manual_embls),
        pd.DataFrame(manual_gffs)
    )

def add_canonical_nctc_data(joint_data):
    logger.info("Finding canonical names for things")
    _get_default_columns(joint_data, 'chromosomes',
                         ['chromosomes_man_embl', 'chromosomes_man_gff'],
                         'Pending')
    _get_default_columns(joint_data, 'plasmids',
                         ['plasmids_man_embl', 'plasmids_man_gff'],
                         'Pending')

def merge_nctc_data(database_data, automatic_gffs, manual_embls, manual_gffs):
    logging.info("Merging in assembly details")
    joint_data = pd.merge(database_data, automatic_gffs,
                          left_on='sample_accession_v', right_on='sample_accession',
                          how='left')
    joint_data = pd.merge(joint_data, manual_embls,
                          left_on='sample_accession_v', right_on='sample_accession',
                          how=left, suffixes=('_auto_gff', '_man_embl'))
    manual_gffs.rename(columns={'url': 'url_man_gff', 'path': 'path_man_gff',
                                'chromosomes': 'chromosomes_man_gff',
                                'plasmids': 'plasmids_man_gff'}, inplace=True)
    joint_data = pd.merge(joint_data, manual_gffs,
                          left_on='sample_accession_v', right_on='sample_accession',
                          how=left)
    add_canonical_nctc_data(joint_data)
    return joint_data


def _list_run_accessions(group):
    return pd.Series({
        'Run Accessions': group.unique().tolist()
    })

def _group_run_accessions(data):
    logging.info("Group runs on the same data together")
    data.columns = prefered_column_names
    columns_except_run = list(data.columns.values)
    columns_except_run = columns_except_run.remove('Run Accession')
    data = data.groupby(columns_except_run).apply(_list_run_accessions)
    data.reset_index(inplace=True)
    return data

def build_relevant_nctc_data(joint_data, nctc_config):
    logger.info("Reformatting data for export")
    now = datetime.now()
    column_name_map = collections.OrderedDict([
        ('species_name', 'Species'),
        ('canonical_strain', 'Strain'),
        ('sample_accession_v', 'Sample Accession'),
        ('run_accession', 'Run Accession'),
        ('url_man_gff', 'Manual GFF URL'),
        ('url_auto_gff', 'Automatic GFF URL'),
        ('url_auto_embl', 'Automatic EMBL URL'),
        ('chromosomes', 'Manual Assembly Chromosome Contig Number'),
        ('plasmids', 'Manual Assembly Plasmid Contig Number'),
    ])
    original_column_names = list(column_name_map.keys())
    prefered_column_names = [column_name_map[key] for key in
                             original_column_names]

    # Don't include data not in ENA
    data = joint_data[(joint_data['withdrawn'] == False) &
                     joint_data['run_in_ena'] &
                     joint_data['study_in_ena']]

    # Keep only the relevant project IDs
    data = data[data['project_ssid'].isin(ntct_config.project_ssids)]

    # Only include the columns we like
    data = data[original_column_names]

    # Group run accessions
    data = _group_run_accessions(data)

    # Deal with aliases
    for alias, original_names in nctc_config.aliases:
        data.loc[df['Species'].isin(original_names), 'Species'] = alias

    return {
        'columns': prefered_column_names,
        'count': len(data.index),
        'data': data.values.tolist(),
        'updated': now.isoformat()
    }

class NctcConfig(object):
    def __init__(self, config_file):
        self.data = yaml.load(config_file)
        self.type = self.data['metadata']['type']
        if self.type != 'nctc':
            message = "Expected %s to contain nctc config, got %s; skipping" % (config_file.name, self.type)
            raise ValueError(message)
        self.nctc_name = self.data['metadata']['name']
        self.databases = self.data['databases']
        self.ftp_root_dir = self.data['ftp_root_dir']
        self.project_ssids = self.data['project_ssids']
        self.aliases = self.data['aliases']
        self.automatic_gffs_dir = self.data['automatic_gffs']['root_dir']
        self.automatic_gffs_url = self.data['automatic_gffs']['root_url']
        self.manual_embls_dir = self.data['manual_embls']['root_dir']
        self.manual_embls_url = self.data['manual_embls']['root_url']
        self.manual_gffs_dir = self.data['manual_gffs']['root_dir']
        self.manual_gffs_url = self.data['manual_gffs']['root_url']

def generate_nctc_data(global_config, nctc_config):
    if global_config.get('DATAPAGES_LOAD_CACHE_PATH'):
        cache_path = global_config.get('DATAPAGES_LOAD_CACHE_PATH')
        logging.warn("Loading cached data from %s" % cache_path)
        cache = reload_cache_data(cache_path, nctc_config.nctc_name)
        project_ssids = data['project_ssids']
        ena_run_details = data['ena_run_details']
        lane_details = data['lane_details']
        studies = data['ss_studies']
        all_paths = data['all_paths']

    else:
        logging.info("Loading data from databases")
        vrtrack_db_details_list = get_vrtrack_db_details_list(global_config,
                                                         nctc_config.databases)
        sequencescape_db_details = get_sequencescape_db_details(global_config)
        lane_details, ena_run_details, studies = get_all_data(vrtrack_db_details_list,
                                                              sequencescape_db_details)
        all_paths = get_all_paths(nctc_config.ftp_root_dir)

    if global_config.get('DATAPAGES_SAVE_CACHE_PATH'):
        cache_path = global_config.get('DATAPAGES_SAVE_CACHE_PATH')
        logging.warn("Saving data to cache in %s" % cache_path)
        project_ssids = list({lane['project_ssid'] for lane in lane_details})
        data = {
            'project_ssids': project_ssids,
            'ena_run_details': ena_run_details,
            'lane_details': lane_details,
            'ss_studies': studies,
            'all_paths': all_paths
        }
        cache_data(cache_path, domain_config.domain_name, data)

    automatic_gffs, manual_embls, manual_gffs = file_mappings(all_paths, nctc_config)
    database_data = merge_data(lane_details, ena_run_details, studies)
    joint_data = merge_nctc_data(database_data, automatic_gffs, manual_embls,
                                 manual_gffs)

    relevant_data = build_relevant_data(joint_data, nctc_config)
    return relevant_data

def write_nctc_index(relevant_data, output_dir_root, nctc_config):
    logger.info("Writing results to %s" % output_dir_root)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    output_dir = os.path,join(output_dir_root, nctc_config.nctc_name)
    output_dir_temp = os.path.join(output_dir_root, "%s_%s_temp" %
                                   (nctc_config.nctc_name, timestamp))
    os.makedirs(output_dir_temp, mode=0o755)
    output_file_path = os.path.join(output_dir_temp, 'index.html')
    output_dir_backup = "%s_backup" % os.path.abspath(output_dir_root)
    template = get_template('nctc.index.html')
    content = template.render(
        title="Awesom NCTC page",
        description="A page about the awesome NCTC project",
        data=json.dumps(relevant_data, sort_keys=True, indent=4,
                        separators=(',', ': '))
    )
    with open(output_file_path, 'w') as output_file:
        print(content, file=output_file)

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
        config['DATAPAGES_SAVE_CACHE_PATH'] = args.save_cache
    else:
        config.setdefault('DATAPAGES_SAVE_CACHE_PATH', None)

    if args.load_cache:
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

    nctc_config = NctcConfig(args.nctc_config)
    logger.info("Processing %s" % args.nctc_config.name)

    if nctc_config.type != 'nctc':
        message = "Expected config type of nctc in %s, got %s" % \
                     (args.nctc_config.name, nctc_config.type)
        logger.error(message)
        raise ValueError(message)

    data = generate_nctc_data(config, nctc_config)
    write_nctc_index(relevant_data, site_dir, nctc_config)

if __name__ == '__main__':
    main()
