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
  querySelectorAll:sel=>sel==='.panel'?Array.from({length:10},mkEl):[]};
global.window = {}; global.navigator = {}; global.innerWidth = 1200;
eval(fs.readFileSync('data.js','utf8'));
class ChartStub{constructor(el,cfg){if(!cfg.options)throw new Error('bad cfg'); ChartStub.n=(ChartStub.n||0)+1;
  for(const ds of cfg.data.datasets){ if(!Array.isArray(ds.data)) throw new Error('dataset.data fehlt');
    let prev=-Infinity; for(const p of ds.data){ if(p==null||p.x==null||p.y===undefined) throw new Error('Punktformat');
      if(p.x<prev) throw new Error('x nicht aufsteigend'); prev=p.x; } } }
  static register(){} static getChart(){return null}}
ChartStub.defaults = {color:'', font:{family:'',size:0}};
global.Chart = ChartStub;
for(const s of scripts) eval(s);
console.log('JS OK | Charts erstellt:', ChartStub.n, '(soll 9)');
console.log('Krypto-Header:', els['h_cr'].textContent);
console.log('MRI-Header:', els['h_mri'].textContent);
console.log('Karten:', els['cards'].children.length, '| Update-Zeile:', els['updated'].innerHTML.replace(/<[^>]+>/g,''));
