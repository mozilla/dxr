$(function() {
    var trigger = $('.sf-select-trigger');
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
        $('.sf-select-options').hide();
    }

    /**
     * Update the query field with the selected filter.
     * @param {String} selectedFilter - The selected filter.
     */
    function setFilter(selectedFilter) {
        var queryField = $('#query');
        var value = queryField.val();

        value += ' ' + selectedFilter;
        queryField.val(value);
        queryField[0].focus();
    }

    // Show/Hide the options
    trigger.click(function(event) {
        event.stopPropagation();

        var optionsContainer = $('.sf-select-options');
        var expanded = optionsContainer.attr('aria-expanded');

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
        setFilter($(this).data('value'));

        hideOptions();
    });

    window.addEventListener('click', function() {
        hideOptions();
    }, false);

    window.addEventListener('keyup', function(event) {
        // 'key' is the standard but has not been implemented in Gecko
        // yet, see https://bugzilla.mozilla.org/show_bug.cgi?id=680830
        // so, we check both.
        var keyPressed = event.key || event.keyCode;
        // esc key pressed.
        if (keyPressed === 27 || keyPressed === 'Esc') {
           hideOptions();
        }
    }, false);
});
