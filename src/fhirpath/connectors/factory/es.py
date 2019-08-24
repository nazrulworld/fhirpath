# _*_ coding: utf-8 _*_
from . import ConnectionFactory


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class ElasticsearchConnectionFactory(ConnectionFactory):
    """ """

    def prepare_params(self):
        """ """
        if not isinstance(self.url, (list, tuple)):
            urls = [self.url]
        else:
            urls = self.url

        host_info = list()

        for url in urls:
            item = {"host": self.url.host, "port": self.url.port or 9200}
            if self.url.username:
                item["http_auth"] = "{0}:{1}".format(
                    self.url.username, self.url.password or ""
                )
            if "use_ssl" in self.url.query:
                item["use_ssl"] = self.url.query.get("use_ssl").lower() in (
                    "true",
                    "t",
                    "yes",
                    "y",
                    "1",
                )
            if "url_prefix" in self.url.query:
                item["url_prefix"] = self.url.query.get("url_prefix")
            host_info.append(item)

        return {"hosts": host_info}

    def __call__(self):
        """ """
        params = self.prepare_params()
        return self.klass(**params)


def create(url, conn_class=None):
    """
    :param url: instance of URL or list of URL.

    :param conn_class: The Connection class.
    """
    if conn_class is None:
        conn_class = "elasticsearch.Elasticsearch"

    factory = ElasticsearchConnectionFactory(url, klass=conn_class)
    return factory()
