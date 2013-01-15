from flask import Flask, request


app = Flask('dxr')  # Look in this package for static files, templates, etc.


@app.route('/search')
def search():
    """Search by regex, caller, superclass, or whatever."""
    return 'searched!'


@app.route('/<path:tree_and_path>')
def browse(tree_and_path):
    """Show a directory listing or a single file from one of the trees."""
    tree, _, path = tree_and_path.partition('/')
    return 'browse to tree %s at %s' % (tree, path)
