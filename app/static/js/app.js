document.addEventListener('DOMContentLoaded', function () {
  const deleteButtons = document.querySelectorAll('.delete-btn');
  deleteButtons.forEach(function (button) {
    button.addEventListener('click', function (event) {
      const confirmed = window.confirm('ยืนยันการลบข้อมูลหรือไม่?');
      if (!confirmed) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) {
        submitButton.classList.add('is-loading');
        submitButton.disabled = true;
      }
    });
  });

  const alertList = document.querySelectorAll('.alert');
  alertList.forEach(function (alert) {
    setTimeout(function () {
      if (alert && alert.parentNode) {
        alert.classList.remove('show');
        alert.classList.add('fade');
        setTimeout(function () {
          alert.remove();
        }, 250);
      }
    }, 4000);
  });
});
