# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core.cache import cache
from django.views.decorators.http import etag

TYPEMAP = {
    "added": "A",
    "removed": "R",
    "modified": "M",
}

def tag_cached(func, tag, *args):
    def tag_func(*args):
        return tag

    def check_cache(*args):
        response = cache.get(tag)
        if response:
            return response

        response = func(*args)
        if response.status_code == 200:
            cache.set(tag, response, 86400)
        return response

    decorator = etag(tag_func)
    view_func = decorator(check_cache)
    return view_func(*args)
