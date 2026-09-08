from sqlalchemy import inspect

def serialize(obj):
    if obj is None: return None
    data = {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}
    for key in ("market", "product", "script", "template", "mix_project", "asset", "ad_plan"):
        rel = getattr(obj, key, None)
        if rel is not None: data[key] = {"id": rel.id, "name": getattr(rel, "name", getattr(rel, "title", getattr(rel, "plan_name", None)))}
    return data
