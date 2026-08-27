(function(){
  'use strict';
  const jm=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const wd=['ش','ی','د','س','چ','پ','ج'];
  const jd=[31,31,31,31,31,31,30,30,30,30,30,29], gd=[31,28,31,30,31,30,31,31,30,31,30,31];
  function leap(g){return g%4===0&&g%100!==0||g%400===0}
  function j2g(jy,jm,jd0){let jy2=jy-979,jm2=jm-1,jd2=jd0-1;let n=365*jy2+Math.floor(jy2/33)*8+Math.floor((jy2%33+3)/4);for(let i=0;i<jm2;i++)n+=jd[i];n+=jd2;let g=n+79,gy=1600+400*Math.floor(g/146097);g%=146097;if(g>=36525){g--;gy+=100*Math.floor(g/36524);g%=36524;if(g>=365)g++;}gy+=4*Math.floor(g/1461);g%=1461;if(g>=366){g--;gy+=Math.floor(g/365);g%=365;}let gm=1;for(let i=0;i<12;i++){let d=gd[i]+(i===1&&leap(gy)?1:0);if(g<d){gm=i+1;break}g-=d}return [gy,gm,g+1]}
  function g2j(gy,gm,gd0){let gy2=gy-1600,gm2=gm-1,day=365*gy2+Math.floor((gy2+3)/4)-Math.floor((gy2+99)/100)+Math.floor((gy2+399)/400);for(let i=0;i<gm2;i++)day+=gd[i];if(gm2>1&&leap(gy))day++;day+=gd0-1;let j=day-79,np=Math.floor(j/12053);j%=12053;let jy=979+33*np+4*Math.floor(j/1461);j%=1461;if(j>=366){jy+=Math.floor((j-1)/365);j=(j-1)%365}let jm0=0;for(;jm0<11&&j>=jd[jm0];jm0++)j-=jd[jm0];return [jy,jm0+1,j+1]}
  function ml(y,m){if(m<=6)return 31;if(m<=11)return 30;return j2g(y,12,30)[2]===30?30:29}
  function today(){const d=new Date();return g2j(d.getFullYear(),d.getMonth()+1,d.getDate())}
  function esc(v){return String(v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
  function normalizeDigits(v){return String(v).replace(/[۰-۹]/g,ch=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(ch)));}
  let activePicker = null;
  function closePicker(){ if(activePicker){activePicker.remove();activePicker=null;document.body.classList.remove('jalali-modal-open');} }
  function makePicker(input){
    if(input.dataset.jalaliReady)return; input.dataset.jalaliReady='1'; input.type='text'; input.readOnly=true;
    let t=today(), val=normalizeDigits(input.value||'').replace(/-/g,'/').split('/').map(Number); let y=val.length===3&&val[0]>=1200&&val[0]<=1600?val[0]:t[0], m=val.length===3&&val[1]>=1&&val[1]<=12?val[1]:t[1];
    input.addEventListener('click',()=>{
      closePicker(); const overlay=document.createElement('div'); overlay.className='jalali-modal-overlay';
      const box=document.createElement('div'); box.className='jalali-modal'; overlay.appendChild(box); document.body.appendChild(overlay); activePicker=overlay; document.body.classList.add('jalali-modal-open');
      const render=()=>{let html='<div class="jp-top"><div><span class="jp-caption">انتخاب تاریخ</span><b>'+jm[m-1]+' '+y+'</b></div><button type="button" class="jp-close">×</button></div><div class="jp-head"><button type="button" data-prev>‹</button><b>'+jm[m-1]+' '+y+'</b><button type="button" data-next>›</button></div><div class="jp-wd">'+wd.map(x=>'<span>'+x+'</span>').join('')+'</div><div class="jp-days">'; let g=j2g(y,m,1), py=new Date(g[0],g[1]-1,g[2]).getDay(); let f=py===6?0:py===0?1:py===1?2:py===2?3:py===3?4:py===4?5:6; for(let i=0;i<f;i++)html+='<span></span>'; for(let d=1;d<=ml(y,m);d++)html+='<button type="button" data-day="'+d+'">'+d+'</button>'; html+='</div><div class="jp-footer"><button type="button" class="jp-today">امروز</button><button type="button" class="jp-cancel">انصراف</button></div>'; box.innerHTML=html;
        box.querySelector('.jp-close').onclick=closePicker; box.querySelector('.jp-cancel').onclick=closePicker; box.querySelector('.jp-today').onclick=()=>{let z=today();y=z[0];m=z[1];input.value=y+'/'+String(m).padStart(2,'0')+'/'+String(z[2]).padStart(2,'0');closePicker()}; box.querySelector('[data-prev]').onclick=()=>{m--;if(m<1){m=12;y--}render()}; box.querySelector('[data-next]').onclick=()=>{m++;if(m>12){m=1;y++}render()}; box.querySelectorAll('[data-day]').forEach(b=>b.onclick=()=>{input.value=y+'/'+String(m).padStart(2,'0')+'/'+String(b.dataset.day).padStart(2,'0');closePicker()}); };
      val=normalizeDigits(input.value||'').replace(/-/g,'/').split('/').map(Number); if(val.length===3&&val[0]>=1200&&val[0]<=1600){y=val[0];m=val[1]} render();
    });
  }
  function init(){document.querySelectorAll('.jalali-date-input').forEach(makePicker);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
