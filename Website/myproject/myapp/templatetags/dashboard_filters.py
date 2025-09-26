"""
Dashboard-specific template filters for the admin interface.
These filters support the dashboard's data display functionality.
"""
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Get a value from a dictionary by key.
    Used primarily in the payment management dashboard for tier pricing display.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''
