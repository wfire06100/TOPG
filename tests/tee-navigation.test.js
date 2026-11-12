/* Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('module/webroot/scripts.js', 'utf8');
const tabs = ['about', 'devices', 'spoofing', 'system', 'tools', 'tee'];
function extract(name) {
 const start = source.indexOf('function '+name+'(');
 assert.notEqual(start,-1,name+' missing');
 const end = source.indexOf('\n}',start);
 assert.ok(end>start,name+' incomplete');
 return source.slice(start,end+2);
}
function fixture() {
 const nodes = new Map(), frames = new Map(), listeners = {}, pushes = [];
 let sequence = 0;
 function node(active=false) {
  const classes = new Set(active ? ['active'] : []);
  return {style:{display:active?'block':'none',opacity:active?'1':'0'},value:'draft',offsetHeight:100,
   classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k),
    toggle(k,on){if(on===undefined)on=!classes.has(k);if(on)classes.add(k);else classes.delete(k);}}};
 }
 for(const id of tabs){nodes.set(id+'-tab',node(id==='about'));nodes.set('tab-'+id,node(id==='about'));}
 nodes.set('device-savebar',node());
 const calls={devices:0,tools:0};
 const context={activeOutput:null,navFromPop:false,
  document:{getElementById:id=>nodes.get(id)||null,
   querySelectorAll:()=>tabs.map(id=>nodes.get('tab-'+id)).filter(n=>n.classList.contains('active'))},
  requestAnimationFrame(fn){const id=++sequence;frames.set(id,fn);return id;},
  cancelAnimationFrame:id=>frames.delete(id),setTimeout:fn=>fn(),
  renderDeviceList:()=>calls.devices++,checkRebootPending:()=>calls.tools++,visibleOverlays:()=>[],
  window:{addEventListener:(name,fn)=>listeners[name]=fn},
  history:{pushState:state=>pushes.push(state.tab),replaceState:()=>{}}};
 vm.createContext(context);
 vm.runInContext(['switchTab','currentTabId','setupBackNav'].map(extract).join('\n'),context);
 function flush(){for(const [id,fn] of Array.from(frames)){frames.delete(id);fn();}}
 return {context,nodes,frames,listeners,pushes,calls,flush};
}
function check(f,id) {
 assert.equal(f.context.currentTabId(),id);
 for(const tab of tabs){
  const panel=f.nodes.get(tab+'-tab'),selected=tab===id;
  assert.equal(panel.classList.contains('active'),selected,tab+' active');
  assert.equal(panel.style.display,selected?'block':'none',tab+' display');
  assert.equal(f.nodes.get('tab-'+tab).classList.contains('active'),selected,tab+' button');
 }
 assert.equal(f.nodes.get(id+'-tab').style.opacity,'1');
 assert.equal(f.nodes.get(id+'-tab').style.transform||'translateX(0)','translateX(0)');
 assert.equal(f.nodes.get('tee-tab').value,'draft');
}
if(process.argv.includes('--expect-bug')){
 const f=fixture();
 for(const tab of tabs){f.nodes.get(tab+'-tab').classList.toggle('active',tab==='tee');f.nodes.get('tab-'+tab).classList.toggle('active',tab==='tee');}
 f.context.switchTab('tools');f.flush();
 assert.equal(tabs.filter(id=>f.nodes.get(id+'-tab').classList.contains('active')).length,2);
 console.log('PASS baseline: original controller leaves TEE active below another panel.');
}else{
 for(const from of tabs)for(const to of tabs){const f=fixture();f.context.switchTab(from);f.flush();f.context.switchTab(to);f.flush();check(f,to);}
 const fast=fixture();for(const id of ['tools','tee','devices','system','tee'])fast.context.switchTab(id);
 assert.equal(fast.frames.size,1);fast.flush();check(fast,'tee');
 const back=fixture();back.context.setupBackNav();back.context.switchTab('tee');back.flush();
 const count=back.pushes.length;back.listeners.popstate({state:{tab:'tools'}});back.flush();check(back,'tools');
 assert.equal(back.pushes.length,count);back.listeners.popstate({state:{tab:'tee'}});back.flush();check(back,'tee');
 assert.equal(back.pushes.length,count);
 const callback=fs.readFileSync('module/webroot/tee/tee.js','utf8');
 assert.ok(callback.includes("btn.addEventListener('click',()=>{switchTab('tee');act(status);});"));
 assert.ok(!callback.includes('stopImmediatePropagation'));
 console.log('PASS: 36 tab pairs; rapid transitions; back navigation; single visible panel; draft retained; unified TEE handler.');
}
