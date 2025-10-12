def tag(label: str, updated: str | None = None):
    return f"[{label} • {updated}]" if updated else f"[{label}]"
