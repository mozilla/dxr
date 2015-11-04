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

    //highlight a single line when its corresponding panel anchor is clicked
    $('.panel a').click(function(event) {
        var highlightLine = $(this.hash);
        $('.highlighted').removeClass('highlighted');
        //add highlighted class back to selected line only
        $(highlightLine).addClass('last-selected highlighted');
    });
});
