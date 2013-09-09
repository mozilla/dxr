/* jshint jquery:true, devel:true, esnext: true */
/* globals nunjucks: true */
$(function() {
    'use strict';

    var searchForm = $('#search'),
        constants = $('#data'),
        wwwroot = constants.data('root'),
        search = constants.data('search'),
        icons = wwwroot + '/static/icons/',
        views = wwwroot + '/static/views';

    if(!nunjucks.env) {
        nunjucks.env = new nunjucks.Environment(new nunjucks.HttpLoader(views));
    }

    var env = nunjucks.env,
        tmpl = env.getTemplate('results.html'),
        pathLineTmpl = env.getTemplate('path_line.html');

    function buildPathLine(fullPath, tree) {
        var pathLines = '',
            pathRoot = tree + '/source/',
            splitPath = fullPath.split('/'),
            splitPathLength = splitPath.length,
            paths = Iterator(splitPath),
            dataPath = [];

        for(let [i, path] in paths) {
            // Do not add a / on the last iteration.
            var displayPath = (splitPathLength - 1) === i ? path : path + '/';

            dataPath.push(path);
            pathLines += pathLineTmpl.render({
                'data_path': dataPath.join('/'),
                'display_path': displayPath,
                'url': pathRoot + dataPath.join('/')
            });
        }

        return pathLines;
    }

    searchForm.on('submit', function(event) {
        event.preventDefault();

        var params = searchForm.serialize(),
            ajaxURL = search + '?' + params,
            contentContainer = $('#content');

        $.getJSON(ajaxURL, function(data) {

            var results = Iterator(data.results);

            for(let [,result] in results) {
                result.pathLine = buildPathLine(result.path, data.tree);
                result.iconPath = icons + result.icon;
            }

            contentContainer.empty().append(tmpl.render(data));
        });
    });
});
