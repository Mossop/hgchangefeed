from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def summarise(value):
    return value.split("\n")[0]
