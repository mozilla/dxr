"""XPIDL plugin: analyze XPIDL files using the mozilla-central xpidl parser.

This plugin analyzes XPIDL files by attempting to parse all files ending in '.idl' using the
xpidl parser. Then it delicately walks the productions in the AST to pull out relevant
information, such as interface and member declarations, and shoves them into refs and needles to
feed to ES. The plugin borrows the xpidl C++ header generating code to find direct hops from
interface constructs to their corresponding output in header land. It also donates Filters which
use the discovered needles to perform structural queries.

For further reference, see https://developer.mozilla.org/en-US/docs/Mozilla/XPIDL.
"""

from functools import partial
from os.path import abspath

from schema import Optional, Use, And

from dxr.config import AbsPath
from dxr.plugins import Plugin, AdHocTreeToIndex, filters_from_namespace, refs_from_namespace
from dxr.plugins.xpidl import filters, refs
from dxr.plugins.xpidl.mappings import mappings
from dxr.plugins.xpidl.indexers import FileToIndex


def split_on_space_into_abspaths(value):
    return map(abspath, value.strip().split())


ColonPathList = And(basestring,
                    Use(split_on_space_into_abspaths),
                    error='This should be a space-separated list of paths.')

plugin = Plugin(
    tree_to_index=partial(AdHocTreeToIndex,
                          file_to_index_class=FileToIndex),
    refs=refs_from_namespace(refs.__dict__),
    filters=filters_from_namespace(filters.__dict__),
    badge_colors={'xpidl': '#DAF6B9'},
    mappings=mappings,
    config_schema={
        'header_path': AbsPath,
        Optional('include_folders', default=[]): ColonPathList})
