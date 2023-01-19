import copy

from django.core import management
from django.core.management.base import BaseCommand
from ruamel.yaml import YAML


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        management.call_command(
            "spectacular",
            "--file",
            "../docs/openapi_full.yaml",
            "--color",
            "--validate",
        )

        yaml = YAML()  # default, if not specfied, is 'rt' (round-trip)
        with open("../docs/openapi_full.yaml") as fp:
            data_public = yaml.load(fp)
        data_private = copy.deepcopy(data_public)

        lst = list(data_public["paths"].keys())
        for x in lst:
            if x.startswith("/api/"):
                print("deleting", x, "from private schema")
                del data_private["paths"][x]
            else:
                print("deleting", x, "from public schema")
                del data_public["paths"][x]
        with open("../docs/openapi.yaml", "w") as fp:
            yaml.dump(data_public, fp)
        with open("../docs/openapi_private.yaml", "w") as fp:
            yaml.dump(data_private, fp)
            yaml.dump(data_private, fp)
            yaml.dump(data_private, fp)
            yaml.dump(data_private, fp)
            yaml.dump(data_private, fp)
