# _*_ coding: utf-8 _*_
from fhirpath.engine.base import EngineResultBody

from .dataset import DATASET_1


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_hit_extraction(engine):
    """ """
    result = EngineResultBody()
    selects = ["organization_resource.name", "organization_resource.address"]
    engine.extract_hits(selects, hits=[DATASET_1], container=result)

    assert result[0][0] == "Burgers University Medical Center"


def test_hit_extraction_with_index(engine):
    """ """
    result = EngineResultBody()
    selects = [
        "organization_resource.name.count()",
        "organization_resource.telecom[0]",
        "organization_resource.address.Skip(0).Take(0).line[0]",
    ]
    engine.extract_hits(selects, hits=[DATASET_1], container=result)

    name_length = len("Burgers University Medical Center")
    assert result[0][0] == name_length
    assert result[0][1] == DATASET_1["_source"]["organization_resource"]["telecom"][0]
    assert (
        result[0][2]
        == DATASET_1["_source"]["organization_resource"]["address"][1]["line"][0]
    )

    # Failed/Missing test
    result = EngineResultBody()
    selects = [
        "organization_resource.name.count()",
        "organization_resource.address.Skip(0).Take(1).line[0]",
    ]
    engine.extract_hits(selects, [DATASET_1], result)
    assert result[0][1] is None
