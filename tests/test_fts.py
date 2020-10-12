#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Unit tests for fts.

'''
import logging
from datetime import datetime
from os.path import join

import pytest
from hdx import hdx_locations
from hdx.data.vocabulary import Vocabulary
from hdx.hdx_configuration import Configuration
from hdx.location.country import Country
from hdx.utilities.compare import assert_files_same
from hdx.utilities.downloader import Download
from hdx.utilities.path import temp_dir

from fts.download import FTSDownload
from fts.locations import Locations
from fts.main import FTS

logger = logging.getLogger(__name__)


class TestFTS:
    @pytest.fixture(scope='function')
    def configuration(self):
        Configuration._create(hdx_read_only=True, user_agent='test',
                              project_config_yaml=join('tests', 'config', 'project_configuration.yml'))
        hdx_locations.Locations.set_validlocations([{'name': 'afg', 'title': 'Afghanistan'}, {'name': 'jor', 'title': 'Jordan'}, {'name': 'pse', 'title': 'occupied Palestinian territory'}])
        Country.countriesdata(False)
        Vocabulary._approved_vocabulary = {'tags': [{'name': 'hxl'}, {'name': 'financial tracking service - fts'}, {'name': 'aid funding'}, {'name': 'epidemics and outbreaks'}, {'name': 'covid-19'}], 'id': '4e61d464-4943-4e97-973a-84673c1aaa87', 'name': 'approved'}
        return Configuration.read()

    def test_generate_dataset_and_showcase(self, configuration):

        def check_resources(dsresources):
            for resource in dsresources:
                resource_name = resource['name']
                expected_file = join('tests', 'fixtures', resource_name)
                actual_file = join(folder, resource_name)
                assert_files_same(expected_file, actual_file)

        with temp_dir('FTS-TEST', delete_on_failure=False) as folder:
            with Download(user_agent='test') as downloader:
                ftsdownloader = FTSDownload(configuration, downloader, testpath=True)
                notes = configuration['notes']
                today = datetime.now()

                locations = Locations(ftsdownloader)
                logger.info('Number of country datasets to upload: %d' % len(locations.countries))

                fts = FTS(ftsdownloader, locations, today, notes, start_year=2019)
                dataset, showcase, hxl_resource, ordered_resource_names = fts.generate_dataset_and_showcase(folder, locations.countries[0])
                assert dataset == {'groups': [{'name': 'afg'}], 'name': 'fts-requirements-and-funding-data-for-afghanistan',
                                   'title': 'Afghanistan - Requirements and Funding Data',
                                   'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}],
                                   'dataset_date': '10/12/2020',
                                   'data_update_frequency': '1', 'maintainer': '196196be-6037-4488-8b71-d786adf4c081',
                                   'owner_org': 'fb7c2910-6080-4b66-8b4f-0be9b6dc4d8e', 'subnational': '0', 'notes': notes}
                resources = dataset.get_resources()
                assert resources == [{'name': 'fts_incoming_funding_afg.csv', 'description': 'FTS Incoming Funding Data for Afghanistan for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_internal_funding_afg.csv', 'description': 'FTS Internal Funding Data for Afghanistan for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_afg.csv', 'description': 'FTS Annual Requirements and Funding Data for Afghanistan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_globalcluster_afg.csv', 'description': 'FTS Annual Requirements and Funding Data by Global Cluster for Afghanistan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_cluster_afg.csv', 'description': 'FTS Annual Requirements and Funding Data by Cluster for Afghanistan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_covid_afg.csv', 'description': 'FTS Annual Covid Requirements and Funding Data for Afghanistan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'}]
                check_resources(resources)
                assert showcase == {'image_url': 'https://fts.unocha.org/sites/default/files/styles/fts_feature_image/public/navigation_101.jpg',
                                    'name': 'fts-requirements-and-funding-data-for-afghanistan-showcase',
                                    'notes': 'Click the image on the right to go to the FTS funding summary page for Afghanistan',
                                    'url': 'https://fts.unocha.org/countries/1/flows/2020', 'title': 'FTS Afghanistan Summary Page',
                                    'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                             {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                             {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                             {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}
                assert hxl_resource == resources[4]
                assert ordered_resource_names == ['fts_requirements_funding_afg.csv', 'fts_requirements_funding_covid_afg.csv', 'fts_requirements_funding_cluster_afg.csv', 'fts_requirements_funding_globalcluster_afg.csv', 'fts_incoming_funding_afg.csv', 'fts_internal_funding_afg.csv']

                dataset, showcase, hxl_resource, ordered_resource_names = fts.generate_dataset_and_showcase(folder, locations.countries[1])
                assert dataset == {'groups': [{'name': 'jor'}], 'name': 'fts-requirements-and-funding-data-for-jordan',
                                   'title': 'Jordan - Requirements and Funding Data',
                                   'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}],
                                   'dataset_date': '10/12/2020',
                                   'data_update_frequency': '1', 'maintainer': '196196be-6037-4488-8b71-d786adf4c081',
                                   'owner_org': 'fb7c2910-6080-4b66-8b4f-0be9b6dc4d8e', 'subnational': '0',
                                   'notes': notes}

                resources = dataset.get_resources()
                assert resources == [{'name': 'fts_incoming_funding_jor.csv', 'description': 'FTS Incoming Funding Data for Jordan for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_internal_funding_jor.csv', 'description': 'FTS Internal Funding Data for Jordan for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_jor.csv', 'description': 'FTS Annual Requirements and Funding Data for Jordan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_globalcluster_jor.csv', 'description': 'FTS Annual Requirements and Funding Data by Global Cluster for Jordan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_cluster_jor.csv', 'description': 'FTS Annual Requirements and Funding Data by Cluster for Jordan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_covid_jor.csv', 'description': 'FTS Annual Covid Requirements and Funding Data for Jordan',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'}]
                check_resources(resources)
                assert showcase == {
                    'image_url': 'https://fts.unocha.org/sites/default/files/styles/fts_feature_image/public/navigation_101.jpg',
                    'name': 'fts-requirements-and-funding-data-for-jordan-showcase',
                    'notes': 'Click the image on the right to go to the FTS funding summary page for Jordan',
                    'url': 'https://fts.unocha.org/countries/114/flows/2020', 'title': 'FTS Jordan Summary Page',
                    'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}
                assert hxl_resource == resources[4]
                assert ordered_resource_names == ['fts_requirements_funding_jor.csv', 'fts_requirements_funding_covid_jor.csv', 'fts_requirements_funding_cluster_jor.csv', 'fts_requirements_funding_globalcluster_jor.csv', 'fts_incoming_funding_jor.csv', 'fts_internal_funding_jor.csv']

                dataset, showcase, hxl_resource, ordered_resource_names = fts.generate_dataset_and_showcase(folder, locations.countries[2])
                assert dataset == {'groups': [{'name': 'pse'}], 'name': 'fts-requirements-and-funding-data-for-occupied-palestinian-territory',
                                   'title': 'occupied Palestinian territory - Requirements and Funding Data',
                                   'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                            {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}],
                                   'dataset_date': '10/12/2020',
                                   'data_update_frequency': '1', 'maintainer': '196196be-6037-4488-8b71-d786adf4c081',
                                   'owner_org': 'fb7c2910-6080-4b66-8b4f-0be9b6dc4d8e', 'subnational': '0',
                                   'notes': notes}

                resources = dataset.get_resources()
                assert resources == [{'name': 'fts_incoming_funding_pse.csv', 'description': 'FTS Incoming Funding Data for occupied Palestinian territory for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_internal_funding_pse.csv', 'description': 'FTS Internal Funding Data for occupied Palestinian territory for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_outgoing_funding_pse.csv', 'description': 'FTS Outgoing Funding Data for occupied Palestinian territory for 2020',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_pse.csv', 'description': 'FTS Annual Requirements and Funding Data for occupied Palestinian territory',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_globalcluster_pse.csv', 'description': 'FTS Annual Requirements and Funding Data by Global Cluster for occupied Palestinian territory',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_cluster_pse.csv', 'description': 'FTS Annual Requirements and Funding Data by Cluster for occupied Palestinian territory',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'},
                                     {'name': 'fts_requirements_funding_covid_pse.csv', 'description': 'FTS Annual Covid Requirements and Funding Data for occupied Palestinian territory',
                                      'format': 'csv', 'resource_type': 'file.upload', 'url_type': 'upload'}]
                check_resources(resources)
                assert showcase == {
                    'image_url': 'https://fts.unocha.org/sites/default/files/styles/fts_feature_image/public/navigation_101.jpg',
                    'name': 'fts-requirements-and-funding-data-for-occupied-palestinian-territory-showcase',
                    'notes': 'Click the image on the right to go to the FTS funding summary page for occupied Palestinian territory',
                    'url': 'https://fts.unocha.org/countries/171/flows/2020', 'title': 'FTS occupied Palestinian territory Summary Page',
                    'tags': [{'name': 'hxl', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'financial tracking service - fts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'aid funding', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                             {'name': 'covid-19', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}
                assert hxl_resource == resources[5]
                assert ordered_resource_names == ['fts_requirements_funding_pse.csv', 'fts_requirements_funding_covid_pse.csv', 'fts_requirements_funding_cluster_pse.csv', 'fts_requirements_funding_globalcluster_pse.csv', 'fts_incoming_funding_pse.csv', 'fts_internal_funding_pse.csv', 'fts_outgoing_funding_pse.csv']
