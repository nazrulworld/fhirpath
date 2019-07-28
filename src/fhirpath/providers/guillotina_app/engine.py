# _*_ coding: utf-8 _*_
import logging

from fhirpath.engine import Connection
from fhirpath.engine import Engine
from guillotina.utils import get_current_container
from guillotina.component import get_adapter
from guillotina_elasticsearch.interfaces import IIndexManager


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.guillotina.engine")


class EsConnection(Connection):
    """Elasticsearch Connection"""

    async def server_info(self):
        info = {}
        try:
            conn = self.raw_connection()
            info = await conn.info()
        except Exception:
            logger.warning(
                "Could not retrieve Elasticsearch Server info, "
                "there is problem with connection."
            )
        return info


class EsEngine(Engine):
    """Elasticsearch Engine"""

    async def get_index_name(self, container=None):
        """ """
        if container is None:
            container = get_current_container()

        index_manager = get_adapter(container, IIndexManager)

        return await index_manager.get_index_name()
