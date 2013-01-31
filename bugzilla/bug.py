# base.py - the base classes etc. for a Python interface to bugzilla
#
# Copyright (C) 2007, 2008, 2009, 2010 Red Hat Inc.
# Author: Will Woods <wwoods@redhat.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

import locale

from bugzilla import log


class _Bug(object):
    '''A container object for a bug report. Requires a Bugzilla instance -
    every Bug is on a Bugzilla, obviously.
    Optional keyword args:
        dict=DICT   - populate attributes with the result of a getBug() call
        bug_id=ID   - if dict does not contain bug_id, this is required before
                      you can read any attributes or make modifications to this
                      bug.
    '''
    def __init__(self, bugzilla, **kwargs):
        self.bugzilla = bugzilla

        if 'dict' in kwargs and kwargs['dict']:
            log.debug("Bug(%s)" % sorted(kwargs['dict'].keys()))
            self._update_dict(kwargs['dict'])

        if 'bug_id' in kwargs:
            log.debug("Bug(%i)" % kwargs['bug_id'])
            setattr(self, 'id', kwargs['bug_id'])

        # Back compat for a previously handled param
        if 'autorefresh' in kwargs:
            del(kwargs["autorefresh"])

        if not hasattr(self, 'id'):
            raise TypeError("Bug object needs a bug_id")

        self.weburl = bugzilla.url.replace('xmlrpc.cgi',
                                           'show_bug.cgi?id=%i' % self.bug_id)

    def __str__(self):
        '''Return a simple string representation of this bug

        This is available only for compatibility. Using 'str(bug)' and
        'print bug' is not recommended because of potential encoding issues.
        Please use unicode(bug) where possible.
        '''
        return unicode(self).encode(locale.getpreferredencoding(), 'replace')

    def __unicode__(self):
        '''Return a simple unicode string representation of this bug'''
        return u"#%-6s %-10s - %s - %s" % (self.bug_id, self.bug_status,
                                          self.assigned_to, self.summary)

    def __repr__(self):
        return '<Bug #%i on %s at %#x>' % (self.bug_id, self.bugzilla.url,
                                           id(self))

    def __getattr__(self, name):
        if 'id' not in self.__dict__:
            # This is fatal, since we have no ID to pass to refresh()
            # Can happen if a messed up include_fields is passed to query
            raise AttributeError("No bug ID cached for bug object")

        refreshed = False
        while True:
            if name in self.__dict__:
                return self.__dict__[name]

            # Check field aliases
            for newname, oldname in self.bugzilla.field_aliases:
                if name == oldname and newname in self.__dict__:
                    return self.__dict__[newname]

            if refreshed:
                break
            log.debug("Bug %i missing attribute '%s' - doing refresh()",
                      self.bug_id, name)
            self.refresh()
            refreshed = True

        raise AttributeError("Bug object has no attribute '%s'" % name)

    def __hasattr__(self):
        if name in self.__dict__:
            return True

        for newname, oldname in self.bugzilla.field_aliases:
            if name == oldname and newname in self.__dict__:
                return True
        return False

    def __getstate__(self):
        sd = self.__dict__
        if self.bugzilla:
            fields = self.bugzilla.bugfields
        else:
            fields = self.bugfields
        vals = [(k, sd[k]) for k in sd.keys() if k in fields]
        vals.append(('bugfields', fields))
        return dict(vals)

    def __setstate__(self, d):
        self._update_dict(d)
        self.bugzilla = None

    def refresh(self):
        '''Refresh all the data in this Bug.'''
        r = self.bugzilla._getbug(self.bug_id)

        # Use post_translation to convert getbug results to back compat values
        q = {}
        q["id"] = str(self.bug_id)
        self.bugzilla.post_translation(q, r)

        self._update_dict(r)

    def _update_dict(self, newdict):
        '''
        Update internal dictionary, in a way that ensures no duplicate
        entries are stored WRT field aliases
        '''
        for newname, oldname in self.bugzilla.field_aliases:
            if not oldname in newdict:
                continue

            if newname not in newdict:
                newdict[newname] = newdict[oldname]
            elif newdict[newname] != newdict[oldname]:
                log.debug("Update dict contained differing alias values "
                          "d[%s]=%s and d[%s]=%s , dropping the value "
                          "d[%s]", newname, newdict[newname], oldname,
                          newdict[oldname], oldname)
            del(newdict[oldname])

        self.__dict__.update(newdict)


    def reload(self):
        '''An alias for refresh()'''
        self.refresh()


    #####################
    # Modify bug status #
    #####################

    def setstatus(self, status, comment=None, private=False,
                  private_in_it=False, nomail=False):
        '''
        Update the status for this bug report.
        Commonly-used values are ASSIGNED, MODIFIED, and NEEDINFO.

        To change bugs to CLOSED, use .close() instead.
        '''
        ignore = private_in_it
        ignore = nomail

        vals = self.bugzilla.build_update(status=status,
                                          comment=comment,
                                          comment_private=private)
        log.debug("setstatus: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)

    def close(self, resolution, dupeid=None, fixedin=None,
              comment=None, isprivate=False,
              private_in_it=False, nomail=False):
        '''Close this bug.
        Valid values for resolution are in bz.querydefaults['resolution_list']
        For bugzilla.redhat.com that's:
        ['NOTABUG', 'WONTFIX', 'DEFERRED', 'WORKSFORME', 'CURRENTRELEASE',
         'RAWHIDE', 'ERRATA', 'DUPLICATE', 'UPSTREAM', 'NEXTRELEASE',
         'CANTFIX', 'INSUFFICIENT_DATA']
        If using DUPLICATE, you need to set dupeid to the ID of the other bug.
        If using WORKSFORME/CURRENTRELEASE/RAWHIDE/ERRATA/UPSTREAM/NEXTRELEASE
          you can (and should) set 'new_fixed_in' to a string representing the
          version that fixes the bug.
        You can optionally add a comment while closing the bug. Set 'isprivate'
          to True if you want that comment to be private.
        '''
        ignore = private_in_it
        ignore = nomail

        vals = self.bugzilla.build_update(comment=comment,
                                          comment_private=isprivate,
                                          resolution=resolution,
                                          dupe_of=dupeid,
                                          fixed_in=fixedin,
                                          status="CLOSED")
        log.debug("close: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)


    #####################
    # Modify bug emails #
    #####################

    def setassignee(self, assigned_to=None, reporter=None,
                    qa_contact=None, comment=None):
        '''
        Set any of the assigned_to or qa_contact fields to a new
        bugzilla account, with an optional comment, e.g.
        setassignee(assigned_to='wwoods@redhat.com')
        setassignee(qa_contact='wwoods@redhat.com', comment='wwoods QA ftw')

        You must set at least one of the two assignee fields, or this method
        will throw a ValueError.

        Returns [bug_id, mailresults].
        '''
        if reporter:
            raise ValueError("reporter can not be changed")

        if not (assigned_to or qa_contact):
            raise ValueError("You must set one of assigned_to "
                             " or qa_contact")

        vals = self.bugzilla.build_update(assigned_to=assigned_to,
                                          qa_contact=qa_contact,
                                          comment=comment)
        log.debug("setassignee: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)

    def addcc(self, cclist, comment=None):
        '''
        Adds the given email addresses to the CC list for this bug.
        cclist: list of email addresses (strings)
        comment: optional comment to add to the bug
        '''
        vals = self.bugzilla.build_update(comment=comment,
                                          cc_add=cclist)
        log.debug("addcc: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)

    def deletecc(self, cclist, comment=None):
        '''
        Removes the given email addresses from the CC list for this bug.
        '''
        vals = self.bugzilla.build_update(comment=comment,
                                          cc_remove=cclist)
        log.debug("deletecc: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)


    ###############
    # Add comment #
    ###############

    def addcomment(self, comment, private=False,
                   timestamp=None, worktime=None, bz_gid=None):
        '''
        Add the given comment to this bug. Set private to True to mark this
        comment as private.
        '''
        ignore = timestamp
        ignore = bz_gid
        ignore = worktime

        vals = self.bugzilla.build_update(comment=comment,
                                          comment_private=private)
        log.debug("addcomment: update=%s", vals)

        return self.bugzilla.update_bugs(self.bug_id, vals)


    ##########################
    # Get/set bug whiteboard #
    ##########################

    def _dowhiteboard(self, text, which, action, comment, private):
        '''
        Update the whiteboard given by 'which' for the given bug.
        '''
        if which not in ["status", "qa", "devel", "internal"]:
            raise ValueError("Unknown whiteboard type '%s'" % which)

        if not which.endswith('_whiteboard'):
            which = which + '_whiteboard'
        if which == "status_whiteboard":
            which = "whiteboard"

        if action != 'overwrite':
            wb = getattr(self, which, '')

            if action == 'prepend':
                text = text + ' ' + wb
            elif action == 'append':
                text = wb + ' ' + text
            else:
                raise ValueError("Unknown whiteboard action '%s'" % action)

        updateargs = {which: text}
        vals = self.bugzilla.build_update(comment=comment,
                                          comment_private=private,
                                          **updateargs)
        log.debug("_updatewhiteboard: update=%s", vals)

        self.bugzilla.update_bugs(self.bug_id, vals)


    def appendwhiteboard(self, text, which='status',
                         comment=None, private=False):
        '''Append the given text (with a space before it) to the given
        whiteboard. Defaults to using status_whiteboard.'''
        self._dowhiteboard(text, which, "append", comment, private)

    def prependwhiteboard(self, text, which='status',
                          comment=None, private=False):
        '''Prepend the given text (with a space following it) to the given
        whiteboard. Defaults to using status_whiteboard.'''
        self._dowhiteboard(text, which, "prepend", comment, private)

    def setwhiteboard(self, text, which='status',
                      comment=None, private=False):
        '''Overwrites the contents of the given whiteboard with the given text.
        Defaults to using status_whiteboard.'''
        self._dowhiteboard(text, which, "overwrite", comment, private)

    def addtag(self, tag, which='status'):
        '''Adds the given tag to the given bug.'''
        whiteboard = self.getwhiteboard(which)
        if whiteboard:
            self.appendwhiteboard(tag, which)
        else:
            self.setwhiteboard(tag, which)

    def gettags(self, which='status'):
        '''Get a list of tags (basically just whitespace-split the given
        whiteboard)'''
        return self.getwhiteboard(which).split()

    def deltag(self, tag, which='status'):
        '''Removes the given tag from the given bug.'''
        tags = self.gettags(which)
        tags.remove(tag)
        self.setwhiteboard(' '.join(tags), which)


    #####################
    # Get/Set bug flags #
    #####################

    def get_flag_type(self, name):
        """
        Return flag_type information for a specific flag
        """
        for t in self.flag_types:
            if t['name'] == name:
                return t
        return None

    def get_flags(self, name):
        """
        Return flag value information for a specific flag
        """
        ft = self.get_flag_type(name)
        if not ft:
            return None

        return ft['flags']

    def get_flag_status(self, name):
        """
        Return a flag 'status' field

        This method works only for simple flags that have only a 'status' field
        with no "requestee" info, and no multiple values. For more complex
        flags, use get_flags() to get extended flag value information.
        """
        f = self.get_flags(name)
        if not f:
            return None

        # This method works only for simple flags that have only one
        # value set.
        assert len(f) <= 1

        return f[0]['status']


    ######################
    # Deprecated methods #
    ######################

    def getwhiteboard(self, which='status'):
        '''
        Deprecated. Use bug.qa_whiteboard, bug.devel_whiteboard, etc.
        '''
        return getattr(self, "%s_whiteboard" % which)

    def updateflags(self, flags):
        '''
        Deprecated, use bugzilla.update_flags() directly
        '''
        flaglist = []
        for key, value in flags.items():
            flaglist.append({"name": key, "status": value})
        return self.bugzilla.update_flags(self.bug_id, flaglist)


class _User(object):
    '''Container object for a bugzilla User.

    :arg bugzilla: Bugzilla instance that this User belongs to.
    :arg name: name that references a user
    :kwarg userid: id in bugzilla for a user
    :kwarg real_name: User's real name
    :kwarg email: User's email address
    :kwarg can_login: If set True, the user can login
    '''
    def __init__(self, bugzilla, name, userid, real_name=None, email=None,
            can_login=True):
        self.bugzilla = bugzilla
        self.__name = name
        self.__userid = userid
        self.real_name = real_name
        self.__email = email
        self.__can_login = can_login
        self.password = None

        # This tells us whether self.name has been changed but not synced to
        # bugzilla
        self._name_dirty = False

    ### Read-only attributes ###

    # We make these properties so that the user cannot set them.  They are
    # unaffected by the update() method so it would be misleading to let them
    # be changed.
    @property
    def userid(self):
        return self.__userid

    @property
    def email(self):
        return self.__email

    @property
    def can_login(self):
        return self.__can_login

    ### name is a key in some methods.  Mark it dirty when we change it ###
    def _name(self):
        return self.__name

    def _set_name(self, value):
        self._name_dirty = True
        self.__name = value

    name = property(_name, _set_name)

    def update(self):
        '''Update Bugzilla with these values.

        :raises xmlrpclib.Fault: Code 304 if you aren't allowed to edit
            the user
        '''
        self._name_dirty = False
        self.bugzilla._update(ids=self.userid, update={'name': self.name,
            'real_name': self.real_name, 'password': self.password})

    def updateperms(self, action, groups):
        '''A method to update the permissions (group membership) of a bugzilla
        user.

        :arg action: either add or rem
        :arg groups: list of groups to be added to (i.e. ['fedora_contrib'])
        '''
        if self._name_dirty:
            from bugzilla import BugzillaError
            raise BugzillaError('name has been changed.  run update() before'
                    ' updating perms.')
        self.bugzilla._updateperms(self.name, action, groups)
