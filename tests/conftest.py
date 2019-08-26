# _*_ coding: utf-8 _*_
from pytest_docker_fixtures import images


images.configure(
    "elasticsearch",
    "docker.elastic.co/elasticsearch/elasticsearch",
    "7.2.0",
    env={
        "xpack.security.enabled": None,  # unset
        "discovery.type": "single-node",
        "http.host": "0.0.0.0",
        "transport.host": "127.0.0.1",
    },
)


pytest_plugins = [
    "aiohttp.pytest_plugin",
    "pytest_docker_fixtures",
    "tests.fixtures",
]
