def validate_blend_names(name_a: str, name_b: str, blend_name: str) -> str | None:
    name_a = (name_a or "").strip()
    name_b = (name_b or "").strip()
    blend_name = (blend_name or "").strip()
    if not blend_name:
        return "Please enter a name for the blend."
    if name_a.lower() == name_b.lower():
        return "Please choose two different flowers to blend."
    if blend_name.lower() in {name_a.lower(), name_b.lower()}:
        return "Blend name must be different from the source flowers."
    return None
