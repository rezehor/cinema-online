import re


def validate_name(name: str):
    if re.search(r'^[A-Za-z]*$', name) is None:
        raise ValueError(f'{name} contains non-english letters')