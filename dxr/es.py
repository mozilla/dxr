"""Elasticsearch utilities not general enough to lift into pyelasticsearch"""

from flask import current_app
from pyelasticsearch import ElasticHttpNotFoundError
from werkzeug.exceptions import NotFound

from dxr.config import FORMAT


UNINDEXED_STRING = {
    'type': 'string',
    'index': 'no',
}


UNINDEXED_INT = {
    'type': 'integer',
    'index': 'no',
}


TREE = 'tree'  # 'tree' doctype


def frozen_configs():
    """Return a list of dicts, each describing a tree of the current format
    version."""
    return filtered_query(current_app.dxr_config.es_catalog_index,
                          TREE,
                          filter={'format': FORMAT},
                          sort=['name'],
                          size=10000)


def frozen_config(tree_name):
    """Return the bits of config that are "frozen" in place upon indexing.

    Return the ES "tree" doc for the given tree at the current format
    version. Raise NotFound if the tree

    """
    try:
        frozen = current_app.es.get(current_app.dxr_config.es_catalog_index,
                                    TREE,
                                    '%s/%s' % (FORMAT, tree_name))
        return frozen['_source']
    except (ElasticHttpNotFoundError, KeyError):
        # If nothing is found, we still get a hash, but it has no _source key.
        raise NotFound('No such tree as %s' % tree_name)


def es_alias_or_not_found(tree):
    """Return the elasticsearch alias for a tree, or raise NotFound."""
    return frozen_config(tree)['es_alias']


def filtered_query(index, doc_type, filter, sort=None, size=1, include=None, exclude=None):
    """Do a simple, filtered term query, returning an iterable of _sources.

    This is just a mindless upfactoring. It probably shouldn't be blown up
    into a full-fledged API.

    ``include`` and ``exclude`` are mutually exclusive for now.

    """
    query = {
            'query': {
                'filtered': {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'term': filter
                    }
                }
            }
        }
    if sort:
        query['sort'] = sort
    if include is not None:
        query['_source'] = {'include': include}
    elif exclude is not None:
        query['_source'] = {'exclude': exclude}
    return _sources(current_app.es.search(
        query,
        index=index,
        doc_type=doc_type,
        size=size))


def _sources(search_results):
    """Return just the _source attributes of some ES search results."""
    return [r['_source'] for r in search_results['hits']['hits']]
