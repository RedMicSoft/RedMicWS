import uuid


def _uid() -> str:
    return uuid.uuid4().hex[:8]
