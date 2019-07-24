# _*_ coding: utf-8 _*_
pytest_plugins = [
    "aiohttp.pytest_plugin",
    "pytest_docker_fixtures",
    "guillotina.tests.fixtures",
    "guillotina_elasticsearch.tests.fixtures",
    "tests.fixtures",
]
