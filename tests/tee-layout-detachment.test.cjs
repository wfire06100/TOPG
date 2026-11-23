// Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0
// Targeted regression test for the TOPG TEE diagnostics UI.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../module/webroot/tee/tee_layout.js'),'utf8');
for(const marker of [
 "const diag=card('Diagnostics'",
 "'Reset boot hash'",
 "ro.boot.vbmeta.digest and verifiedBootHash mismatch",
 "showResetConfirm(diag)",
 "'Delete the stored boot hash?'",
 "'Confirm'",
 "rm -f /data/adb/topg/boot_hash.bin",
 "'Boot hash reset.'"
]){
 assert.ok(source.includes(marker),`Missing required UI marker: ${marker}`);
}
function makeNode(tag){
 const node={
  tagName:String(tag).toUpperCase(),children:[],listeners:{},style:{},attributes:{},hidden:false,textContent:'',className:'',id:'',
  append(...kids){this.children.push(...kids);},
  appendChild(kid){this.children.push(kid);return kid;},
  insertBefore(kid,ref){const i=this.children.indexOf(ref);if(i<0){this.children.push(kid);}else{this.children.splice(i,0,kid);}return kid;},
  remove(){this.removed=true;},
  setAttribute(key,value){this.attributes[key]=value;if(key==='id'){this.id=value;}},
  addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);},
  click(){for(const handler of this.listeners.click||[]){handler();}}
 };
 return node;
}
function run(){
 const created=[];
 const document={
  createElement(tag){const node=makeNode(tag);created.push(node);return node;},
  getElementById(id){return created.find(node=>node.id===id)||null;}
 };
 const root=makeNode('div');
 root.replaceChildren=()=>{root.children.length=0;};
 const execCalls=[];
 const ksu={exec(command,options,callback){execCalls.push({command,options,callback});callback(0,'','');}};
 const context={document,ksu,module:{exports:{}}};
 vm.createContext(context);
 vm.runInContext(source+'\nglobalThis.__topg={render,boot};',context);
 context.__topg.render(root,{device:'test',android:'15',build:'test',state:'ok',checks:[],logs:''});
 return {created,execCalls,root,context};
}
const first=run();
const reset=first.created.find(node=>node.id==='tee-reset');
assert.ok(reset,'Reset button must be created');
assert.equal(reset.textContent,'Reset boot hash');
assert.equal(reset.attributes.type,'button');
assert.equal(reset.style.background,'#ff9800');
assert.equal(reset.style.width,'100%');
const notice=first.created.find(node=>node.className==='notice'&&node.children.some(child=>child.textContent==='Boot hash reset'));
assert.ok(notice,'Boot hash mismatch notice must be rendered');
assert.ok(notice.children.some(child=>child.textContent.includes('ro.boot.vbmeta.digest and verifiedBootHash mismatch')),'Mismatch guidance must be rendered');
const feedback=first.created.find(node=>node.id==='tee-reset-feedback');
assert.ok(feedback,'Accessible feedback element must be created');
assert.equal(feedback.attributes.role,'status');
assert.equal(feedback.attributes['aria-live'],'polite');
assert.equal(feedback.hidden,true,'Feedback must start hidden');
reset.click();
const panel=first.created.find(node=>node.className==='notice'&&node.children.some(child=>child.textContent==='Delete the stored boot hash?'));
assert.ok(panel,'In-panel confirmation must appear');
const confirm=panel.children.flatMap(node=>node.children).find(node=>node.textContent==='Confirm');
assert.ok(confirm,'Confirm control must be available');
confirm.click();
assert.equal(first.execCalls.length,1,'Exactly one root command must run');
assert.equal(first.execCalls[0].command,'rm -f /data/adb/topg/boot_hash.bin');
assert.equal(feedback.hidden,false,'Feedback must become visible after the reset');
assert.equal(feedback.textContent,'Boot hash reset.');
assert.ok(panel.removed,'Confirmation panel must close after the action');
const absent=run();
absent.context.__topg.boot(null);
console.log('PASS: diagnostics UI, mismatch notice, in-panel confirmation, root reset and accessible feedback verified.');
