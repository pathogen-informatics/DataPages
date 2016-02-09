import json
import logging
import markdown
import os
import shutil
import sys

from datetime import datetime

from .common import species_filename

logger = logging.getLogger(__name__)

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

def write_domain_data_files(relevant_data, output_dir_root, domain_name):
    now = datetime.now()
    summary = {'species': {},
               'created': now.isoformat()}
    timestamp = now.strftime("%Y%m%d%H%M%S")
    output_dir_temp = os.path.join(output_dir_root, "%s_%s_temp" % (domain_name, timestamp))
    data_dir_temp = os.path.join(output_dir_temp, 'data')
    data_dir = os.path.join(output_dir_root, domain_name, 'data')
    logger.info("About to write data to %s" % data_dir)
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
