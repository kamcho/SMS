from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Custom filter to look up a value in a dictionary by key.
    Usage: {{ configs_by_grade|lookup:grade }}
    """
    if dictionary is None:
        return []
    return dictionary.get(key, [])
