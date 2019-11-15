# _*_ coding: utf-8 _*_

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


async def test_fhirbase_pg(fhirbase_pg):
    host, port = fhirbase_pg
    assert 1 == 1
