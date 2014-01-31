$(function() {
    var contentContainer = $('#content');
    var options = $('.selector-options');

    /**
     * Mark the selected element as checked.
     * @param {Object} selected - The item to mark as checked.
     */
    function setSelectedItem(selected) {
        var items = options.find('a');

        items.each(function() {
            $(this).removeClass('selected')
                   .removeAttr('aria-checked');
        });

        selected.addClass('selected');
        selected.attr('aria-checked', 'true');
    }

    /**
     * Hide the current selector's options.
     */
    function hideOptions() {
        // Because the tree selector can be injected by a JS
        // template, we need to use the selector directly here,
        // as the element will not exist on DOM ready.
        $('.select-options').hide();
    }

    // Show/Hide the options
    contentContainer.on('click', '.ts-select-trigger', function(event) {
        event.stopPropagation();

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

    options.on('click', 'a', function(event) {
        event.stopPropagation();
        setSelectedItem($(this));
        // Set the value of the relevant hidden type element to
        // the selected value.
        $('#ts-value').val($(this).text());
        hideOptions();
    });

    window.addEventListener('click', hideOptions, false);

    onEsc(function() {
        $('.select-options').hide();
    });
});
