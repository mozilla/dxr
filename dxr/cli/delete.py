from click import command, echo, option
from pyelasticsearch import ElasticSearch

from dxr.cli.utils import tree_objects, config_option, tree_names_argument


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
    """Delete indices and their catalog entries."""
    es = ElasticSearch(config.es_hosts)
    if all:
        echo('Deleting catalog...')
        es.delete_index(config.es_catalog_index)
        # TODO: Delete tree indices as well.
    else:
        raise NotImplementedError
