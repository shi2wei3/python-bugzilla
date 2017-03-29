#
# Copyright Red Hat, Inc. 2012
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.
#

'''
Unit tests that do permanent functional against a real bugzilla instances.
'''

from __future__ import print_function

import os
import unittest

import bugzilla

import tests

cf = os.path.expanduser("~/.bugzillacookies")
tf = os.path.expanduser("~/.bugzillatoken")


class RHPartnerTest(unittest.TestCase):
    # Despite its name, this instance is simply for bugzilla testing,
    # doesn't send out emails and is blown away occasionally. The front
    # page has some info.
    url = tests.REDHAT_URL or "https://partner-bugzilla.redhat.com/xmlrpc.cgi"
    bzclass = bugzilla.RHBugzilla

    def _test3Query(self, args, expectstr):
        """
        Create a bug with minimal amount of fields, then close it
        """
        bz = self.bzclass(url=self.url, cookiefile=cf, tokenfile=tf)
        out = tests.clicomm("bugzilla query %s" % args, bz)

        self.assertTrue(expectstr in out)


class RHTest(RHPartnerTest):
    test0 = lambda s: RHPartnerTest._test3Query(s,
"--product='Red Hat Enterprise Linux 7' --component=libguestfs --bug_status=CLOSED --flag=needinfo? --bug_id=1076478 --outputformat \"[^]%{bug_id}[#_#]%{component}[#_#]%{sub_component}[#_#]%{priority}/%{bug_severity}[#_#]%{status}[#_#]%{short_desc}[#_#]%{product}[#_#]%{flags}[#_#]%{status_whiteboard}[#_#]\"",
"[^]1076478[#_#]libguestfs[#_#][#_#]unspecified/unspecified[#_#]CLOSED[#_#]FTBFS: libguestfs-1.22.6-15.el7[#_#]Red Hat Enterprise Linux 7[#_#]needinfo?igor.zubkov@gmail.com,needinfo?igor.zubkov@gmail.com,rhel-7.1.0?,pm_ack+,devel_ack?,qa_ack?[#_#][#_#]")
    test1 = lambda s:RHPartnerTest._test3Query(s,
"--product='Red Hat Enterprise Linux 7' --component=kernel --bug_status=CLOSED --qa_contact=virt-bugs@redhat.com --sub-component='Virtualization Xen' --flag=qa_ack? --bug_id=1167010 --outputformat \"[^]%{bug_id}[#_#]%{component}[#_#]%{sub_component}[#_#]%{priority}/%{bug_severity}[#_#]%{status}[#_#]%{short_desc}[#_#]%{product}[#_#]%{flags_requestee}[#_#]%{status_whiteboard}[#_#]\"",
"[^]1167010[#_#]kernel[#_#][#_#]unspecified/high[#_#]CLOSED[#_#]Known mm bug on Xen PV instances - vsftpd fails with 500 OOPS munmap[#_#]Red Hat Enterprise Linux 7[#_#][#_#][#_#]")
