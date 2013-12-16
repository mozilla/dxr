$(function() {
    var selectTrigger = $('.ts-select-trigger');
    var options = $('.ts-options');

    function setSelectedItem(selected) {
        var items = options.find('a');

        items.each(function() {
            $(this).removeClass('selected')
                   .removeAttr('aria-checked');
        });

        selected.addClass('selected');
        selected.attr('aria-checked', 'true');
    }

    function hideOptions() {
        options.parents('.select-options').hide();
    }

    // Show/Hide the options
    selectTrigger.on('click', function(event) {
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
            $('.ts-options', optionsContainer)[0].focus();
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
