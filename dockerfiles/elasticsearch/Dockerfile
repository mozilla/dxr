FROM elasticsearch:1.4

# Install the javascript plugin
RUN /usr/share/elasticsearch/bin/plugin -install elasticsearch/elasticsearch-lang-javascript/2.4.1

# copy into place per https://registry.hub.docker.com/u/library/elasticsearch/dockerfile/

ADD elasticsearch.yml /usr/share/elasticsearch/config/elasticsearch.yml
