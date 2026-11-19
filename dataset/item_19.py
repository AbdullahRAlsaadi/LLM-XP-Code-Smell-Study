class Metadata:
    # Metadata is stored as a sequence of tagged binary records.  Each
    # record will have some subset of add, encode, load, create, and
    # apply methods, i.e. _add_foo...

    # We do allow an "empty" object as a special case, i.e. no
    # records.  One can be created by trying to write Metadata(), and
    # for such an object, read() will return None.  This is used by
    # "bup save", for example, as a placeholder in cases where
    # from_path() fails.

    # NOTE: if any relevant fields are added or removed, be sure to
    # update same_file() below.

    ## Common records

    # Timestamps are (sec, ns), relative to 1970-01-01 00:00:00, ns
    # must be non-negative and < 10**9.

    def _add_common(self, path, st):
        assert(st.st_uid >= 0)
        assert(st.st_gid >= 0)
        self.uid = st.st_uid
        self.gid = st.st_gid
        self.atime = st.st_atime
        self.mtime = st.st_mtime
        self.ctime = st.st_ctime
        self.user = self.group = ''
        entry = pwd_from_uid(st.st_uid)
        if entry:
            self.user = entry.pw_name
        entry = grp_from_gid(st.st_gid)
        if entry:
            self.group = entry.gr_name
        self.mode = st.st_mode
        # Only collect st_rdev if we might need it for a mknod()
        # during restore.  On some platforms (i.e. kFreeBSD), it isn't
        # stable for other file types.  For example "cp -a" will
        # change it for a plain file.
        if stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
            self.rdev = st.st_rdev
        else:
            self.rdev = 0

    def _same_common(self, other):
        """Return true or false to indicate similarity in the hardlink sense."""
        return self.uid == other.uid \
            and self.gid == other.gid \
            and self.rdev == other.rdev \
            and self.mtime == other.mtime \
            and self.ctime == other.ctime \
            and self.user == other.user \
            and self.group == other.group

    def _encode_common(self):
        if not self.mode:
            return None
        atime = xstat.nsecs_to_timespec(self.atime)
        mtime = xstat.nsecs_to_timespec(self.mtime)
        ctime = xstat.nsecs_to_timespec(self.ctime)
        result = vint.pack('vvsvsvvVvVvV',
                           self.mode,
                           self.uid,
                           self.user,
                           self.gid,
                           self.group,
                           self.rdev,
                           atime[0],
                           atime[1],
                           mtime[0],
                           mtime[1],
                           ctime[0],
                           ctime[1])
        return result

    def _load_common_rec(self, port, legacy_format=False):
        unpack_fmt = 'vvsvsvvVvVvV'
        if legacy_format:
            unpack_fmt = 'VVsVsVvVvVvV'
        data = vint.read_bvec(port)
        (self.mode,
         self.uid,
         self.user,
         self.gid,
         self.group,
         self.rdev,
         self.atime,
         atime_ns,
         self.mtime,
         mtime_ns,
         self.ctime,
         ctime_ns) = vint.unpack(unpack_fmt, data)
        self.atime = xstat.timespec_to_nsecs((self.atime, atime_ns))
        self.mtime = xstat.timespec_to_nsecs((self.mtime, mtime_ns))
        self.ctime = xstat.timespec_to_nsecs((self.ctime, ctime_ns))

    def _recognized_file_type(self):
        return stat.S_ISREG(self.mode) \
            or stat.S_ISDIR(self.mode) \
            or stat.S_ISCHR(self.mode) \
            or stat.S_ISBLK(self.mode) \
            or stat.S_ISFIFO(self.mode) \
            or stat.S_ISSOCK(self.mode) \
            or stat.S_ISLNK(self.mode)

    def _create_via_common_rec(self, path, create_symlinks=True):
        if not self.mode:
            raise ApplyError('no metadata - cannot create path ' + path)

        # If the path already exists and is a dir, try rmdir.
        # If the path already exists and is anything else, try unlink.
        st = None
        try:
            st = xstat.lstat(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        if st:
            if stat.S_ISDIR(st.st_mode):
                try:
                    os.rmdir(path)
                except OSError as e:
                    if e.errno in (errno.ENOTEMPTY, errno.EEXIST):
                        msg = 'refusing to overwrite non-empty dir ' + path
                        raise Exception(msg)
                    raise
            else:
                os.unlink(path)

        if stat.S_ISREG(self.mode):
            assert(self._recognized_file_type())
            fd = os.open(path, os.O_CREAT|os.O_WRONLY|os.O_EXCL, 0o600)
            os.close(fd)
        elif stat.S_ISDIR(self.mode):
            assert(self._recognized_file_type())
            os.mkdir(path, 0o700)
        elif stat.S_ISCHR(self.mode):
            assert(self._recognized_file_type())
            os.mknod(path, 0o600 | stat.S_IFCHR, self.rdev)
        elif stat.S_ISBLK(self.mode):
            assert(self._recognized_file_type())
            os.mknod(path, 0o600 | stat.S_IFBLK, self.rdev)
        elif stat.S_ISFIFO(self.mode):
            assert(self._recognized_file_type())
            os.mknod(path, 0o600 | stat.S_IFIFO)
        elif stat.S_ISSOCK(self.mode):
            try:
                os.mknod(path, 0o600 | stat.S_IFSOCK)
            except OSError as e:
                if e.errno in (errno.EINVAL, errno.EPERM):
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.bind(path)
                else:
                    raise
        elif stat.S_ISLNK(self.mode):
            assert(self._recognized_file_type())
            if self.symlink_target and create_symlinks:
                # on MacOS, symlink() permissions depend on umask, and there's
                # no way to chown a symlink after creating it, so we have to
                # be careful here!
                oldumask = os.umask((self.mode & 0o777) ^ 0o777)
                try:
                    os.symlink(self.symlink_target, path)
                finally:
                    os.umask(oldumask)
        # FIXME: S_ISDOOR, S_IFMPB, S_IFCMP, S_IFNWK, ... see stat(2).
        else:
            assert(not self._recognized_file_type())
            add_error('not creating "%s" with unrecognized mode "0x%x"\n'
                      % (path, self.mode))

    def _apply_common_rec(self, path, restore_numeric_ids=False):
        if not self.mode:
            raise ApplyError('no metadata - cannot apply to ' + path)

        # FIXME: S_ISDOOR, S_IFMPB, S_IFCMP, S_IFNWK, ... see stat(2).
        # EACCES errors at this stage are fatal for the current path.
        if lutime and stat.S_ISLNK(self.mode):
            try:
                lutime(path, (self.atime, self.mtime))
            except OSError as e:
                if e.errno == errno.EACCES:
                    raise ApplyError('lutime: %s' % e)
                else:
                    raise
        else:
            try:
                utime(path, (self.atime, self.mtime))
            except OSError as e:
                if e.errno == errno.EACCES:
                    raise ApplyError('utime: %s' % e)
                else:
                    raise

        uid = gid = -1 # By default, do nothing.
        if is_superuser():
            uid = self.uid
            gid = self.gid
            if not restore_numeric_ids:
                if self.uid != 0 and self.user:
                    entry = pwd_from_name(self.user)
                    if entry:
                        uid = entry.pw_uid
                if self.gid != 0 and self.group:
                    entry = grp_from_name(self.group)
                    if entry:
                        gid = entry.gr_gid
        else: # not superuser - only consider changing the group/gid
            user_gids = os.getgroups()
            if self.gid in user_gids:
                gid = self.gid
            if not restore_numeric_ids and self.gid != 0:
                # The grp might not exist on the local system.
                grps = filter(None, [grp_from_gid(x) for x in user_gids])
                if self.group in [x.gr_name for x in grps]:
                    g = grp_from_name(self.group)
                    if g:
                        gid = g.gr_gid

        if uid != -1 or gid != -1:
            try:
                os.lchown(path, uid, gid)
            except OSError as e:
                if e.errno == errno.EPERM:
                    add_error('lchown: %s' %  e)
                elif sys.platform.startswith('cygwin') \
                   and e.errno == errno.EINVAL:
                    add_error('lchown: unknown uid/gid (%d/%d) for %s'
                              %  (uid, gid, path))
                else:
                    raise

        if _have_lchmod:
            try:
                os.lchmod(path, stat.S_IMODE(self.mode))
            except errno.ENOSYS:  # Function not implemented
                pass
        elif not stat.S_ISLNK(self.mode):
            os.chmod(path, stat.S_IMODE(self.mode))


    ## Path records

    def _encode_path(self):
        if self.path:
            return vint.pack('s', self.path)
        else:
            return None

    def _load_path_rec(self, port):
        self.path = vint.unpack('s', vint.read_bvec(port))[0]


    ## Symlink targets

    def _add_symlink_target(self, path, st):
        try:
            if stat.S_ISLNK(st.st_mode):
                self.symlink_target = os.readlink(path)
        except OSError as e:
            add_error('readlink: %s' % e)

    def _encode_symlink_target(self):
        return self.symlink_target

    def _load_symlink_target_rec(self, port):
        self.symlink_target = vint.read_bvec(port)


    ## Hardlink targets

    def _add_hardlink_target(self, target):
        self.hardlink_target = target

    def _same_hardlink_target(self, other):
        """Return true or false to indicate similarity in the hardlink sense."""
        return self.hardlink_target == other.hardlink_target

    def _encode_hardlink_target(self):
        return self.hardlink_target

    def _load_hardlink_target_rec(self, port):
        self.hardlink_target = vint.read_bvec(port)


    ## POSIX1e ACL records

    # Recorded as a list:
    #   [txt_id_acl, num_id_acl]
    # or, if a directory:
    #   [txt_id_acl, num_id_acl, txt_id_default_acl, num_id_default_acl]
    # The numeric/text distinction only matters when reading/restoring
    # a stored record.
    def _add_posix1e_acl(self, path, st):
        if not posix1e or not posix1e.HAS_EXTENDED_CHECK:
            return
        if not stat.S_ISLNK(st.st_mode):
            acls = None
            def_acls = None
            try:
                if posix1e.has_extended(path):
                    acl = posix1e.ACL(file=path)
                    acls = [acl, acl] # txt and num are the same
                    if stat.S_ISDIR(st.st_mode):
                        def_acl = posix1e.ACL(filedef=path)
                        def_acls = [def_acl, def_acl]
            except EnvironmentError as e:
                if e.errno not in (errno.EOPNOTSUPP, errno.ENOSYS):
                    raise
            if acls:
                txt_flags = posix1e.TEXT_ABBREVIATE
                num_flags = posix1e.TEXT_ABBREVIATE | posix1e.TEXT_NUMERIC_IDS
                acl_rep = [acls[0].to_any_text('', '\n', txt_flags),
                           acls[1].to_any_text('', '\n', num_flags)]
                if def_acls:
                    acl_rep.append(def_acls[0].to_any_text('', '\n', txt_flags))
                    acl_rep.append(def_acls[1].to_any_text('', '\n', num_flags))
                self.posix1e_acl = acl_rep

    def _same_posix1e_acl(self, other):
        """Return true or false to indicate similarity in the hardlink sense."""
        return self.posix1e_acl == other.posix1e_acl

    def _encode_posix1e_acl(self):
        # Encode as two strings (w/default ACL string possibly empty).
        if self.posix1e_acl:
            acls = self.posix1e_acl
            if len(acls) == 2:
                acls.extend(['', ''])
            return vint.pack('ssss', acls[0], acls[1], acls[2], acls[3])
        else:
            return None

    def _load_posix1e_acl_rec(self, port):
        acl_rep = vint.unpack('ssss', vint.read_bvec(port))
        if acl_rep[2] == '':
            acl_rep = acl_rep[:2]
        self.posix1e_acl = acl_rep

    def _apply_posix1e_acl_rec(self, path, restore_numeric_ids=False):
        def apply_acl(acl_rep, kind):
            try:
                acl = posix1e.ACL(text = acl_rep)
            except IOError as e:
                if e.errno == 0:
                    # pylibacl appears to return an IOError with errno
                    # set to 0 if a group referred to by the ACL rep
                    # doesn't exist on the current system.
                    raise ApplyError("POSIX1e ACL: can't create %r for %r"
                                     % (acl_rep, path))
                else:
                    raise
            try:
                acl.applyto(path, kind)
            except IOError as e:
                if e.errno == errno.EPERM or e.errno == errno.EOPNOTSUPP:
                    raise ApplyError('POSIX1e ACL applyto: %s' % e)
                else:
                    raise

        if not posix1e:
            if self.posix1e_acl:
                add_error("%s: can't restore ACLs; posix1e support missing.\n"
                          % path)
            return
        if self.posix1e_acl:
            acls = self.posix1e_acl
            if len(acls) > 2:
                if restore_numeric_ids:
                    apply_acl(acls[3], posix1e.ACL_TYPE_DEFAULT)
                else:
                    apply_acl(acls[2], posix1e.ACL_TYPE_DEFAULT)
            if restore_numeric_ids:
                apply_acl(acls[1], posix1e.ACL_TYPE_ACCESS)
            else:
                apply_acl(acls[0], posix1e.ACL_TYPE_ACCESS)


    ## Linux attributes (lsattr(1), chattr(1))

    def _add_linux_attr(self, path, st):
        check_linux_file_attr_api()
        if not get_linux_file_attr: return
        if stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode):
            try:
                attr = get_linux_file_attr(path)
                if attr != 0:
                    self.linux_attr = attr
            except OSError as e:
                if e.errno == errno.EACCES:
                    add_error('read Linux attr: %s' % e)
                elif e.errno in (errno.ENOTTY, errno.ENOSYS, errno.EOPNOTSUPP):
                    # Assume filesystem doesn't support attrs.
                    return
                else:
                    raise

    def _same_linux_attr(self, other):
        """Return true or false to indicate similarity in the hardlink sense."""
        return self.linux_attr == other.linux_attr

    def _encode_linux_attr(self):
        if self.linux_attr:
            return vint.pack('V', self.linux_attr)
        else:
            return None

    def _load_linux_attr_rec(self, port):
        data = vint.read_bvec(port)
        self.linux_attr = vint.unpack('V', data)[0]

    def _apply_linux_attr_rec(self, path, restore_numeric_ids=False):
        if self.linux_attr:
            check_linux_file_attr_api()
            if not set_linux_file_attr:
                add_error("%s: can't restore linuxattrs: "
                          "linuxattr support missing.\n" % path)
                return
            try:
                set_linux_file_attr(path, self.linux_attr)
            except OSError as e:
                if e.errno in (errno.ENOTTY, errno.EOPNOTSUPP, errno.ENOSYS,
                               errno.EACCES):
                    raise ApplyError('Linux chattr: %s (0x%s)'
                                     % (e, hex(self.linux_attr)))
                else:
                    raise


    ## Linux extended attributes (getfattr(1), setfattr(1))

    def _add_linux_xattr(self, path, st):
        if not xattr: return
        try:
            self.linux_xattr = xattr.get_all(path, nofollow=True)
        except EnvironmentError as e:
            if e.errno != errno.EOPNOTSUPP:
                raise

    def _same_linux_xattr(self, other):
        """Return true or false to indicate similarity in the hardlink sense."""
        return self.linux_xattr == other.linux_xattr

    def _encode_linux_xattr(self):
        if self.linux_xattr:
            result = vint.pack('V', len(self.linux_xattr))
            for name, value in self.linux_xattr:
                result += vint.pack('ss', name, value)
            return result
        else:
            return None

    def _load_linux_xattr_rec(self, file):
        data = vint.read_bvec(file)
        memfile = StringIO(data)
        result = []
        for i in range(vint.read_vuint(memfile)):
            key = vint.read_bvec(memfile)
            value = vint.read_bvec(memfile)
            result.append((key, value))
        self.linux_xattr = result

    def _apply_linux_xattr_rec(self, path, restore_numeric_ids=False):
        if not xattr:
            if self.linux_xattr:
                add_error("%s: can't restore xattr; xattr support missing.\n"
                          % path)
            return
        if not self.linux_xattr:
            return
        try:
            existing_xattrs = set(xattr.list(path, nofollow=True))
        except IOError as e:
            if e.errno == errno.EACCES:
                raise ApplyError('xattr.set %r: %s' % (path, e))
            else:
                raise
        for k, v in self.linux_xattr:
            if k not in existing_xattrs \
                    or v != xattr.get(path, k, nofollow=True):
                try:
                    xattr.set(path, k, v, nofollow=True)
                except IOError as e:
                    if e.errno == errno.EPERM \
                            or e.errno == errno.EOPNOTSUPP:
                        raise ApplyError('xattr.set %r: %s' % (path, e))
                    else:
                        raise
            existing_xattrs -= frozenset([k])
        for k in existing_xattrs:
            try:
                xattr.remove(path, k, nofollow=True)
            except IOError as e:
                if e.errno == errno.EPERM:
                    raise ApplyError('xattr.remove %r: %s' % (path, e))
                else:
                    raise

    def __init__(self):
        self.mode = self.uid = self.gid = self.user = self.group = None
        self.atime = self.mtime = self.ctime = None
        # optional members
        self.path = None
        self.size = None
        self.symlink_target = None
        self.hardlink_target = None
        self.linux_attr = None
        self.linux_xattr = None
        self.posix1e_acl = None

    def __repr__(self):
        result = ['<%s instance at %s' % (self.__class__, hex(id(self)))]
        if self.path:
            result += ' path:' + repr(self.path)
        if self.mode:
            result += ' mode:' + repr(xstat.mode_str(self.mode)
                                      + '(%s)' % hex(self.mode))
        if self.uid:
            result += ' uid:' + str(self.uid)
        if self.gid:
            result += ' gid:' + str(self.gid)
        if self.user:
            result += ' user:' + repr(self.user)
        if self.group:
            result += ' group:' + repr(self.group)
        if self.size:
            result += ' size:' + repr(self.size)
        for name, val in (('atime', self.atime),
                          ('mtime', self.mtime),
                          ('ctime', self.ctime)):
            result += ' %s:%r' \
                % (name,
                   time.strftime('%Y-%m-%d %H:%M %z',
                                 time.gmtime(xstat.fstime_floor_secs(val))))
        result += '>'
        return ''.join(result)

    def write(self, port, include_path=True):
        records = include_path and [(_rec_tag_path, self._encode_path())] or []
        records.extend([(_rec_tag_common_v2, self._encode_common()),
                        (_rec_tag_symlink_target,
                         self._encode_symlink_target()),
                        (_rec_tag_hardlink_target,
                         self._encode_hardlink_target()),
                        (_rec_tag_posix1e_acl, self._encode_posix1e_acl()),
                        (_rec_tag_linux_attr, self._encode_linux_attr()),
                        (_rec_tag_linux_xattr, self._encode_linux_xattr())])
        for tag, data in records:
            if data:
                vint.write_vuint(port, tag)
                vint.write_bvec(port, data)
        vint.write_vuint(port, _rec_tag_end)

    def encode(self, include_path=True):
        port = StringIO()
        self.write(port, include_path)
        return port.getvalue()

    @staticmethod
    def read(port):
        # This method should either return a valid Metadata object,
        # return None if there was no information at all (just a
        # _rec_tag_end), throw EOFError if there was nothing at all to
        # read, or throw an Exception if a valid object could not be
        # read completely.
        tag = vint.read_vuint(port)
        if tag == _rec_tag_end:
            return None
        try: # From here on, EOF is an error.
            result = Metadata()
            while True: # only exit is error (exception) or _rec_tag_end
                if tag == _rec_tag_path:
                    result._load_path_rec(port)
                elif tag == _rec_tag_common_v2:
                    result._load_common_rec(port)
                elif tag == _rec_tag_symlink_target:
                    result._load_symlink_target_rec(port)
                elif tag == _rec_tag_hardlink_target:
                    result._load_hardlink_target_rec(port)
                elif tag == _rec_tag_posix1e_acl:
                    result._load_posix1e_acl_rec(port)
                elif tag == _rec_tag_linux_attr:
                    result._load_linux_attr_rec(port)
                elif tag == _rec_tag_linux_xattr:
                    result._load_linux_xattr_rec(port)
                elif tag == _rec_tag_end:
                    return result
                elif tag == _rec_tag_common: # Should be very rare.
                    result._load_common_rec(port, legacy_format = True)
                else: # unknown record
                    vint.skip_bvec(port)
                tag = vint.read_vuint(port)
        except EOFError:
            raise Exception("EOF while reading Metadata")

    def isdir(self):
        return stat.S_ISDIR(self.mode)

    def create_path(self, path, create_symlinks=True):
        self._create_via_common_rec(path, create_symlinks=create_symlinks)

    def apply_to_path(self, path=None, restore_numeric_ids=False):
        # apply metadata to path -- file must exist
        if not path:
            path = self.path
        if not path:
            raise Exception('Metadata.apply_to_path() called with no path')
        if not self._recognized_file_type():
            add_error('not applying metadata to "%s"' % path
                      + ' with unrecognized mode "0x%x"\n' % self.mode)
            return
        num_ids = restore_numeric_ids
        for apply_metadata in (self._apply_common_rec,
                               self._apply_posix1e_acl_rec,
                               self._apply_linux_attr_rec,
                               self._apply_linux_xattr_rec):
            try:
                apply_metadata(path, restore_numeric_ids=num_ids)
            except ApplyError as e:
                add_error(e)

    def same_file(self, other):
        """Compare this to other for equivalency.  Return true if
        their information implies they could represent the same file
        on disk, in the hardlink sense.  Assume they're both regular
        files."""
        return self._same_common(other) \
            and self._same_hardlink_target(other) \
            and self._same_posix1e_acl(other) \
            and self._same_linux_attr(other) \
            and self._same_linux_xattr(other)
