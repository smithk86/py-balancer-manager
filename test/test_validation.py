import os.path

import pytest
import random

from get_vars import get_var
from py_balancer_manager import ValidationClient, ValidatedRoute, ValidatedCluster
import requests_mock


@pytest.fixture(
    scope='class',
    params=get_var('servers'),
    ids=[s['id'] for s in get_var('servers')]
)
def client(request):

    module_directory = os.path.abspath(os.path.dirname(__file__))
    server = request.param

    if server.get('url')[:4] == 'mock':
        with open('{module_directory}/data/{data_file}'.format(module_directory=module_directory, data_file=server['data_file'])) as fh:
            mock_data = fh.read()
    else:
        mock_data = None

    client = ValidationClient(
        server['url'],
        insecure=server.get('insecure', False),
        username=server.get('username', None),
        password=server.get('password', None),
        mock_data=mock_data
    )

    profile = client.get_profile()
    assert type(profile) is dict
    client.set_profile(profile)

    def fin():
        client.close()

    request.cls.server = server
    request.cls.client = client


@pytest.mark.usefixtures('client')
class TestValidationClient():

    def skip_mock_server(self):

        if self.server.get('url')[:4] == 'mock':
            pytest.skip('mock adapter')

    def test_routes(self):

        assert type(self.client.get_routes()) is list
        for route in self.client.get_routes():
            assert type(route) is ValidatedRoute

    def test_validate_clusters_and_routes(self):

        self.skip_mock_server()

        assert self.client.holistic_compliance_status is True
        assert type(self.client.profile) is dict
        assert self.client.all_routes_are_profiled is True
        # there should be a entry per cluster
        assert len(self.client.profile) == len(self.client.get_clusters())

        for cluster in self.client.get_clusters():
            assert type(self.client) is ValidationClient

            for route in cluster.get_routes():
                assert type(route.cluster) == ValidatedCluster
                assert route.compliance_status is True
                assert type(route.status_validation) is dict

    def test_compliance_manually(self):

        self.skip_mock_server()

        for route in self._get_random_routes():

            status_disabled = route.status_disabled

            assert route.status_disabled is status_disabled
            assert route.compliance_status is True
            assert self.client.holistic_compliance_status is True

            route.change_status(status_disabled=not status_disabled)

            assert route.status_disabled is not status_disabled
            assert route.compliance_status is False
            assert self.client.holistic_compliance_status is False

            route.change_status(status_disabled=status_disabled)

            assert route.status_disabled is status_disabled
            assert route.compliance_status is True
            assert self.client.holistic_compliance_status is True

    def test_compliance_with_enforce(self):

        self.skip_mock_server()

        assert self.client.holistic_compliance_status is True

        for route in self._get_random_routes():
            assert route.compliance_status is True
            route.change_status(status_disabled=not route.status_disabled)
            assert route.compliance_status is False

        assert self.client.holistic_compliance_status is False

        self.client.enforce()

        assert self.client.holistic_compliance_status is True

    def _get_random_routes(self):

        random_routes = list()
        for cluster in self.client.get_clusters():
            routes = cluster.get_routes()
            if len(routes) > 1:
                random_index = random.randrange(0, len(routes) - 1) if len(routes) > 1 else 0
                random_routes.append(routes[random_index])

        if len(random_routes) == 0:
            raise ValueError('no routes were found')

        return random_routes
