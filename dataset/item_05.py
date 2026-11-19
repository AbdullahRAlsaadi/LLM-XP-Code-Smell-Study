def _mexe(self, request, sender=None, override_num_retries=None,
          retry_handler=None):
    """
    mexe - Multi-execute inside a loop, retrying multiple times to handle
           transient Internet errors by simply trying again.
           Also handles redirects.

    This code was inspired by the S3Utils classes posted to the boto-users
    Google group by Larry Bates.  Thanks!

    """
    boto.log.debug('Method: %s' % request.method)
    boto.log.debug('Path: %s' % request.path)
    boto.log.debug('Data: %s' % request.body)
    boto.log.debug('Headers: %s' % request.headers)
    boto.log.debug('Host: %s' % request.host)
    boto.log.debug('Port: %s' % request.port)
    boto.log.debug('Params: %s' % request.params)
    response = None
    body = None
    ex = None
    if override_num_retries is None:
        num_retries = config.getint('Boto', 'num_retries', self.num_retries)
    else:
        num_retries = override_num_retries
    i = 0
    connection = self.get_http_connection(request.host, request.port,
                                          self.is_secure)

    # Convert body to bytes if needed
    if not isinstance(request.body, bytes) and hasattr(request.body,
                                                       'encode'):
        request.body = request.body.encode('utf-8')

    while i <= num_retries:
        # Use binary exponential backoff to desynchronize client requests.
        next_sleep = min(random.random() * (2 ** i),
                         boto.config.get('Boto', 'max_retry_delay', 60))
        try:
            # we now re-sign each request before it is retried
            boto.log.debug('Token: %s' % self.provider.security_token)
            request.authorize(connection=self)
            # Only force header for non-s3 connections, because s3 uses
            # an older signing method + bucket resource URLs that include
            # the port info. All others should be now be up to date and
            # not include the port.
            if 's3' not in self._required_auth_capability():
                if not getattr(self, 'anon', False):
                    if not request.headers.get('Host'):
                        self.set_host_header(request)
            boto.log.debug('Final headers: %s' % request.headers)
            request.start_time = datetime.now()
            if callable(sender):
                response = sender(connection, request.method, request.path,
                                  request.body, request.headers)
            else:
                connection.request(request.method, request.path,
                                   request.body, request.headers)
                response = connection.getresponse()
            boto.log.debug('Response headers: %s' % response.getheaders())
            location = response.getheader('location')
            # -- gross hack --
            # http_client gets confused with chunked responses to HEAD requests
            # so I have to fake it out
            if request.method == 'HEAD' and getattr(response,
                                                    'chunked', False):
                response.chunked = 0
            if callable(retry_handler):
                status = retry_handler(response, i, next_sleep)
                if status:
                    msg, i, next_sleep = status
                    if msg:
                        boto.log.debug(msg)
                    time.sleep(next_sleep)
                    continue
            if response.status in [500, 502, 503, 504]:
                msg = 'Received %d response.  ' % response.status
                msg += 'Retrying in %3.1f seconds' % next_sleep
                boto.log.debug(msg)
                body = response.read()
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
            elif response.status < 300 or response.status >= 400 or \
                    not location:
                # don't return connection to the pool if response contains
                # Connection:close header, because the connection has been
                # closed and default reconnect behavior may do something
                # different than new_http_connection. Also, it's probably
                # less efficient to try to reuse a closed connection.
                conn_header_value = response.getheader('connection')
                if conn_header_value == 'close':
                    connection.close()
                else:
                    self.put_http_connection(request.host, request.port,
                                             self.is_secure, connection)
                if self.request_hook is not None:
                    self.request_hook.handle_request_data(request, response)
                return response
            else:
                scheme, request.host, request.path, \
                    params, query, fragment = urlparse(location)
                if query:
                    request.path += '?' + query
                # urlparse can return both host and port in netloc, so if
                # that's the case we need to split them up properly
                if ':' in request.host:
                    request.host, request.port = request.host.split(':', 1)
                msg = 'Redirecting: %s' % scheme + '://'
                msg += request.host + request.path
                boto.log.debug(msg)
                connection = self.get_http_connection(request.host,
                                                      request.port,
                                                      scheme == 'https')
                response = None
                continue
        except PleaseRetryException as e:
            boto.log.debug('encountered a retry exception: %s' % e)
            connection = self.new_http_connection(request.host, request.port,
                                                  self.is_secure)
            response = e.response
            ex = e
        except self.http_exceptions as e:
            for unretryable in self.http_unretryable_exceptions:
                if isinstance(e, unretryable):
                    boto.log.debug(
                        'encountered unretryable %s exception, re-raising' %
                        e.__class__.__name__)
                    raise
            boto.log.debug('encountered %s exception, reconnecting' %
                           e.__class__.__name__)
            connection = self.new_http_connection(request.host, request.port,
                                                  self.is_secure)
            ex = e
        time.sleep(next_sleep)
        i += 1
    # If we made it here, it's because we have exhausted our retries
    # and stil haven't succeeded.  So, if we have a response object,
    # use it to raise an exception.
    # Otherwise, raise the exception that must have already happened.
    if self.request_hook is not None:
        self.request_hook.handle_request_data(request, response, error=True)
    if response:
        raise BotoServerError(response.status, response.reason, body)
    elif ex:
        raise ex
    else:
        msg = 'Please report this exception as a Boto Issue!'
        raise BotoClientError(msg)
