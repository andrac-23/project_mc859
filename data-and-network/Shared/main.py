import dataclasses
import json


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def make_string_filesystem_safe(s: str) -> str:
    return ''.join(c if c.isalnum() else '_' for c in s).rstrip('_').lower()
