"""Tests for emission of high-level markup, as by templates"""

from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_, ok_


class MarkupTests(DxrInstanceTestCase):
    def test_autofocus_root(self):
        """Autofocus the query field at the root of each tree but not
        elsewhere."""
        markup = self.source_page('')
        ok_('<input type="text" name="q" autofocus' in markup)

        response = self.client().get('/code/source/%26folder%26')
        eq_(response.status_code, 200)
        ok_('<input type="text" name="q" autofocus' not in response.data)

    def test_folder_name_escaping(self):
        """Make sure folder names are HTML-escaped."""
        markup = self.source_page('')
        ok_('&folder&' not in markup)
        ok_('&amp;folder&amp;' in markup)

    def test_body_escaping(self):
        """Make sure source code is HTML-escaped."""
        markup = self.source_page('%26folder%26/README.mkd')
        ok_('<stuff>' not in markup)
        ok_('& things' not in markup)
        ok_('&lt;stuff&gt;' in markup)
        ok_('&amp; things' in markup)

    def test_folder_links(self):
        """Make sure folders link to the right places, not just to their first
        chars."""
        markup = self.source_page('')
        ok_('<a href="/code/source/%26folder%26" class="icon folder">&amp;folder&amp;</a>'
            in markup)

    def test_file_links(self):
        """Make sure files link to the right places."""
        markup = self.source_page('%26folder%26')
        ok_('<a href="/code/source/%26folder%26/README.mkd" class="icon unknown">README.mkd</a>'
            in markup)

    def test_analytics_snippet_empty(self):
        """Make sure google analytics snippet doesn't show up
        in when the key isn't configured"""
        markup = self.source_page('')
        ok_('.google-analytics.com' not in markup)
