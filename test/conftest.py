pytest_plugins = ['helpers_namespace']

import asyncio
import json
import os
import random
from collections import namedtuple
from packaging import version

import docker
import pytest
import respx
from py_balancer_manager import BalancerManager, ValidatedBalancerManager

import docker_helpers


_dir = os.path.dirname(os.path.abspath(__file__))


def pytest_addoption(parser):
    parser.addoption('--httpd-version', default='2.4.41')


@pytest.fixture(scope='session')
def httpd_version(request):
    v = request.config.getoption('httpd_version')
    return version.parse(v)


@pytest.fixture(scope='session')
def httpd_instance(httpd_version):
    _dir = os.path.dirname(os.path.abspath(__file__))
    tag = f'py_balancer_manager-pytest_httpd_1:{httpd_version}'

    docker.from_env().images.build(
        path=f'{_dir}/httpd',
        dockerfile='Dockerfile',
        tag=tag,
        buildargs={
            'FROM': f'httpd:{httpd_version}'
        }
    )

    container_info = docker_helpers.run(tag, ports=['80/tcp'])
    yield container_info
    container_info.container.stop()


@pytest.fixture
def client_url(httpd_instance):
    return f"http://{httpd_instance.address}:{httpd_instance.ports['80/tcp']}/balancer-manager"


@pytest.fixture
@pytest.mark.asyncio
async def balancer_manager(client_url):
    balancer_manager = BalancerManager(client={
        'url': client_url,
        'username': 'admin',
        'password': 'password',
        'timeout': .25
    })
    return await balancer_manager.update()


@pytest.fixture
@pytest.mark.asyncio
async def validated_balancer_manager(client_url):
    with open(f'{_dir}/data/test_validation_profile.json') as fh:
        profile = json.load(fh)
    balancer_manager = ValidatedBalancerManager(client={
        'url': client_url,
        'username': 'admin',
        'password': 'password',
        'timeout': .25
    }, profile=profile)
    return await balancer_manager.update()


@pytest.fixture
@pytest.mark.asyncio
async def mocked_balancer_manager():
    balancer_manager = BalancerManager(client={
        'url': 'http://respx/balancer-manager'
    })

    await update_mocked_balancer_manager(balancer_manager, 'balancer-manager-mock-1.html')

    return balancer_manager


@pytest.helpers.register
async def update_mocked_balancer_manager(balancer_manager, filename):
    with open(f'{_dir}/data/{filename}', 'r') as fh:
        html_payload = fh.read()

    with respx.mock:
        respx.get('http://respx/balancer-manager', content=html_payload)
        await balancer_manager.update()
