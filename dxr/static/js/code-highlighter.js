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
    var lines = $(".line-number");

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
            line = $("#line-" + selected_num);
            last_selected_num = last_selected.attr('aria-labelledby');

            if (last_selected_num === selected_num) {
                //toggle a single shiftclicked line
                line.removeClass("last-selected highlighted clicked");

            } else if (last_selected_num < selected_num) {
                //shiftclick descending down the page
                line.addClass("clicked");
                selected = $(".last-selected").nextUntil($(".clicked"));
                // on last element add last-selected class
                $("code").removeClass("clicked highlighted");
                selected.addClass("highlighted");
                // since all highlighed items are stripped, add one back
                last_selected.addClass("highlighted");
                line.addClass("highlighted");

            } else if (last_selected_num > selected_num) {
                //shiftclick ascending up the page
                $("code").removeClass("highlighted clicked");
                line.addClass("clicked");
                selected = $(".clicked").nextUntil(last_selected);
                selected.addClass("highlighted");
                last_selected.addClass("highlighted");
                line.addClass("highlighted");
            }

            selected.each(function () {
                var selected_code = $(this).html();
                if (selected_code === "") {
                    $(this).html("<br>");
                }
            });

        } else {
            //single non-shift click toggle
            line = $("#line-" + selected_num);
            if (last_selected.attr('aria-labelledby') !== selected_num) {
                $(".highlighted").removeClass("last-selected highlighted");
                line.toggleClass("last-selected highlighted");

            } else {
                $(".highlighted").removeClass("last-selected highlighted");
            }

            if (line.text() === "") {
                line.html("<br>");
            }

        }
        window.location.hash = line.attr('id');

    });
});
