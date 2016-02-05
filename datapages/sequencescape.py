import logging
import pymysql
import time

class Sfind(object):
    def __init__(self, host, port, database, user):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Connecting to sequencescape on %s:%s" % (host, port))
        self.connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            db=database
        )
        self.max_ssids = 20
        self.wait = 1
        self.database = database

    def get_studies(self, project_ssids):
        self.logger.info("Getting sequencescape details from %s" %
                         self.database)
        SIZE=self.max_ssids
        ssid_groups = (project_ssids[i:i+SIZE] for i in range(0,len(project_ssids),SIZE))
        ssid_group = next(ssid_groups, [])
        studies = self._get_studies_for_group(ssid_group)
        for ssid_group in ssid_groups:
            time.sleep(self.wait)
            studies += self._get_studies_for_group(ssid_group)
        return studies       
    
    def _get_studies_for_group(self, project_ssids):
        if not project_ssids:
            return []
        query = """SELECT  study.internal_id as project_ssid,
        study.accession_number as study_accession,
        study.study_title as study_title,
        study.name as study_name,
        sample.strain as sample_strain,
        sample.public_name as sample_public_name,
        sample.name as sample_name,
        sample.common_name as sample_common_name,
        sample.organism as sample_organism,
        sample.name as sample_supplier_name,
        sample.accession_number as sample_accession
FROM    current_studies study,
        current_study_samples study_sample,
        current_samples sample
WHERE   study.internal_id IN %s AND
        study_sample.study_internal_id=study.internal_id AND
        sample.internal_id=study_sample.sample_internal_id"""
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, (project_ssids,))
            studies = cursor.fetchall()
        return studies
