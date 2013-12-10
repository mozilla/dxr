$(function() {
    var panelToggle = $('#panel-toggle');

    /**
     * Toggles the ARIA expanded and hidden attributes' state.
     *
     * @param Object elem The element on which to toggle the attribute.
     */
    function toggleAria(elem) {
        var expandedState = elem.attr('aria-expanded') === 'true' ? 'false' : 'true';
        var hiddenState = elem.attr('aria-hidden') === 'true' ? 'false' : 'true';
        elem.attr('aria-hidden', state);
        elem.attr('aria-expanded', state);
    }

    panelToggle.click(function(event) {
        var panelContent = $(this).next();
        var icon = $('.navpanel-icon', this);

        icon.toggleClass('expanded');
        panelContent.slideToggle();
        toggleAria(panelContent);
    });
});
