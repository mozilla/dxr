"""Tests for whether buglink finds and links bug references"""

from dxr.testing import DxrInstanceTestCase, menu_on


class XblTests(DxrInstanceTestCase):
    def test_refs(self):
        markup = self.source_page('socialchat.xml')

        # Expect refs to appear on "implements" sections.
        menu_on(markup,
                'nsIDOMEventListener',
                {'html': 'Find declaration of nsIDOMEventListener',
                 'href': '/code/search?q=type-decl%3A%22nsIDOMEventListener%22'})
        menu_on(markup,
                'nsIMessageListener',
                {'html': 'Find definition of nsIMessageListener',
                 'href': '/code/search?q=type%3A%22nsIMessageListener%22'})
        menu_on(markup,
                'nsIDOMEventListener2',
                {'html': 'Find declaration of nsIDOMEventListener2',
                 'href': '/code/search?q=type-decl%3A%22nsIDOMEventListener2%22'})

    def test_searches(self):
        """Be able to find fields, properties, and methods qualified and unqualified.
        """
        self.found_line_eq('type:nsIDOMEventListener',
                           '&lt;implementation implements="<b>nsIDOMEventListener</b>, nsIMessageListener"&gt;',
                           9)

        self.found_line_eq('type:nsIMessageListener',
                           '&lt;implementation implements="nsIDOMEventListener, <b>nsIMessageListener</b>"&gt;',
                           9)

        self.found_line_eq('prop:promiseChatLoaded',
                           '&lt;property name="<b>promiseChatLoaded</b>"&gt;',
                           11)

        self.found_line_eq('prop:_chat',
                           '&lt;field name="<b>_chat</b>" readonly="true"&gt;',
                           14)

        self.found_line_eq('+prop:chatbox#focus',
                           '&lt;method name="<b>focus</b>"&gt;',
                           17)

        self.found_line_eq('+prop:chatbox#showNotifications',
                           '&lt;method name="<b>showNotifications</b>"&gt;',
                           20)

        self.found_line_eq('+prop:chatbar#focus',
                           '&lt;method name="<b>focus</b>"&gt;',
                           36)

        self.found_line_eq('+prop:chatbar#selectedChat',
                           '&lt;property name="<b>selectedChat</b>"&gt;',
                           41)

        self.found_line_eq('prop:menuItemMap',
                           '&lt;field name="<b>menuItemMap</b>"&gt;new WeakMap()&lt;/field&gt;',
                           44)
