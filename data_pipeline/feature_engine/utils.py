# utils.py
import json
import logging

def parse_json(element):
    """
    Parses a JSON string into a Python dictionary.
    Returns None if parsing fails.
    """
    try:
        return json.loads(element)
    except json.JSONDecodeError:
        logging.warning(f"Failed to decode JSON: {element}")
        return None
