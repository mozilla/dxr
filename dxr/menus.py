from dxr.utils import without_ending


class MenuMakerIdTagger(type):
    """Metaclass which automatically generates an ``id`` attr on the class as
    a serializable class identifier.

    Having a dedicated identifier allows MenuMakers to move or change name
    without breaking index compatibility.

    Expects a ``_plugin`` attr to use as a prefix.

    """
    def __new__(metaclass, name, bases, dict):
        dict['id'] = without_ending('MenuMaker', name)
        return type.__new__(metaclass, name, bases, dict)


class MenuMaker(object):
    """Serializable data + functionality that spits out menu items on refs

    It is often possible to render multiple :class:`~dxr.lines.Ref` menu items
    from one set of data. This class acts as a serialization bucket for each
    set of data at index time and also rehydrates it into menu items at
    request time.

    :classvar plugin: The name of the plugin to which I belong, so I can be
        looked up later during rehydration

    """
    __metaclass__ = MenuMakerIdTagger

    def __init__(self, tree):
        """
        :arg tree: A TreeConfig representing the tree I make menus for

        Subclasses should add whatever additional constructor args they need.

        """
        self.tree = tree

    def es(self):
        """Return serialized data to insert into elasticsearch.

        This will be JSONified into a string before ES sees it, so you can do
        whatever you want: don't worry about mixing types in arrays, for
        instance.

        """
        raise NotImplementedError

    @classmethod
    def from_es(cls, tree, data):
        """Recreate an instance of this class using data from ES.

        This should expect whatever ``self.es()`` returns.

        """
        raise NotImplementedError

    def menu_items(self):
        """Return an iterable of menu items to be attached to a ref.

        Return an iterable of dicts of this form::

            {
                html: the HTML to be used as the menu item itself
                href: the URL to visit when the menu item is chosen
                title: the tooltip text given on hovering over the menu item
                icon: the icon to show next to the menu item: the name of a PNG
                    from the ``icons`` folder, without the .png extension
            }

        """
        raise NotImplementedError


class SingleDatumMenuMaker(MenuMaker):
    """A :class:`~dxr.menus.MenuMaker` that takes a tree and one piece of
    parametrizing data

    :ivar data: The data to be persisted in ES

    Even if you have multiple (but not sparse) pieces of data, it's often
    easiest to pack them into a tuple and use this.

    """
    def __init__(self, tree, data):
        """
        :arg data: JSON-serializable data to persist in ES

        """
        super(SingleDatumMenuMaker, self).__init__(tree)
        self.data = data

    def es(self):
        """Return serialized data to insert into elasticsearch.

        This will be JSONified into a string before ES sees it, so you can do
        whatever you want: don't worry about mixing types in arrays, for
        instance.

        """
        return self.data

    @classmethod
    def from_es(cls, tree, data):
        return cls(tree, data)
