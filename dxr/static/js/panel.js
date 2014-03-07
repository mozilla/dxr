$(function() {
    /**
     * Toggles the ARIA expanded and hidden attributes' state.
     *
     * @param Object elem The element on which to toggle the attribute.
     */
    function toggleAria(elem) {
        var expandedState = elem.attr('aria-expanded') === 'true' ? 'false' : 'true';
        var hiddenState = elem.attr('aria-hidden') === 'true' ? 'false' : 'true';
        elem.attr('aria-hidden', hiddenState);
        elem.attr('aria-expanded', expandedState);
    }

    $('#panel-toggle').click(function(event) {
        var panelContent = $('#panel-content');
        var icon = $('.navpanel-icon', this);

        icon.toggleClass('expanded');
        panelContent.toggle();
        toggleAria(panelContent);
    });

    $('#panel-content a.class').click(function (event) {
        $(".highlighted").removeClass("highlighted");
        var highlighted_line = $(this).attr('href').replace('#', '');
        $("#" + highlighted_line).addClass("highlighted");
    });
});
