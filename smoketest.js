// Smoke-Test: fuehrt das Dashboard-JS mit Stub-DOM aus
const fs = require('fs');
const html = fs.readFileSync('dashboard.html','utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const els = {};
const mkEl = () => ({textContent:'',innerHTML:'',style:{},className:'',children:[],
  appendChild(c){this.children.push(c)}, insertBefore(c){this.children.unshift(c)},
  querySelector(){return mkEl()}, querySelectorAll(){return [mkEl(),mkEl()]},
  get lastChild(){return this.children[this.children.length-1]||mkEl()}});
global.document = {getElementById:id=>els[id]||(els[id]=mkEl()), createElement:()=>mkEl(),
  querySelectorAll:sel=>sel==='.panel'?Array.from({length:9},mkEl):[]};
global.window = {}; global.navigator = {};
eval(fs.readFileSync('data.js','utf8'));
global.Chart = class{constructor(el,cfg){if(!cfg.options)throw new Error('bad cfg'); Chart.n=(Chart.n||0)+1}
  static register(){} static getChart(){return null}};
for(const s of scripts) eval(s);
console.log('JS OK | Charts erstellt:', Chart.n, '(soll 9)');
console.log('Krypto-Header:', els['h_cr'].textContent);
console.log('MRI-Header:', els['h_mri'].textContent);
console.log('Karten gesamt:', els['cards'].children.length);