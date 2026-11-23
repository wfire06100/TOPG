// Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0
// TOPG module UI. Keep the public surface stable; see README.md for usage.
// This file is intentionally framework-free: it is loaded as a plain browser script.
'use strict';
let state=null;
let pendingReset=null;
function el(tag,attrs={},text=''){
 const node=document.createElement(tag);
 for(const [key,value] of Object.entries(attrs)){
  if(key==='class'){node.className=value;}
  else if(key==='style'){Object.assign(node.style,value);}
  else if(key==='text'){node.textContent=value;}
  else if(key==='onclick'){node.addEventListener('click',value);}
  else{node.setAttribute(key,value);}
 }
 if(text){node.textContent=text;}
 return node;
}
function card(title,subtitle=''){
 const root=el('section',{class:'card'});
 const head=el('div',{class:'card-head'});
 head.append(el('h2',{class:'card-title',text:title}));
 if(subtitle){head.append(el('div',{class:'card-sub',text:subtitle}));}
 root.append(head);
 return root;
}
function actions(...nodes){
 const wrap=el('div',{class:'actions'});
 wrap.append(...nodes.filter(Boolean));
 return wrap;
}
function badge(text,tone='muted'){
 return el('span',{class:'badge badge-'+tone,text});
}
function kv(label,value,tone='muted'){
 const row=el('div',{class:'kv'});
 row.append(el('span',{class:'kv-label',text:label}));
 row.append(el('span',{class:'kv-value kv-'+tone,text:value}));
 return row;
}
function pre(text){
 return el('pre',{class:'mono',text:text||'(empty)'});
}
function render(root,data){
 state=data;
 root.replaceChildren();
 const status=card('TOPG','TEE attestation status');
 status.append(kv('Device',data.device||'unknown'));
 status.append(kv('Android',data.android||'unknown'));
 status.append(kv('Build',data.build||'unknown'));
 status.append(kv('State',data.state||'unknown',data.state==='ok'?'ok':'warn'));
 root.append(status);
 const checks=card('Checks','Local TEE verification');
 for(const c of data.checks||[]){
  checks.append(kv(c.label||'Check',c.value||'unknown',c.tone||'muted'));
 }
 root.append(checks);
 const diag=card('Diagnostics','Local diagnostics and recovery');
 const notice=el('div',{class:'notice',role:'note'});
 notice.append(el('strong',{text:'Boot hash reset'}));
 notice.append(el('p',{text:'Use if ro.boot.vbmeta.digest and verifiedBootHash mismatch. After reset, reset the key in Attestation Key and run a new attestation.'}));
 diag.append(notice);
 const reset=el('button',{id:'tee-reset',class:'btn danger',type:'button',text:'Reset boot hash',onclick:()=>showResetConfirm(diag)});
 reset.style.width='100%';
 reset.style.background='#ff9800';
 reset.style.color='#111';
 diag.append(actions(reset));
 const feedback=el('div',{id:'tee-reset-feedback',class:'notice',role:'status','aria-live':'polite'});
 feedback.hidden=true;
 diag.append(feedback);
 root.append(diag);
 const logs=card('Logs','Recent TOPG events');
 logs.append(pre(data.logs||''));
 root.append(logs);
}
function showResetConfirm(diag){
 if(pendingReset){pendingReset.remove();pendingReset=null;}
 const panel=el('div',{class:'notice'});
 panel.append(el('p',{text:'Delete the stored boot hash?'}));
 const row=actions(
  el('button',{class:'btn',type:'button',text:'Cancel',onclick:()=>{panel.remove();pendingReset=null;}}),
  el('button',{class:'btn danger',type:'button',text:'Confirm',onclick:()=>doReset(panel)})
 );
 panel.append(row);
 diag.insertBefore(panel,document.getElementById('tee-reset-feedback'));
 pendingReset=panel;
}
function doReset(panel){
 const feedback=document.getElementById('tee-reset-feedback');
 feedback.hidden=false;
 feedback.textContent='Working...';
 ksu.exec('rm -f /data/adb/topg/boot_hash.bin','',(code,stdout,stderr)=>{
  if(code===0){feedback.textContent='Boot hash reset.';}
  else{feedback.textContent='Reset failed: '+(stderr||stdout||('exit '+code));}
  panel.remove();pendingReset=null;
 });
}
function boot(root){
 if(!root){return;}
 const data={device:'unknown',android:'unknown',build:'unknown',state:'unknown',checks:[],logs:''};
 render(root,data);
}
if(typeof module!=='undefined'&&module.exports){module.exports={render,boot};}
