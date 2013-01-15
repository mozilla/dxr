import os.path

from flask import Blueprint, Flask, request, send_from_directory


# Look in the 'dxr' package for static files, templates, etc.:
dxr_blueprint = Blueprint('dxr_blueprint', 'dxr')


def make_app(instance_folder):
    """Return a DXR application which looks in the given folder for
    configuration.

    Also set up the static and template folder according to the configured
    template.

    """
    # TODO: Actually obey the template selection in the config file by passing
    # a different static_folder and template_folder to Flask().
    app = Flask('dxr', instance_path=instance_folder)
    app.register_blueprint(dxr_blueprint)
    return app


@dxr_blueprint.route('/')
def index():
    return 'index!'


@dxr_blueprint.route('/search')
def search():
    """Search by regex, caller, superclass, or whatever."""
    return 'searched!'


@dxr_blueprint.route('/<path:tree_and_path>')
def browse(tree_and_path):
    """Show a directory listing or a single file from one of the trees."""
    tree, _, path = tree_and_path.partition('/')
    return send_from_directory(
        os.path.join('/home/vagrant/dxr/tests/json-test/target', tree),
        path)
#NEXT: Make this work. This will lead you to making the CSS (static files) work as well. It'll also make you get the ini file working.
