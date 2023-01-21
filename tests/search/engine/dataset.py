from tests._utils import DOC_TYPE


DATASET_1 = {
    "_type": DOC_TYPE,
    "_source": {
        "organization_resource": {
            "address": [
                {
                    "city": "Den Burg;Jeg fik bøde på "
                    "5.000 kroner i et andet "
                    "orkester. først søge "
                    "permanent ophold i år 2032",
                    "country": "NLD",
                    "line": ["Galapagosweg 91"],
                    "postalCode": "9105 PZ",
                    "use": "work",
                },
                {
                    "city": "Den Burg",
                    "country": "NLD",
                    "line": ["PO Box 2311"],
                    "postalCode": "9100 AA",
                    "use": "work",
                },
            ],
            "name": "Burgers University Medical Center",
            "telecom": [{"system": "phone", "value": "022-655 2300", "use": "work"}],
        }
    },
}
