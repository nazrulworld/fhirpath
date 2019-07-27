# _*_ coding: utf-8 _*_
import logging

from fhirpath.engine import Connection
from fhirpath.engine import Engine


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
