/** @odoo-module **/

// Portal Customer Edit with Edit State Logic
document.addEventListener('DOMContentLoaded', function () {
    const editBtn = document.getElementById('editCustomerBtn');
    const cancelBtn = document.getElementById('cancelEditBtn');
    const viewMode = document.getElementById('customerViewMode');
    const editMode = document.getElementById('customerEditMode');

    if (editBtn && viewMode && editMode) {
        // Show edit mode
        editBtn.addEventListener('click', function () {
            viewMode.style.display = 'none';
            editMode.style.display = 'block';
            editBtn.style.display = 'none';

            // Scroll to top of form
            editMode.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        // Cancel edit - show view mode
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function () {
                viewMode.style.display = 'block';
                editMode.style.display = 'none';
                editBtn.style.display = 'inline-block';

                // Scroll back to top
                viewMode.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }
    }

    // Auto-dismiss success/info messages after 5 seconds
    const alerts = document.querySelectorAll('.alert-success, .alert-info');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.classList.remove('show');
            setTimeout(function () {
                alert.remove();
            }, 150);
        }, 5000);
    });

    // Confirm before requesting edit
    const requestEditForms = document.querySelectorAll('form[action*="/request_edit"]');
    requestEditForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm('Bạn có chắc muốn yêu cầu quyền chỉnh sửa khách hàng này?')) {
                e.preventDefault();
            }
        });
    });
});
