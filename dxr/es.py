"""Elasticsearch utilities not general enough to lift into pyelasticsearch"""

from flask import current_app
from pyelasticsearch import ElasticHttpNotFoundError, ElasticHttpError
from werkzeug.exceptions import NotFound

from dxr.config import FORMAT


UNINDEXED_STRING = {
    'type': 'keyword',
    'index': 'false',
}


UNANALYZED_STRING = {
    'type': 'keyword',
    'index': 'true',
}


UNINDEXED_INT = {
    'type': 'integer',
    'index': 'false',
}


UNINDEXED_LONG = {
    'type': 'long',
    'index': 'false',
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


def filtered_query(*args, **kwargs):
    """Do a simple, filtered term query, returning an iterable of sources.

    This is just a mindless upfactoring. It probably shouldn't be blown up
    into a full-fledged API.

    ``include`` and ``exclude`` are mutually exclusive for now.

    """
    return sources(filtered_query_hits(*args, **kwargs))


def filtered_query_hits(index, doc_type, filter, sort=None, size=1, include=None, exclude=None):
    """Do a simple, filtered term query, returning an iterable of hit hashes."""
    query = {
            'query': {
                'bool': {
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
    return current_app.es.search(
        query,
        index=index,
        doc_type=doc_type,
        size=size)['hits']['hits']


def create_index_and_wait(es, index, settings=None):
    """Create a new index, and wait for all shards to become ready."""
    
    #MLS FIXME - seems to be correctly creating index, even though flagging as error 
    try:
        es.create_index(index, settings=settings)
    except ElasticHttpError:
        pass
        
    es.health(index=index,
              wait_for_status='yellow',
#              wait_for_no_relocating_shards='true',  # wait for all
              timeout='5m')
    

    # curl -XPUT 'http://localhost:9200/_all/_settings?preserve_existing=true' -d '{
    # "index.max_result_window" : "2147483647"
    #}'
    es.update_all_settings({'index':{'max_result_window':2147483647 }})


def sources(search_results):
    """Return just the _source attributes of some ES search results."""
    return [r['_source'] for r in search_results]
