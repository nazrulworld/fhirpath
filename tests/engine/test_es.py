# _*_ coding: utf-8 _*_
from fhirpath.engine.base import EngineResultBody

from .dataset import DATASET_1


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_hit_extraction(engine):
    """ """
    result = EngineResultBody()
    selects = ["organization_resource.name", "organization_resource.address"]
    engine.extract_hits(selects, [DATASET_1], result)

    assert result[0][0] == "Burgers University Medical Center"
