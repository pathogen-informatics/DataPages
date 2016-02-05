import logging
import pymysql

class Vrtrack(object):
    def __init__(self, host, port, database, user):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Connecting to vrtrack on %s:%s" % (host, port))
        self.connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            db=database
        )
        self.database = database

    def get_lanes(self):
        self.logger.info("Getting vrtrack details from %s" % self.database)
        query = """SELECT DISTINCT latest_project.name as internal_project_name,
                latest_sample.name as internal_sample_name,
                latest_lane.name as lane_name,
                latest_lane.acc as run_accession,
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
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query)
            lane_details = cursor.fetchall()

        return lane_details
