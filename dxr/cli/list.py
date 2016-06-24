from click import command, echo, secho
from itertools import izip
from pyelasticsearch import ElasticSearch
from tabulate import tabulate

from dxr.cli.utils import config_option
from dxr.config import FORMAT
from dxr.es import TREE, sources


@command()
@config_option
def list(config):
    """List the indices the catalog knows about, with metadata.

    Dangling index pointers are conspicuously pointed out.

    """
    secho('Current format: %s' % FORMAT, fg='green')
    echo('Catalog: %s\n' % config.es_catalog_index)

    es = ElasticSearch(config.es_hosts)
    query = {
        'query': {
            'match_all': {}
        },
        'sort': ['name', 'format']
    }
    catalog_docs = sources(es.search(query,
                                     index=config.es_catalog_index,
                                     doc_type=TREE,
                                     size=10000)['hits']['hits'])
    aliases = alias_to_index_map(es, [d['es_alias'] for d in catalog_docs])

    lines = []
    colors = []
    for d in catalog_docs:
        index_missing = d['es_alias'] not in aliases
        colors.append('red' if index_missing else
                      ('green' if d['format'] == FORMAT else None))
        lines.append([d['name'],
                      d['format'],
                      d['es_alias'],
                      'MISSING!' if index_missing else aliases[d['es_alias']],
                      d['generated_date']])
    table = tabulate(lines, headers=['Name', 'Format', 'Alias', 'Index', 'Generated'], tablefmt='simple').splitlines()
    echo(table[0])
    echo(table[1])
    for line, color in izip(table[2:], colors):
        secho(line, fg=color)


def alias_to_index_map(es, aliases):
    results = es.get_aliases(alias=aliases)
    aliases = {}  # alias -> index
    for index, obj in results.iteritems():
        for alias in obj['aliases']:
            # Doesn't handle aliases pointing to more than one index, because
            # that shouldn't happen. The last one will win for now.
            aliases[alias] = index
    return aliases
