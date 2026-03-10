from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Safe dict.get for templates: {{ mydict|dict_get:var }}."""
    if isinstance(d, dict):
        return d.get(key, {})
    return {}
