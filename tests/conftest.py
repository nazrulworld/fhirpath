# _*_ coding: utf-8 _*_
from pytest_docker_fixtures import images


images.configure(
    "elasticsearch",
    "docker.elastic.co/elasticsearch/elasticsearch",
    "7.3.1",
    env={
        "xpack.security.enabled": None,  # unset
        "discovery.type": "single-node",
        "http.host": "0.0.0.0",
        "transport.host": "127.0.0.1",
    },
)

images.configure(
    "postgresql",
    "postgres",
    "10.10",
    env={
        "POSTGRES_USER": "fhir_dm",
        "POSTGRES_PASSWORD": "Secret#",
        "POSTGRES_DB": "fhir_db"
    },
)

pytest_plugins = [
    "aiohttp.pytest_plugin",
    "pytest_docker_fixtures",
    "tests.fixtures",
]
