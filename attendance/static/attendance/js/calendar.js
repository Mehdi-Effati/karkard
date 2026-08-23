(function () {
  'use strict';

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  const csrftoken = getCookie('csrftoken');

  const overlay = document.getElementById('day-modal-overlay');
  const modalDateEl = document.getElementById('modal-date');
  const modalHolidayEl = document.getElementById('modal-holiday');
  const statusOptions = document.querySelectorAll('.status-opt');
  const hoursInput = document.getElementById('overtime-input');
  const noteInput = document.getElementById('note-input');
  const errorEl = document.getElementById('form-error');
  const saveBtn = document.getElementById('save-btn');
  const deleteBtn = document.getElementById('delete-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const statusHidden = document.getElementById('status-hidden');

  let currentDate = null;

  function resetForm() {
    statusOptions.forEach((el) => el.classList.remove('picked'));
    statusHidden.value = '';
    hoursInput.value = '';
    noteInput.value = '';
    errorEl.textContent = '';
  }

  function openModalForCell(cell) {
    currentDate = cell.dataset.date;
    resetForm();

    modalDateEl.textContent = cell.dataset.gdate;

    if (cell.dataset.holiday) {
      const kindLabel = cell.dataset.holidayKind === 'government' ? 'تعطیلی اعلامی دولت' : 'تعطیل رسمی';
      modalHolidayEl.textContent = '📌 ' + kindLabel + ': ' + cell.dataset.holiday;
      modalHolidayEl.style.display = 'block';
    } else {
      modalHolidayEl.style.display = 'none';
    }

    const existingStatus = cell.dataset.status;
    if (existingStatus) {
      statusHidden.value = existingStatus;
      statusOptions.forEach((el) => {
        if (el.dataset.value === existingStatus) el.classList.add('picked');
      });
    }
    if (cell.dataset.overtime) {
      hoursInput.value = cell.dataset.overtime;
    }
    if (cell.dataset.note) {
      noteInput.value = cell.dataset.note;
    }

    deleteBtn.style.display = cell.dataset.checked === '1' ? 'block' : 'none';

    overlay.classList.add('open');
  }

  function closeModal() {
    overlay.classList.remove('open');
    currentDate = null;
  }

  document.querySelectorAll('.day-check').forEach((checkbox) => {
    checkbox.addEventListener('click', (e) => {
      e.preventDefault();
      const cell = checkbox.closest('.day-cell');
      openModalForCell(cell);
    });
  });

  statusOptions.forEach((opt) => {
    opt.addEventListener('click', () => {
      const isPicked = opt.classList.contains('picked');
      statusOptions.forEach((el) => el.classList.remove('picked'));
      if (!isPicked) {
        opt.classList.add('picked');
        statusHidden.value = opt.dataset.value;
      } else {
        statusHidden.value = '';
      }
    });
  });

  cancelBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  function setLoading(btn, loadingText) {
    btn.dataset.originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = loadingText;
  }

  saveBtn.addEventListener('click', async () => {
    errorEl.textContent = '';
    const status = statusHidden.value;
    const hours = hoursInput.value.trim();
    const note = noteInput.value.trim();

    if (!status && !hours) {
      errorEl.textContent = 'حداقل یکی از وضعیت روز یا ساعت اضافه‌کاری را وارد کنید.';
      return;
    }

    setLoading(saveBtn, 'در حال ثبت...');

    try {
      const res = await fetch(SAVE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify({
          date: currentDate,
          status: status,
          overtime_hours: hours,
          note: note,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        errorEl.textContent = data.error || 'ثبت اطلاعات با خطا مواجه شد.';
        saveBtn.disabled = false;
        saveBtn.textContent = saveBtn.dataset.originalText;
        return;
      }
      // برای اینکه خلاصه ماه، یادآوری و کارکرد هم به‌روز شوند، صفحه را رفرش می‌کنیم
      window.location.reload();
    } catch (err) {
      errorEl.textContent = 'ارتباط با سرور برقرار نشد.';
      saveBtn.disabled = false;
      saveBtn.textContent = saveBtn.dataset.originalText;
    }
  });

  deleteBtn.addEventListener('click', async () => {
    if (!currentDate) return;
    setLoading(deleteBtn, 'در حال حذف...');
    try {
      const res = await fetch(DELETE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify({ date: currentDate }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        errorEl.textContent = data.error || 'حذف با خطا مواجه شد.';
        deleteBtn.disabled = false;
        deleteBtn.textContent = deleteBtn.dataset.originalText;
        return;
      }
      window.location.reload();
    } catch (err) {
      errorEl.textContent = 'ارتباط با سرور برقرار نشد.';
      deleteBtn.disabled = false;
      deleteBtn.textContent = deleteBtn.dataset.originalText;
    }
  });
})();
