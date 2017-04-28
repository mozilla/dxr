$(function() {
    var contentContainer = $('.nav-bar');

    // Show/Hide the options
    contentContainer.on('click', '.ts-select-trigger', function(event) {

        var optionsFilter = $('.options-filter');
        var optionsContainer = $('.tree-selector').find('.select-options');
        var expanded = optionsContainer.attr('aria-expanded');

        // Show or hide the filter field if active.
        if (optionsFilter.data('active')) {
            optionsFilter.toggle();
        }

        optionsContainer.toggle();

        // Update ARIA expanded state
        optionsContainer.attr('aria-expanded', expanded === 'false' ? 'true' : 'false');
        // Move focus to options container if expanded
        if (expanded === 'false') {
            $('.selector-options', optionsContainer)[0].focus();
        }
    });

    // Hide the options if anything outside the options or trigger box is
    // clicked.
    $(document.documentElement).on('mousedown', function(event) {
        if ($(event.target).is(':not(.ts-select-trigger, ' +
                                    '.select-options, .select-options *)')) {
            $('.select-options').hide();
        }
    });

    contentContainer.on('click', '.selector-options tr', function(event) {
        event.stopPropagation();
        window.location = $(this).data('href');
    });

    onEsc(hideOptionsAndHelp);
});
