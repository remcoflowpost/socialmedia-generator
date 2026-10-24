from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Basis voor documenten die als JSON naar de frontend en render-service gaan.

    Python gebruikt snake_case, JSON camelCase.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )
