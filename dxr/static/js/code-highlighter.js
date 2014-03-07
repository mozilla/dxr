/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

/**
 * Toggle the .highlighted class on a <code> element with aria-labelledby="num" attribute
 * where num is extracted from the <td id="line-numbers"><span id="num"> structure.
 * This mapping allows clicking on the line numbers spans without interfering with
 * the dynamically overlaid context-menu on each line.
 *
 * One major failing is that holding shift, selecting a group of lines, and then
 * and then selecting another line leads to a complete mess. Not sure what to do there.
 */

$(function () {
    'use strict';
    var container = $("#line-numbers");

    //bind to all span.line-number click events
    container.on("click", ".line-number", function (event) {
        var order = null,
            line = null,
            last_selected_num = null,
            //get the line number
            selected_num = $(this).attr('id'),
            selected = null,
            last_selected = $(".last-selected");

        //multiselect on shiftkey press and click
        if (event.shiftKey) {
            // on shift, find last-selected code element
            // if last_selected_num less than selected_num go back
            // else if last_selected_num greater than line id, go forward
            line = $("#" + selected_num);
            last_selected_num = last_selected.attr('id');

            if (last_selected_num === selected_num) {
                //toggle a single shiftclicked line
                line.removeClass("last-selected highlighted clicked");

            } else if (last_selected_num < selected_num) {
                //shiftclick descending down the page
                line.addClass("clicked");
                selected = $(".last-selected").nextUntil($(".clicked"));
                // on last element add last-selected class
                $(".line-number").removeClass("clicked highlighted");

            } else if (last_selected_num > selected_num) {
                //shiftclick ascending up the page
                $(".line-number").removeClass("highlighted clicked");
                line.addClass("clicked");
                selected = $(".clicked").nextUntil(last_selected);
            }

            selected.each(function () {
                selected.addClass("highlighted");
                var selected_code = $(this).html();
                if (selected_code === "") {
                    $(this).html("<br>");
                }
            });

            // since all highlighed items are stripped, add one back
            last_selected.addClass("highlighted");
            line.addClass("highlighted");

            var last_clicked_line = $(".clicked").attr('id');
            var last_selected_line = $(".last-selected").attr('id');
            console.log(last_clicked_line);
            console.log(last_selected_line);
            if (last_clicked_line) {
                window.location.hash = last_clicked_line + "-" + last_selected_line;
            } else {
                var last_highlighted_lines = $(".highlighted");
		var len_last_highlighted_lines = last_highlighted_lines.length - 1;
                var last_highlighted_line = last_highlighted_lines[len_last_highlighted_lines].id;
                window.location.hash = last_selected_line + "-" + last_highlighted_line;
            }
        } else {
            //single non-shift click toggle
            line = $("#" + selected_num);
            if (last_selected.attr('id') !== selected_num) {
                $(".highlighted").removeClass("last-selected highlighted");
                line.toggleClass("last-selected highlighted");

            } else {
                $(".highlighted").removeClass("last-selected highlighted");
            }

            if (line.text() === "") {
                line.html("<br>");
            }
            window.location.hash = line.attr('id');
        }

    });

    $(document).ready(function () {
        var hash = window.location.hash.replace("#", "");
        var lines = hash.split("-");

        //handle multi-line highlights
        if (lines.length > 1) {
            var start_line = lines[0];
            var end_line = lines[1];
            var selected = $("#" + start_line).nextUntil("#" + end_line);
            $("#" + start_line).addClass('highlighted');
            $("#" + end_line).addClass('highlighted');

            selected.each(function () {
                $(this).addClass('highlighted');
                var selected_code = $(this).html();
                if (selected_code === "") {
                    $(this).html("<br>");
                }
            });

        } else {
            //handle a single line highlight, 'lines' is one line number here
            var line = $("#" + lines);
            line.addClass('highlighted');
            if (line.text() === "") {
                line.html("<br>");
            }
        }
    });

});
