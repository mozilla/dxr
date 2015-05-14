"""Tests for the nav pane"""

from nose.tools import ok_

from dxr.testing import DxrInstanceTestCase


class NavTests(DxrInstanceTestCase):
    def test_nav(self):
        markup = self.source_page('main.cpp')

        # Header for class should be there:
        ok_('<h4>nsAuth</h4>' in markup)

        # Class link should be there:
        ok_('title="nsAuth" class="class icon">nsAuth</a>' in
            markup)

        # Instance vars should be there:
        ok_('title="mPtr" class="field icon">mPtr</a>' in markup)

        # Make sure macros get into the list:
        ok_('title="SOMETHING" class="macro icon">SOMETHING</a>' in markup)

        # Ptr shouldn't be a macro:
        ok_('title="Ptr" class="macro icon">Ptr</a>' not in markup)
