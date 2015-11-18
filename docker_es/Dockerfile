FROM elasticsearch:1.4

RUN plugin install elasticsearch/elasticsearch-lang-javascript/2.4.1
COPY elasticsearch.yml /etc/elasticsearch/elasticsearch.yml
# Add some memory:
RUN sed 's/#ES_HEAP_SIZE=.*/ES_HEAP_SIZE=2g/' /etc/init.d/elasticsearch > /etc/init.d/elasticsearch
