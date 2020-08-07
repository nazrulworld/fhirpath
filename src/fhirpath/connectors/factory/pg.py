# _*_ coding: utf-8 _*_
import logging
from contextlib import contextmanager

from psycopg2.pool import SimpleConnectionPool

from fhirpath.enums import EngineQueryType

from ..connection import Connection
from ..interfaces import IURL
from ..url import _parse_rfc1738_args
from . import ConnectionFactory

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.connectors.factory.pg")


class PostgresConnection(Connection):
    """PostgreSQL Connection"""

    def __init__(self, pool):
        """ """
        Connection.__init__(self, None)
        self._pool = pool

    @property
    def raw_connection(self):
        """ """
        return self._get_conn()

    @contextmanager
    def _get_conn(self):
        """ """
        try:
            connection = self._pool.getconn()
            yield connection
        finally:
            self._pool.putconn(connection)

    @contextmanager
    def get_cursor(self, commit=False, cursor_factory=None):
        """ """
        with self._get_conn() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                if commit:
                    conn.commit()
            finally:
                cursor.close()

    @classmethod
    def from_url(cls, url: str):
        """ """
        url = _parse_rfc1738_args(url)
        self = cls(PostgresConnectionFactory.create_pool(url))
        return self

    def server_info(self):
        """ """
        try:
            with self.raw_connection as conn:
                info = conn.info
        except Exception:
            logger.warning(
                "Could not retrieve PostgreSQL Server info, "
                "there is problem with connection."
            )
            info = None
        return info

    def finalize_search_params(self, compiled_query, query_type=EngineQueryType.DML):
        """ """
        pass

    def fetch(self, index, compiled_query):
        """ """
        pass

    def count(self, index, compiled_query):
        """ """
        pass

    def _evaluate_result(self, result):
        """ """
        pass


class PostgresConnectionFactory(ConnectionFactory):
    """ """

    def __init__(self, url, klass=None):
        """
        :param url: URL instance.

        :param klass: Connection Class or full path of string class.
        """
        self.url = IURL(url)

    @staticmethod
    def create_pool(url):
        """ """
        url = IURL(url)
        pool = SimpleConnectionPool(
            1,
            20,
            database=url.database,
            user=url.username,
            password=url.password,
            host=url.host or "127.0.0.1",
            port=url.port or 5432,
        )
        return pool

    def __call__(self):
        """ """
        pool = PostgresConnectionFactory.create_pool(self.url)
        return PostgresConnection(pool)


def create(url, klass=None):
    """
    :param url: instance of URL or list of URL.

    :param conn_class: The Connection class.
    """
    factory = PostgresConnectionFactory(url, klass)
    return factory()
