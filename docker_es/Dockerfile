FROM elasticsearch:1.5

RUN plugin install elasticsearch/elasticsearch-lang-javascript/2.7.0
RUN plugin install mobz/elasticsearch-head
# Modified configs.
COPY elasticsearch.yml /usr/share/elasticsearch/config/elasticsearch.yml
COPY elasticsearch.yml /etc/elasticsearch/elasticsearch.yml
# Add some memory.
RUN sed 's/#ES_HEAP_SIZE=.*/ES_HEAP_SIZE=3500m/' /etc/init.d/elasticsearch > /etc/init.d/elasticsearch
