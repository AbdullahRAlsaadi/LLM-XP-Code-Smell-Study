class Consumer(object):
    Strategies = dict

    #: set when consumer is shutting down.
    in_shutdown = False

    #: Optional callback called the first time the worker
    #: is ready to receive tasks.
    init_callback = None

    #: The current worker pool instance.
    pool = None

    #: A timer used for high-priority internal tasks, such
    #: as sending heartbeats.
    timer = None

    restart_count = -1  # first start is the same as a restart

    class Blueprint(bootsteps.Blueprint):
        name = 'Consumer'
        default_steps = [
            'celery.worker.consumer:Connection',
            'celery.worker.consumer:Mingle',
            'celery.worker.consumer:Events',
            'celery.worker.consumer:Gossip',
            'celery.worker.consumer:Heart',
            'celery.worker.consumer:Control',
            'celery.worker.consumer:Tasks',
            'celery.worker.consumer:Evloop',
            'celery.worker.consumer:Agent',
        ]

        def shutdown(self, parent):
            self.send_all(parent, 'shutdown')

    def __init__(self, on_task_request,
                 init_callback=noop, hostname=None,
                 pool=None, app=None,
                 timer=None, controller=None, hub=None, amqheartbeat=None,
                 worker_options=None, disable_rate_limits=False,
                 initial_prefetch_count=2, prefetch_multiplier=1, **kwargs):
        self.app = app
        self.controller = controller
        self.init_callback = init_callback
        self.hostname = hostname or socket.gethostname()
        self.pid = os.getpid()
        self.pool = pool
        self.timer = timer
        self.strategies = self.Strategies()
        self.conninfo = self.app.connection()
        self.connection_errors = self.conninfo.connection_errors
        self.channel_errors = self.conninfo.channel_errors
        self._restart_state = restart_state(maxR=5, maxT=1)

        self._does_info = logger.isEnabledFor(logging.INFO)
        self._limit_order = 0
        self.on_task_request = on_task_request
        self.on_task_message = set()
        self.amqheartbeat_rate = self.app.conf.broker_heartbeat_checkrate
        self.disable_rate_limits = disable_rate_limits
        self.initial_prefetch_count = initial_prefetch_count
        self.prefetch_multiplier = prefetch_multiplier

        # this contains a tokenbucket for each task type by name, used for
        # rate limits, or None if rate limits are disabled for that task.
        self.task_buckets = defaultdict(lambda: None)
        self.reset_rate_limits()

        self.hub = hub
        if self.hub:
            self.amqheartbeat = amqheartbeat
            if self.amqheartbeat is None:
                self.amqheartbeat = self.app.conf.broker_heartbeat
        else:
            self.amqheartbeat = 0

        if not hasattr(self, 'loop'):
            self.loop = loops.asynloop if hub else loops.synloop

        if _detect_environment() == 'gevent':
            # there's a gevent bug that causes timeouts to not be reset,
            # so if the connection timeout is exceeded once, it can NEVER
            # connect again.
            self.app.conf.broker_connection_timeout = None

        self.steps = []
        self.blueprint = self.Blueprint(
            app=self.app, on_close=self.on_close,
        )
        self.blueprint.apply(self, **dict(worker_options or {}, **kwargs))

    def bucket_for_task(self, type):
        limit = rate(getattr(type, 'rate_limit', None))
        return TokenBucket(limit, capacity=1) if limit else None

    def reset_rate_limits(self):
        self.task_buckets.update(
            (n, self.bucket_for_task(t)) for n, t in items(self.app.tasks)
        )

    def _update_prefetch_count(self, index=0):
        """Update prefetch count after pool/shrink grow operations.

        Index must be the change in number of processes as a positive
        (increasing) or negative (decreasing) number.

        .. note::

            Currently pool grow operations will end up with an offset
            of +1 if the initial size of the pool was 0 (e.g.
            ``--autoscale=1,0``).

        """
        num_processes = self.pool.num_processes
        if not self.initial_prefetch_count or not num_processes:
            return  # prefetch disabled
        self.initial_prefetch_count = (
            self.pool.num_processes * self.prefetch_multiplier
        )
        return self._update_qos_eventually(index)

    def _update_qos_eventually(self, index):
        return (self.qos.decrement_eventually if index < 0
                else self.qos.increment_eventually)(
            abs(index) * self.prefetch_multiplier)

    def _limit_move_to_pool(self, request):
        task_reserved(request)
        self.on_task_request(request)

    def _limit_task(self, request, bucket, tokens):
        if not bucket.can_consume(tokens):
            hold = bucket.expected_time(tokens)
            pri = self._limit_order = (self._limit_order + 1) % 10
            self.timer.call_after(
                hold, self._limit_move_to_pool, (request,),
                priority=pri,
            )
        else:
            task_reserved(request)
            self.on_task_request(request)

    def start(self):
        blueprint = self.blueprint
        while blueprint.state != CLOSE:
            self.restart_count += 1
            maybe_shutdown()
            try:
                blueprint.start(self)
            except self.connection_errors as exc:
                # If we're not retrying connections, no need to catch
                # connection errors
                if not self.app.conf.broker_connection_retry:
                    raise
                if isinstance(exc, OSError) and exc.errno == errno.EMFILE:
                    raise  # Too many open files
                maybe_shutdown()
                try:
                    self._restart_state.step()
                except RestartFreqExceeded as exc:
                    crit('Frequent restarts detected: %r', exc, exc_info=1)
                    sleep(1)
                if blueprint.state != CLOSE and self.connection:
                    warn(CONNECTION_RETRY, exc_info=True)
                    try:
                        self.connection.collect()
                    except Exception:
                        pass
                    self.on_close()
                    blueprint.restart(self)

    def register_with_event_loop(self, hub):
        self.blueprint.send_all(
            self, 'register_with_event_loop', args=(hub,),
            description='Hub.register',
        )

    def shutdown(self):
        self.in_shutdown = True
        self.blueprint.shutdown(self)

    def stop(self):
        self.blueprint.stop(self)

    def on_ready(self):
        callback, self.init_callback = self.init_callback, None
        if callback:
            callback(self)

    def loop_args(self):
        return (self, self.connection, self.task_consumer,
                self.blueprint, self.hub, self.qos, self.amqheartbeat,
                self.app.clock, self.amqheartbeat_rate)

    def on_decode_error(self, message, exc):
        """Callback called if an error occurs while decoding
        a message received.

        Simply logs the error and acknowledges the message so it
        doesn't enter a loop.

        :param message: The message with errors.
        :param exc: The original exception instance.

        """
        crit(MESSAGE_DECODE_ERROR,
             exc, message.content_type, message.content_encoding,
             safe_repr(message.headers), dump_body(message, message.body),
             exc_info=1)
        message.ack()

    def on_close(self):
        # Clear internal queues to get rid of old messages.
        # They can't be acked anyway, as a delivery tag is specific
        # to the current channel.
        if self.controller and self.controller.semaphore:
            self.controller.semaphore.clear()
        if self.timer:
            self.timer.clear()
        reserved_requests.clear()
        if self.pool and self.pool.flush:
            self.pool.flush()

    def connect(self):
        """Establish the broker connection.

        Will retry establishing the connection if the
        :setting:`broker_connection_retry` setting is enabled

        """
        conn = self.app.connection(heartbeat=self.amqheartbeat)

        # Callback called for each retry while the connection
        # can't be established.
        def _error_handler(exc, interval, next_step=CONNECTION_RETRY_STEP):
            if getattr(conn, 'alt', None) and interval == 0:
                next_step = CONNECTION_FAILOVER
            error(CONNECTION_ERROR, conn.as_uri(), exc,
                  next_step.format(when=humanize_seconds(interval, 'in', ' ')))

        # remember that the connection is lazy, it won't establish
        # until needed.
        if not self.app.conf.broker_connection_retry:
            # retry disabled, just call connect directly.
            conn.connect()
            return conn

        conn = conn.ensure_connection(
            _error_handler, self.app.conf.broker_connection_max_retries,
            callback=maybe_shutdown,
        )
        if self.hub:
            conn.transport.register_with_event_loop(conn.connection, self.hub)
        return conn

    def _flush_events(self):
        if self.event_dispatcher:
            self.event_dispatcher.flush()

    def on_send_event_buffered(self):
        if self.hub:
            self.hub._ready.add(self._flush_events)

    def add_task_queue(self, queue, exchange=None, exchange_type=None,
                       routing_key=None, **options):
        cset = self.task_consumer
        queues = self.app.amqp.queues
        # Must use in' here, as __missing__ will automatically
        # create queues when :setting:`task_create_missing_queues` is enabled.
        # (Issue #1079)
        if queue in queues:
            q = queues[queue]
        else:
            exchange = queue if exchange is None else exchange
            exchange_type = ('direct' if exchange_type is None
                             else exchange_type)
            q = queues.select_add(queue,
                                  exchange=exchange,
                                  exchange_type=exchange_type,
                                  routing_key=routing_key, **options)
        if not cset.consuming_from(queue):
            cset.add_queue(q)
            cset.consume()
            info('Started consuming from %s', queue)

    def cancel_task_queue(self, queue):
        info('Cancelling queue %s', queue)
        self.app.amqp.queues.deselect(queue)
        self.task_consumer.cancel_by_queue(queue)

    def apply_eta_task(self, task):
        """Method called by the timer to apply a task with an
        ETA/countdown."""
        task_reserved(task)
        self.on_task_request(task)
        self.qos.decrement_eventually()

    def _message_report(self, body, message):
        return MESSAGE_REPORT.format(dump_body(message, body),
                                     safe_repr(message.content_type),
                                     safe_repr(message.content_encoding),
                                     safe_repr(message.delivery_info),
                                     safe_repr(message.headers))

    def on_unknown_message(self, body, message):
        warn(UNKNOWN_FORMAT, self._message_report(body, message))
        message.reject_log_error(logger, self.connection_errors)

    def on_unknown_task(self, body, message, exc):
        error(UNKNOWN_TASK_ERROR, exc, dump_body(message, body), exc_info=True)
        message.reject_log_error(logger, self.connection_errors)

    def on_invalid_task(self, body, message, exc):
        error(INVALID_TASK_ERROR, exc, dump_body(message, body), exc_info=True)
        message.reject_log_error(logger, self.connection_errors)

    def update_strategies(self):
        loader = self.app.loader
        for name, task in items(self.app.tasks):
            self.strategies[name] = task.start_strategy(self.app, self)
            task.__trace__ = build_tracer(name, task, loader, self.hostname,
                                          app=self.app)

    def create_task_handler(self):
        strategies = self.strategies
        on_unknown_message = self.on_unknown_message
        on_unknown_task = self.on_unknown_task
        on_invalid_task = self.on_invalid_task
        callbacks = self.on_task_message

        def on_task_received(message):
            # payload will only be set for v1 protocol, since v2
            # will defer deserializing the message body to the pool.
            payload = None
            try:
                type_ = message.headers['task']                # protocol v2
            except TypeError:
                return on_unknown_message(None, message)
            except KeyError:
                payload = message.payload
                try:
                    type_, payload = payload['task'], payload  # protocol v1
                except (TypeError, KeyError):
                    return on_unknown_message(payload, message)
            try:
                strategy = strategies[type_]
            except KeyError as exc:
                return on_unknown_task(payload, message, exc)
            else:
                try:
                    strategy(
                        message, payload, message.ack_log_error,
                        message.reject_log_error, callbacks,
                    )
                except InvalidTaskError as exc:
                    return on_invalid_task(payload, message, exc)
                except MemoryError:
                    raise
                except Exception as exc:
                    # XXX handle as internal error?
                    return on_invalid_task(payload, message, exc)

        return on_task_received

    def __repr__(self):
        return '<Consumer: {self.hostname} ({state})>'.format(
            self=self, state=self.blueprint.human_state(),
        )
