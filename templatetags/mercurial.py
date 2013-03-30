# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape

register = template.Library()

@register.filter
@stringfilter
def summarise(value):
    return value.split("\n")[0]

@register.filter(needs_autoescape = True)
@stringfilter
def bugzilla(value, autoescape = None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    result = ""
    bugs = re.finditer('\\b(?:BUG )?(\\d{4,7})\\b', value, re.IGNORECASE)
    last = 0
    for bug in bugs:
        result = "%s%s<a href=\"https://bugzilla.mozilla.org/show_bug.cgi?id=%s\">%s</a>" % (result, esc(value[last:bug.start()]), bug.group(1), esc(bug.group()))
        last = bug.end()

    result = result + esc(value[last:])

    return mark_safe(result)
