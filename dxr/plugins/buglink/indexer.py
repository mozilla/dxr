import dxr.plugins

# Nothing to do here, but we must implement indexer.py to explicitly declare
# that these functions are no-op. Otherwise DXR shall assume the file or the
# implementation is missing, and thus, something is badly wrong.

def pre_process(tree, environ):
    pass

def post_process(tree, conn):
    pass

__all__ = dxr.plugins.indexer_exports()
