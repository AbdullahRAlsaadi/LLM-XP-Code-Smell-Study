def _execute(task, host, my_env, args, kwargs, jobs, queue, multiprocessing):
    """
    Primary single-host work body of execute()
    """
    # Log to stdout
    if state.output.running and not hasattr(task, 'return_value'):
        print("[%s] Executing task '%s'" % (host, my_env['command']))
    # Create per-run env with connection settings
    local_env = to_dict(host)
    local_env.update(my_env)
    # Set a few more env flags for parallelism
    if queue is not None:
        local_env.update({'parallel': True, 'linewise': True})
    # Handle parallel execution
    if queue is not None: # Since queue is only set for parallel
        name = local_env['host_string']
        # Wrap in another callable that:
        # * expands the env it's given to ensure parallel, linewise, etc are
        #   all set correctly and explicitly. Such changes are naturally
        #   insulted from the parent process.
        # * nukes the connection cache to prevent shared-access problems
        # * knows how to send the tasks' return value back over a Queue
        # * captures exceptions raised by the task
        def inner(args, kwargs, queue, name, env):
            state.env.update(env)
            def submit(result):
                queue.put({'name': name, 'result': result})
            try:
                state.connections.clear()
                submit(task.run(*args, **kwargs))
            except BaseException as e:  # We really do want to capture everything
                # SystemExit implies use of abort(), which prints its own
                # traceback, host info etc -- so we don't want to double up
                # on that. For everything else, though, we need to make
                # clear what host encountered the exception that will
                # print.
                if e.__class__ is not SystemExit:
                    if not (isinstance(e, NetworkError) and
                            _is_network_error_ignored()):
                        sys.stderr.write("!!! Parallel execution exception under host %r:\n" % name)
                    submit(e)
                # Here, anything -- unexpected exceptions, or abort()
                # driven SystemExits -- will bubble up and terminate the
                # child process.
                if not (isinstance(e, NetworkError) and
                        _is_network_error_ignored()):
                    raise

        # Stuff into Process wrapper
        kwarg_dict = {
            'args': args,
            'kwargs': kwargs,
            'queue': queue,
            'name': name,
            'env': local_env,
        }
        p = multiprocessing.Process(target=inner, kwargs=kwarg_dict)
        # Name/id is host string
        p.name = name
        # Add to queue
        jobs.append(p)
    # Handle serial execution
    else:
        with settings(**local_env):
            return task.run(*args, **kwargs)
