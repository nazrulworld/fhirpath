# _*_ coding: utf-8 _*_
"""Self-contained fixtures for the core engine tests (no search/Elasticsearch deps)."""

import json
import pathlib
from decimal import Decimal

from fhir.resources import get_fhir_model_class

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

STATIC_DIR = pathlib.Path(__file__).parent.parent / "_static" / "FHIR"


def load_json(name: str) -> dict:
    with open(str(STATIC_DIR / name), "r") as fp:
        return json.load(fp, parse_float=Decimal)


def load_model(name: str):
    data = load_json(name)
    return get_fhir_model_class(data["resourceType"]).model_validate(data)


__all__ = ["load_json", "load_model", "STATIC_DIR"]
