# _*_ coding: utf-8 _*_
from zope.interface import Interface


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class IURL(Interface):
    """ """

class IConnectionFactory(Interface):
    """ "mssql+pyodbc://scott:tiger@ms_2008
    mysql://scott:tiger@localhost/test
    "mysql+pymysql://scott:tiger@localhost/"
  "test?plugin=myplugin&my_argument_one=foo&my_argument_two=bar",
  from sqlalchemy.engine.url import make_url
  https://github.com/sqlalchemy/sqlalchemy/blob/master/lib/sqlalchemy/engine/url.py""""
