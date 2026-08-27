from __future__ import annotations

import importlib
from typing import Any


# Constructor paths are lazy so adding a Seed does not import all of its code.
COLLECTOR_FACTORIES = {
    "airport_friction": "public_data_alpha_engine.airport_friction:AirportFrictionCollector",
    "seoul_city": "public_data_alpha_engine.collectors.seoul_city:SeoulCityCollector",
}


def create_collector(collector_id: str, /, **kwargs: Any) -> Any:
    try:
        target = COLLECTOR_FACTORIES[collector_id]
    except KeyError as exc:
        choices = ", ".join(sorted(COLLECTOR_FACTORIES))
        raise ValueError(f"unknown collector {collector_id!r}; choose one of: {choices}") from exc
    module_name, object_name = target.split(":", 1)
    constructor = getattr(importlib.import_module(module_name), object_name)
    return constructor(**kwargs)
