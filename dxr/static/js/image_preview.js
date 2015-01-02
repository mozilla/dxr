$(function() {
    'use strict';

    /**
     * Replace 'source' with 'images' in href, and set that to the background-image
     */
    function setBackgroundImageFromLink(anchorElement) {
        var href = anchorElement.getAttribute('href');
        // note: breaks if the tree's name is "source"
        var bg_src = href.replace('source', 'images');
        anchorElement.style.backgroundImage = 'url(' + bg_src + ')';
    }

    window.addEventListener('load', function() {
        $(".image").each(function() {
            setBackgroundImageFromLink(this);
        });
    });
});
