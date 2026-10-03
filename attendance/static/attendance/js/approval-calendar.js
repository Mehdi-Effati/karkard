(function () {
  'use strict';

  const modal = document.getElementById('approval-overview-modal');
  const list = document.getElementById('approval-overview-list');
  const title = document.getElementById('approval-overview-title');
  const meta = document.getElementById('approval-overview-meta');
  const close = document.getElementById('approval-overview-close');
  const dataEl = document.getElementById('approval-days-data');
  if (!modal || !list || !dataEl) return;

  const days = JSON.parse(dataEl.textContent || '[]');
  const csrf = (window.CSRF_TOKEN || '').trim() || ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const approveTemplate = window.APPROVE_URL_TEMPLATE || '';
  const rejectTemplate = window.REJECT_URL_TEMPLATE || '';

  function actionUrl(template, id) {
    return (template || '').replace('/0/', '/' + id + '/');
  }

  function openModal(day) {
    title.textContent = 'روز ' + day.jalali_date;
    meta.textContent = 'معادل میلادی: ' + day.gregorian;
    renderRows(day);
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function statusClass(status) {
    return ({
      work: 'shift-work',
      night: 'shift-night',
      holiday_work: 'shift-holiday',
      friday_work: 'shift-friday',
      leave: 'shift-leave',
      off: 'shift-off'
    })[status] || 'shift-off';
  }

  function approvalLabel(record) {
    if (record.approval_status === 'approved') return '<span class="person-approval approved">✓ تایید شده</span>';
    if (record.approval_status === 'rejected') return '<span class="person-approval rejected">! رد شده</span>';
    return '<span class="person-approval pending">در انتظار تایید</span>';
  }

  function renderRows(day) {
    list.innerHTML = '';
    if (!day.records.length) {
      list.innerHTML = '<div class="approval-no-records">برای این روز هنوز هیچ کارکردی توسط کارکنان ثبت نشده است.</div>';
      return;
    }

    day.records.forEach(function (record) {
      const row = document.createElement('div');
      row.className = 'approval-person-row ' + statusClass(record.status);
      row.dataset.recordId = record.id;
      row.innerHTML =
        '<div class="approval-person-main">' +
          '<strong>' + escapeHtml(record.employee) + '</strong>' +
          '<small>@' + escapeHtml(record.username) + '</small>' +
        '</div>' +
        '<div class="approval-person-shift">' +
          '<b>' + escapeHtml(record.status_display) + '</b>' +
          (record.overtime_hours ? '<span>' + escapeHtml(record.overtime_hours) + ' ساعت اضافه‌کاری</span>' : '') +
          (record.note ? '<span>' + escapeHtml(record.note) + '</span>' : '') +
        '</div>' +
        '<div class="approval-person-action">' + approvalLabel(record) + '</div>' +
        '<div class="approval-person-buttons"></div>';

      const buttons = row.querySelector('.approval-person-buttons');
      if (window.CAN_APPROVE && record.approval_status === 'pending') {
        const approve = document.createElement('button');
        approve.type = 'button';
        approve.className = 'approve-btn';
        approve.textContent = '✓ تایید';
        approve.addEventListener('click', function () { updateRecord(day, record, 'approve', row, approve); });
        buttons.appendChild(approve);
      }

      // حتی بعد از تایید هم مدیر می‌تواند متوجه اشتباه شود و همان کارکرد را
      // از حالت تایید خارج کرده و رد کند.
      if (window.CAN_APPROVE && (record.approval_status === 'pending' || record.approval_status === 'approved')) {
        const reject = document.createElement('button');
        reject.type = 'button';
        reject.className = 'reject-btn';
        reject.textContent = record.approval_status === 'approved' ? 'لغو تایید و رد' : 'رد';
        reject.addEventListener('click', function () { rejectRecord(day, record, row, reject); });
        buttons.appendChild(reject);
      }
      list.appendChild(row);
    });
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      },
      body: new URLSearchParams(body).toString()
    });
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok || !data.ok) throw new Error(data.error || 'عملیات انجام نشد.');
    return data;
  }

  function finishRow(day, record, row, status, reason) {
    record.approval_status = status;
    record.approval_status_display = status === 'approved' ? 'تایید شده' : (status === 'rejected' ? 'رد شده' : 'در انتظار تایید');
    record.rejection_reason = reason || '';
    row.querySelector('.approval-person-action').innerHTML = approvalLabel(record);
    row.querySelector('.approval-person-buttons').innerHTML = '';
    updateDayState(day);
  }

  async function updateRecord(day, record, action, row, button) {
    button.disabled = true;
    button.textContent = '...';
    try {
      const data = await post(actionUrl(approveTemplate, record.id), {});
      finishRow(day, record, row, data.approval_status, '');
    } catch (err) {
      button.disabled = false;
      button.textContent = '✓ تایید';
      alert(err.message);
    }
  }

  async function rejectRecord(day, record, row, button) {
    const reason = prompt('دلیل رد کارکرد را وارد کنید:', record.rejection_reason || 'نیاز به بررسی مجدد دارد.');
    if (reason === null) return;
    button.disabled = true;
    button.textContent = '...';
    try {
      const data = await post(actionUrl(rejectTemplate, record.id), { reason: reason });
      finishRow(day, record, row, data.approval_status, data.rejection_reason || reason);
    } catch (err) {
      button.disabled = false;
      button.textContent = 'رد';
      alert(err.message);
    }
  }

  function updateDayState(day) {
    if (day.state === 'future' || !day.records.length) return;
    const pending = day.records.filter(function (record) { return record.approval_status !== 'approved'; }).length;
    day.count = pending;
    day.state = pending ? 'pending' : 'approved';
    const cell = document.querySelector('.approval-overview-day[data-day-index="' + days.indexOf(day) + '"]');
    if (!cell) return;
    cell.classList.remove('state-approved', 'state-pending', 'state-unregistered', 'state-future');
    cell.classList.add('state-' + day.state);
    const small = cell.querySelector('small');
    if (small) {
      small.className = pending ? 'day-pending-count' : 'day-state-label';
      small.textContent = pending ? String(pending) : 'تایید شده';
    }
    const totalPending = days.reduce(function (sum, d) { return sum + (d.count || 0); }, 0);
    const totalEl = document.querySelector('.approval-total b');
    if (totalEl) totalEl.textContent = totalPending;
  }

  document.querySelectorAll('.approval-overview-day').forEach(function (cell) {
    cell.addEventListener('click', function () {
      const day = days[Number(cell.dataset.dayIndex)];
      if (day) openModal(day);
    });
  });

  if (close) close.addEventListener('click', closeModal);
  modal.addEventListener('click', function (event) { if (event.target === modal) closeModal(); });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeModal(); });
})();
