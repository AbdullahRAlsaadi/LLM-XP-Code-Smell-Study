def _handle(self, environ):
    path = environ['bottle.raw_path'] = environ['PATH_INFO']
    if py3k:
        environ['PATH_INFO'] = path.encode('latin1').decode('utf8', 'ignore')

    def _inner_handle():
        # Maybe pass variables as locals for better performance? 
        try:
            route, args = self.router.match(environ)
            environ['route.handle'] = route
            environ['bottle.route'] = route
            environ['route.url_args'] = args
            return route.call(**args)
        except HTTPResponse:
            return _e()
        except RouteReset:
            route.reset()
            return _inner_handle()
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception:
            if not self.catchall: raise
            stacktrace = format_exc()
            environ['wsgi.errors'].write(stacktrace)
            return HTTPError(500, "Internal Server Error", _e(), stacktrace)

    try:
        out = None
        environ['bottle.app'] = self
        request.bind(environ)
        response.bind()
        self.trigger_hook('before_request')
        out = _inner_handle()
        return out;
    finally:
        if isinstance(out, HTTPResponse):
            out.apply(response)
        self.trigger_hook('after_request')
