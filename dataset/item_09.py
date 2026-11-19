def put(self, local_path, remote_path, use_sudo, mirror_local_mode, mode,
    local_is_path, temp_dir):

    from fabric.api import sudo, hide
    pre = self.ftp.getcwd()
    pre = pre if pre else ''
    if local_is_path and self.isdir(remote_path):
        basename = os.path.basename(local_path)
        remote_path = posixpath.join(remote_path, basename)
    if output.running:
        print("[%s] put: %s -> %s" % (
            env.host_string,
            _format_local(local_path, local_is_path),
            posixpath.join(pre, remote_path)
        ))
    # When using sudo, "bounce" the file through a guaranteed-unique file
    # path in the default remote CWD (which, typically, the login user will
    # have write permissions on) in order to sudo(mv) it later.
    if use_sudo:
        target_path = remote_path
        hasher = hashlib.sha1()
        hasher.update(env.host_string)
        hasher.update(target_path)
        remote_path = posixpath.join(temp_dir, hasher.hexdigest())
    # Read, ensuring we handle file-like objects correct re: seek pointer
    putter = self.ftp.put
    if not local_is_path:
        old_pointer = local_path.tell()
        local_path.seek(0)
        putter = self.ftp.putfo
    rattrs = putter(local_path, remote_path)
    if not local_is_path:
        local_path.seek(old_pointer)
    # Handle modes if necessary
    if (local_is_path and mirror_local_mode) or (mode is not None):
        lmode = os.stat(local_path).st_mode if mirror_local_mode else mode
        # Cast to octal integer in case of string
        if isinstance(lmode, basestring):
            lmode = int(lmode, 8)
        lmode = lmode & int('07777', 8)
        rmode = rattrs.st_mode
        # Only bitshift if we actually got an rmode
        if rmode is not None:
            rmode = rmode & int('07777', 8)
        if lmode != rmode:
            if use_sudo:
                # Temporarily nuke 'cwd' so sudo() doesn't "cd" its mv
                # command. (The target path has already been cwd-ified
                # elsewhere.)
                with settings(hide('everything'), cwd=""):
                    sudo('chmod %o \"%s\"' % (lmode, remote_path))
            else:
                self.ftp.chmod(remote_path, lmode)
    if use_sudo:
        # Temporarily nuke 'cwd' so sudo() doesn't "cd" its mv command.
        # (The target path has already been cwd-ified elsewhere.)
        with settings(hide('everything'), cwd=""):
            sudo("mv \"%s\" \"%s\"" % (remote_path, target_path))
        # Revert to original remote_path for return value's sake
        remote_path = target_path
    return remote_path
