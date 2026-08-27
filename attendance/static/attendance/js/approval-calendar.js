(function(){
 const modal=document.getElementById('approval-day-modal'); if(!modal)return;
 const close=document.getElementById('approval-modal-close'), title=document.getElementById('approval-modal-title'), meta=document.getElementById('approval-modal-meta'), status=document.getElementById('approval-modal-status'), hours=document.getElementById('approval-modal-hours'), note=document.getElementById('approval-modal-note'), reasonWrap=document.getElementById('approval-modal-reason-wrap'), reason=document.getElementById('approval-modal-reason'), actions=document.getElementById('approval-modal-actions');
 const csrf=(window.CSRF_TOKEN||'').trim() || ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)||[])[1]||'');
 function actionUrl(template,id){return (template||'').replace('/0/','/'+id+'/');}
 function addHidden(form,name,value){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.appendChild(input);}
 function open(c){
  title.textContent='روز '+c.dataset.jalali;
  meta.textContent='معادل میلادی: '+c.dataset.gregorian;
  status.textContent=c.dataset.status||'ثبت نشده';
  hours.textContent=c.dataset.hours?c.dataset.hours+' ساعت':'—';
  note.textContent=c.dataset.note||'یادداشتی ثبت نشده است';
  reason.textContent=c.dataset.reason||'—';
  reasonWrap.style.display=c.dataset.reason?'block':'none';
  actions.innerHTML='';
  if(c.dataset.recordId && c.dataset.approval==='pending' && window.CAN_APPROVE){
   const approve=document.createElement('form');
   approve.method='post'; approve.action=actionUrl(window.APPROVE_URL_TEMPLATE,c.dataset.recordId);
   addHidden(approve,'csrfmiddlewaretoken',csrf);
   const approveBtn=document.createElement('button'); approveBtn.type='submit'; approveBtn.className='approve-btn'; approveBtn.textContent='✓ تایید این روز'; approve.appendChild(approveBtn); actions.appendChild(approve);
   const reject=document.createElement('form');
   reject.method='post'; reject.action=actionUrl(window.REJECT_URL_TEMPLATE,c.dataset.recordId);
   addHidden(reject,'csrfmiddlewaretoken',csrf);
   const reasonInput=document.createElement('input'); reasonInput.name='reason'; reasonInput.placeholder='دلیل رد (اختیاری)'; reject.appendChild(reasonInput);
   const rejectBtn=document.createElement('button'); rejectBtn.type='submit'; rejectBtn.className='reject-btn'; rejectBtn.textContent='رد روز'; reject.appendChild(rejectBtn); actions.appendChild(reject);
  } else if(c.dataset.approval){
   const state=document.createElement('span'); state.className='approval-state '+c.dataset.approval; state.textContent=c.dataset.approvalDisplay||'وضعیت ثبت شده'; actions.appendChild(state);
  }
  modal.classList.add('open'); document.body.classList.add('modal-open');
 }
 document.querySelectorAll('.approval-day:not(.empty)').forEach(c=>c.addEventListener('click',()=>open(c)));
 if(close)close.addEventListener('click',()=>{modal.classList.remove('open');document.body.classList.remove('modal-open')});
 modal.addEventListener('click',e=>{if(e.target===modal){modal.classList.remove('open');document.body.classList.remove('modal-open')}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){modal.classList.remove('open');document.body.classList.remove('modal-open')}});
})();
