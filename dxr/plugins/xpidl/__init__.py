from functools import partial
from os.path import abspath

from schema import Optional, Use, And

from dxr.config import AbsPath
from dxr.plugins import Plugin, AdHocTreeToIndex, filters_from_namespace
from dxr.plugins.xpidl import filters
from dxr.plugins.xpidl.mappings import mappings
from dxr.plugins.xpidl.indexers import FileToIndex


def split_on_colon_into_abspaths(value):
    return map(abspath, value.strip().split(':'))


ColonPathList = And(basestring,
                    Use(split_on_colon_into_abspaths),
                    error='This should be a colon-separated list of paths.')

plugin = Plugin(
    tree_to_index=partial(AdHocTreeToIndex,
                          file_to_index_class=FileToIndex),
    filters=filters_from_namespace(filters.__dict__),
    mappings=mappings,
    config_schema={
        'header_bucket': AbsPath,
        Optional('include_folders', default=[]): ColonPathList})
