# _*_ coding: utf-8 _*_
from . import ConnectionFactory


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class ElasticsearchConnectionFactory(ConnectionFactory):
    """ """

    def prepare_params(self):
        """ """
        host_info = {"host": self.url.host, "port": self.url.port or 9200}
        if self.username:
            host_info["http_auth"] = "{0}:{1}".format(
                self.url.username, self.url.password or ""
            )
        if "use_ssl" in self.url.query:
            host_info["use_ssl"] = self.url.query.get("use_ssl").lower() in (
                "true",
                "t",
                "yes",
                "y",
                "1",
            )
        if "url_prefix" in self.url.query:
            host_info["url_prefix"] = self.url.query.get("url_prefix")

        return {"hosts": [host_info]}

    def __call__(self):
        """ """
        params = self.prepare_params()

        return self.klass(**params)
