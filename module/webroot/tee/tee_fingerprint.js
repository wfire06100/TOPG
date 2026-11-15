/* Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0 */
(function(){
'use strict';
let serial=0;
const quote=s=>"'"+String(s).replace(/'/g,"'\\''")+"'";
function run(action,value){return new Promise((resolve,reject)=>{
 const cb='topg_fp_'+Date.now()+'_'+(++serial);
 window[cb]=(code,out,err)=>{delete window[cb];String(code)==='0'?resolve(out||''):reject(new Error(err||out||t('fp_error')));};
 try{ksu.exec('sh /data/adb/modules/COPG-VD/tee/tee_fingerprint_scheduler.sh '+quote(action)+(value===undefined?'':' '+quote(value)),'{}',cb);}catch(e){delete window[cb];reject(e);}
});}
function mount(){
 const panel=document.getElementById('tee-tab');if(!panel)return false;
 if(document.getElementById('fp-schedule'))return true;
 const box=document.createElement('section');box.id='fp-schedule';box.className='card';box.style.padding='16px';
 box.innerHTML='<h3 data-i18n="fp_title"></h3><label for="fp-minutes" data-i18n="fp_interval"></label> <button type="button" class="info-btn-item" data-info-button aria-label="Info">?</button><input id="fp-minutes" type="number" min="0" max="10080" step="1" value="0" disabled><small data-i18n="fp_hint"></small><p data-state></p><button type="button" class="action-btn" data-save data-i18n="fp_save"></button><pre data-output style="white-space:pre-wrap"></pre><dialog data-help class="card"><p data-i18n="fp_help"></p><button type="button" data-close data-i18n="fp_close"></button></dialog>';
 panel.append(box);I18N.apply(box);
 const q=s=>box.querySelector(s),input=q('input'),output=q('[data-output]');let busy=false,loaded=false;
 function controls(){input.disabled=busy||!loaded;box.querySelectorAll('button:not([data-info-button]):not([data-close])').forEach(b=>b.disabled=busy||!loaded);}
 async function read(){
  const raw=await run('status'),s={};for(const line of raw.split('\n')){const i=line.indexOf('=');if(i>0)s[line.slice(0,i)]=line.slice(i+1);}
  if(!/^\d+$/.test(s.minutes||'')||Number(s.minutes)>10080)throw new Error(t('fp_error'));
  input.value=s.minutes;loaded=true;
  const date=v=>Number(v)>0?new Date(Number(v)*1000).toLocaleString():t('fp_none');
  q('[data-state]').textContent=Number(s.minutes)===0?t('fp_disabled'):t('fp_next')+' '+date(s.next);
  if(s.last)q('[data-state]').textContent+=' · '+t('fp_last')+' '+date(s.last)+' · '+(s.result==='0'?t('fp_ok'):t('fp_error'));
 }
 async function act(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){output.textContent=t('fp_error')+': '+String(e.message||e);}finally{busy=false;controls();}}
 q('[data-save]').onclick=()=>act(async()=>{const n=input.value;if(!/^(0|[1-9]\d*)$/.test(n)||Number(n)>10080)throw new Error(t('fp_invalid'));await run('configure',n);await read();output.textContent=t('fp_saved');});
 const dialog=q('[data-help]');q('[data-info-button]').onclick=()=>{I18N.apply(dialog);dialog.showModal();};q('[data-close]').onclick=()=>dialog.close();
 controls();act(read);return true;
}
function start(){if(mount())return;const o=new MutationObserver(()=>{if(mount())o.disconnect();});o.observe(document.body,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
