import re
import requests
import time
from xml.etree import ElementTree

class ENADetails(object):
    def __init__(self):
        self.url_template = "http://www.ebi.ac.uk/ena/data/view/%s&display=xml"
        self.max_accessions = 20
        self.wait = 1
    
    def get_run_accessions(self, study_accessions):
        SIZE=self.max_accessions
        accn_groups = (study_accessions[i:i+SIZE] for i in range(0,len(study_accessions),SIZE))
        accn_group = next(accn_groups, [])
        sample_accessions = self._get_run_accessions_for_group(accn_group)
        for accn_group in accn_groups:
            time.sleep(self.wait)
            sample_accessions += self._get_run_accessions_for_group(accn_group)
        return sample_accessions       
    
    def _get_run_accessions_for_group(self, study_accessions):
        sample_accessions = []
        if not study_accessions:
            return []
        studies_accessions_string = ",".join(study_accessions)
        studies_response = requests.get(self.url_template % studies_accessions_string)
        studies_response.raise_for_status()
        studies_tree = ElementTree.fromstring(studies_response.content)
        for study in studies_tree.findall('STUDY'):
            study_accession = study.attrib['accession']
            run_ids_element = study.find('./STUDY_LINKS/STUDY_LINK/XREF_LINK/[DB="ENA-RUN"]/ID')
            if run_ids_element is None:
                continue
            run_ids_range_string = run_ids_element.text
            run_ids_list = self.parse_run_ids(run_ids_range_string)
            sample_accessions += [{'study_accession': study_accession, 'run_accession': run_accession}
                                  for run_accession in run_ids_list]
        return sample_accessions       
            
    def parse_id_range(self, id_range):
        try:
            (alpha, first_num, second_num) = re.match(r'^([a-zA-Z]+)([0-9]+)-\1([0-9]+)$', id_range).groups()
            num_digits = len(first_num)
            first_num, second_num = int(first_num), int(second_num)
        except AttributeError:
            if re.match(r'[a-zA-Z]+[0-9]+', id_range):
                return [id_range]
            else:
                raise
        else:
            return [alpha+str(num).zfill(num_digits) for num in range(first_num, second_num+1)]

    def parse_run_ids(self, run_ids_string):
        run_ranges = run_ids_string.split(",")
        runs_ids = []
        for id_range in run_ranges:
            runs_ids += self.parse_id_range(id_range)
        return runs_ids
