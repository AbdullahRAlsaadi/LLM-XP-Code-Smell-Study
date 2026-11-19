def canonical_query_string(self, http_request):
    # Note that we just do not return an empty string for
    # POST request. Query strings in url are included in canonical
    # query string.
    l = []
    for param in sorted(http_request.params):
        value = boto.utils.get_utf8_value(http_request.params[param])
        l.append('%s=%s' % (urllib.parse.quote(param, safe='-_.~'),
                            urllib.parse.quote(value, safe='-_.~')))
    return '&'.join(l)
