# _*_ coding: utf-8 _*_
import pytest
from psycopg2.extras import DictCursor

from ._utils import IS_TRAVIS


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@pytest.mark.skipif(IS_TRAVIS, reason="ignore for travis environment")
def test_fhirbase_structure(init_fhirbase_pg, fhirbase_pg):
    connection = init_fhirbase_pg
    stmt = """SELECT table_name
    FROM information_schema.tables
    WHERE table_type='BASE TABLE'
    AND table_schema='public';"""

    with connection.get_cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(stmt)
        result = cursor.fetchall()
        total = cursor.rowcount
    assert total == 293
    assert len(result) == 293
