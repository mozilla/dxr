from click import ClickException, command, echo, option
from pyelasticsearch import ElasticSearch, ElasticHttpNotFoundError

from dxr.cli.utils import config_option, tree_names_argument
from dxr.config import FORMAT
from dxr.es import TREE


@command()
@config_option
@option('--force', '-f',
        is_flag=True,
        help='Skip prompting for confirmation.')
@option('--all', '-a',
        is_flag=True,
        help='Delete all trees, and also delete the catalog index, in case it '
             'was somehow corrupted.')
@tree_names_argument
def delete(config, tree_names, all, force):
    """Delete indices and their catalog entries.

    This deletes the indices that have the format version of the copy of DXR
    this runs under.

    """
    es = ElasticSearch(config.es_hosts)
    if all:
        echo('Deleting catalog...')
        es.delete_index(config.es_catalog_index)
        # TODO: Delete tree indices as well.
    else:
        for tree_name in tree_names:
            frozen_id = '%s/%s' % (FORMAT, tree_name)
            try:
                frozen = es.get(config.es_catalog_index, TREE, frozen_id)
            except ElasticHttpNotFoundError:
                raise ClickException('No tree "%s" in catalog.' % tree_name)
            # Delete the index first. That way, if that fails, we can still
            # try again; we won't have lost the catalog entry. Refresh is
            # infrequent enough that we wouldn't avoid a race around a
            # catalogued but deleted instance the other way around.
            try:
                es.delete_index(frozen['_source']['es_alias'])
            except ElasticHttpNotFoundError:
                # It's already gone. Fine. Just remove the catalog entry.
                pass
            es.delete(config.es_catalog_index, TREE, frozen_id)
