document.addEventListener('DOMContentLoaded', function() {
    var select = document.getElementById('forecast-provider-type');
    if (!select) return;

    function update_provider_visibility() {
        var type = select.value;
        document.querySelectorAll('.provider-config').forEach(function(el) {
            el.style.display = 'none';
        });
        if (type) {
            var target = document.getElementById('provider-config-' + type.replace('_', '-'));
            if (target) target.style.display = '';
        }
    }

    select.addEventListener('change', update_provider_visibility);
    update_provider_visibility();
});
