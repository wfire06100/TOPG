/* Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0 */
(function(){
'use strict';
const cli='/data/adb/modules/COPG-VD/tee/tee_scheduler.sh';
const quote=s=>"'"+String(s).replace(/'/g,"'\\''")+"'";
let sequence=0,queue=Promise.resolve();
function run(action,value){
 const command='sh '+quote(cli)+' '+quote(action)+(value===undefined?'':' '+quote(value));
 const task=queue.then(()=>new Promise((resolve,reject)=>{
  const callback='topg_schedule_'+Date.now()+'_'+(++sequence);
  window[callback]=(code,out,err)=>{delete window[callback];if(String(code)==='0')resolve(out||'');else reject(new Error(err||out||'Schedule command failed'));};
  try{if(typeof ksu==='undefined'||typeof ksu.exec!=='function')throw new Error('Root bridge unavailable');ksu.exec(command,'{}',callback);}
  catch(e){delete window[callback];reject(e);}
 }));
 queue=task.catch(()=>undefined);return task;
}
function mount(){
 const get=id=>document.getElementById(id);
 const input=get('tee-interval'),save=get('tee-schedule-save'),refresh=get('tee-schedule-status'),output=get('tee-schedule-output'),panel=get('tee-tab');
 if(!input||!save||!refresh||!output||!panel)return false;
 if(input.dataset.scheduleReady)return true;
 input.dataset.scheduleReady='1';input.value='';input.disabled=true;
 let loaded=false,dirty=false,writing=false,generation=0;
 function controls(){input.disabled=writing||!loaded;save.setAttribute('aria-busy',String(writing));}
 function report(e){output.textContent=String(e);}
 async function read(force=false){
  if(!force&&(dirty||writing))return;
  const ticket=++generation;
  try{
   const raw=await run('status');
   if(ticket!==generation)return;
   const match=raw.match(/^interval_minutes=(\d+)\r?$/m),n=match?Number(match[1]):NaN;
   if(!Number.isInteger(n)||n<1||n>10080)throw new Error('Invalid saved schedule interval');
   loaded=true;output.textContent=raw;
   if(force||!dirty){input.value=String(n);dirty=false;}
  }catch(e){if(ticket===generation)report(e);}
  finally{controls();}
 }
 input.addEventListener('input',()=>{dirty=true;});
 refresh.onclick=()=>{if(!writing)return read(true);};
 save.onclick=async()=>{
  if(writing)return;
  const n=Number(input.value);
  if(!loaded||!Number.isInteger(n)||n<1||n>10080){report(new Error('Schedule must be loaded and contain 1–10080 minutes'));return;}
  writing=true;++generation;controls();
  try{await run('configure',n);await read(true);}
  catch(e){report(e);}
  finally{writing=false;controls();}
 };
 new MutationObserver(()=>{if(panel.classList.contains('active'))read();}).observe(panel,{attributes:true,attributeFilter:['class']});
 read();return true;
}
function start(){
 if(mount())return;
 const observer=new MutationObserver(()=>{if(mount())observer.disconnect();});
 observer.observe(document.body,{childList:true,subtree:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
