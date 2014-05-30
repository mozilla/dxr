"""

The build command is responsible for laying down whatever data the indexing
plugins need to do their jobs--possibly nothing if no compiler is involved. The
constructors of the indexing plugins can help with that: for example, by
setting environment variables.

"""
plugin = DxrPlugin.from_namespace(globals())
