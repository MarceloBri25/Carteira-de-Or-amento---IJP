from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from calendar import month_name as calendar_month_name

register = template.Library()

@register.filter
def br_format(value):
    try:
        value = float(value)
        # Format with 2 decimal places
        main, dec = f"{value:.2f}".split('.')
        # Add thousand separators
        main = intcomma(main).replace(',', '.')
        return f"{main},{dec}"
    except (ValueError, TypeError):
        return value

@register.filter
def get_range(value):
    return range(1, value + 1)

@register.filter
def month_name(month_number):
    try:
        return calendar_month_name[int(month_number)]
    except (ValueError, IndexError):
        return ''

@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return None

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return None

@register.filter
def as_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
