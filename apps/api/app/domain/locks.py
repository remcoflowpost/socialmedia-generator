"""Rechtencontrole op post-wijzigingen. Draait server-side; de UI verbergt alleen."""

from app.schema import BrandKitData, PostDocument, TemplateDefinition


class LockViolation(ValueError):
    pass


def validate_document(
    document: PostDocument, template: TemplateDefinition, brand: BrandKitData, role: str
) -> None:
    fields = {field.key: field for field in template.fields}
    for key, value in document.content.items():
        field = fields.get(key)
        if not field:
            raise LockViolation(f"Onbekend veld: {key}")
        if field.max_length and isinstance(value, str) and len(value) > field.max_length:
            raise LockViolation(f'"{field.label}" mag maximaal {field.max_length} tekens zijn.')
        if field.type in ("select",) and value and field.options and value not in field.options:
            raise LockViolation(f'Ongeldige keuze voor "{field.label}".')

    layers = {layer.id: layer for layer in template.layers}
    for layer_id in document.overrides:
        layer = layers.get(layer_id)
        if not layer:
            raise LockViolation(f"Onbekende laag: {layer_id}")
        if role == "admin":
            continue
        if not layer.editable:
            raise LockViolation(f'Laag "{layer_id}" is niet aanpasbaar.')
        if layer.type == "logo" and "logo" in brand.locks:
            raise LockViolation("Het logo is vergrendeld in de brand kit.")
