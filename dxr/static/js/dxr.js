/* jshint jquery:true, devel:true, esnext: true */
/* globals nunjucks: true */
$(function() {
    'use strict';

    var searchForm = $('#search'),
        constants = $('#data'),
        wwwroot = constants.data('root'),
        search = constants.data('search'),
        icons = wwwroot + '/static/icons/',
        views = wwwroot + '/static/views',
        additionalFields = $('.adv_additional');

    additionalFields.find('input[type="checkbox"]').each(function() {
        if($(this).prop('checked')) {
             $('#' + $(this).attr('data-field')).parents('.form_elem_container').show();
        }
    });

    if(!nunjucks.env) {
        nunjucks.env = new nunjucks.Environment(new nunjucks.HttpLoader(views));
    }

    var env = nunjucks.env,
        tmpl = env.getTemplate('results.html'),
        pathLineTmpl = env.getTemplate('path_line.html');

    function buildPathLine(fullPath, tree) {
        var pathLines = '',
            pathRoot = tree + '/source/',
            paths = fullPath.split('/'),
            splitPathLength = paths.length,
            dataPath = [];

        for(var path in paths) {
            // Do not add a / on the last iteration.
            var displayPath = (splitPathLength - 1) === path ? paths[path] : paths[path] + '/';

            dataPath.push(path);
            pathLines += pathLineTmpl.render({
                'data_path': dataPath.join('/'),
                'display_path': displayPath,
                'url': pathRoot + dataPath.join('/')
            });
        }

        return pathLines;
    }

    var showAdvanced = $('#show_advanced'),
        advSearchContainer = $('#advanced_search'),
        hidden = true;

    showAdvanced.on('click', function(event) {
        event.preventDefault();

        if(hidden) {
            advSearchContainer.show();
            hidden = false;
        } else {
            advSearchContainer.hide();
            hidden = true;
        }
    });

    additionalFields.on('click', 'input[type="checkbox"]', function() {
        var fieldID = $(this).attr('data-field');

        if($(this).prop('checked')) {
            $('#' + fieldID).parents('.form_elem_container').show();
        } else {
            $('#' + fieldID).parents('.form_elem_container').hide();
        }
    });

    searchForm.on('submit', function(event) {
        event.preventDefault();

        var params = searchForm.serialize(),
            ajaxURL = search + '?' + params,
            contentContainer = $('#content');

        $.getJSON(ajaxURL, function(data) {

            var results = data.results;

            for(var result in results) {
                results[result].pathLine = buildPathLine(results[result].path, data.tree);
                results[result].iconPath = icons + results[result].icon;
            }

            contentContainer.empty().append(tmpl.render(data));
        });
    });
});
