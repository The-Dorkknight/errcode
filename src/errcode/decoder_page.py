# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The offline HTML decoder: one self-contained page (dictionary embedded) that turns
EC2 digits, quick codes or EC1 strings back into plain language. Works on a phone,
from a file, or on GitHub Pages - where a QR made with --link opens it directly.

    errcode decoder docs/decode.html
"""
from __future__ import annotations

import json

CSS = r"""
:root{
  /* layout: one narrow column - paste box, verdict, code rows, then the code book */
  --bg:#f3f5f7; --panel:#ffffff; --ink:#15202b; --muted:#566573; --line:#d5dce3;
  --accent:#0b5cad; --accent-ink:#ffffff; --mono-bg:#eaeff4;
  --ok:#1d7a3e; --warn:#8a6100; --err:#b54708; --fatal:#b3122e;
  --ok-bg:#e3f4e9; --warn-bg:#fbf0d4; --err-bg:#fde8db; --fatal-bg:#fbe1e6;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0e141b; --panel:#151d26; --ink:#e4ebf2; --muted:#9aabbb; --line:#283442;
  --accent:#7cb8f5; --accent-ink:#0b1622; --mono-bg:#1b2531;
  --ok:#6fd496; --warn:#f2c35b; --err:#ffa36b; --fatal:#ff7a90;
  --ok-bg:#15301f; --warn-bg:#352a0c; --err-bg:#3a2112; --fatal-bg:#3d1520; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e141b; --panel:#151d26; --ink:#e4ebf2; --muted:#9aabbb; --line:#283442;
  --accent:#7cb8f5; --accent-ink:#0b1622; --mono-bg:#1b2531;
  --ok:#6fd496; --warn:#f2c35b; --err:#ffa36b; --fatal:#ff7a90;
  --ok-bg:#15301f; --warn-bg:#352a0c; --err-bg:#3a2112; --fatal-bg:#3d1520; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans)}
.dec-wrap{max-width:860px;margin:0 auto;padding-block:20px 48px;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));
  display:grid;gap:18px}
.dec-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px}
.dec-head h1{margin:0;font-size:1.5rem;letter-spacing:-.01em;text-wrap:balance}
.dec-head .ver{font:12px var(--mono);color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}
label.lbl{display:block;font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
textarea{width:100%;min-height:96px;resize:vertical;font:15px/1.5 var(--mono);color:var(--ink);background:var(--mono-bg);
  border:1px solid var(--line);border-radius:8px;padding:10px}
textarea:focus,input:focus,button:focus-visible,select:focus{outline:2px solid var(--accent);outline-offset:1px}
.row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;align-items:center}
button{font:600 14px var(--sans);border-radius:8px;border:1px solid var(--accent);background:transparent;color:var(--accent);
  padding:8px 14px;cursor:pointer}
button.primary{background:var(--accent);color:var(--accent-ink)}
.hint{color:var(--muted);font-size:13px}
.msg{font-size:14px;padding:10px 12px;border-radius:8px;background:var(--mono-bg)}
.msg.bad{background:var(--fatal-bg);color:var(--fatal)}
.meta{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--muted)}
.meta b{color:var(--ink);font-weight:600}
.meta .mi{display:inline-block}
.codes{display:grid;gap:10px}
.code{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;padding:12px 14px;border-radius:10px;
  border:1px solid var(--line);background:var(--panel);border-left-width:5px}
.code.s0{border-left-color:var(--ok)} .code.s1{border-left-color:var(--warn)}
.code.s2{border-left-color:var(--err)} .code.s3{border-left-color:var(--fatal)}
.code .num{font:600 1.6rem/1 var(--mono);font-variant-numeric:tabular-nums;grid-row:span 3;padding-top:2px}
.code .top{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;min-width:0}
.chip{font:600 11px var(--mono);letter-spacing:.05em;padding:2px 7px;border-radius:99px}
.chip.s0{background:var(--ok-bg);color:var(--ok)} .chip.s1{background:var(--warn-bg);color:var(--warn)}
.chip.s2{background:var(--err-bg);color:var(--err)} .chip.s3{background:var(--fatal-bg);color:var(--fatal)}
.key{font:13px var(--mono);color:var(--muted);overflow-wrap:anywhere}
.what{min-width:0}
.detail{font:13px var(--mono);background:var(--mono-bg);padding:1px 6px;border-radius:5px;overflow-wrap:anywhere}
.fix{font-size:13.5px;color:var(--muted);min-width:0} .fix b{color:var(--ink)}
.blocks{font:14px/1.7 var(--mono);font-variant-numeric:tabular-nums;overflow-x:auto;white-space:pre}
.blocks .badblk{background:var(--fatal-bg);color:var(--fatal);border-radius:4px}
.book-tools{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.book-tools input{flex:1 1 220px;min-width:0;font:15px var(--sans);padding:8px 10px;border-radius:8px;border:1px solid var(--line);
  background:var(--mono-bg);color:var(--ink)}
.book-tools select{font:14px var(--sans);padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--mono-bg);color:var(--ink)}
.book{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.book table{border-collapse:collapse;width:100%;font-size:13.5px}
.book th,.book td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
.book th{position:sticky;top:0;background:var(--mono-bg);font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.book td.c{font:600 14px var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.book tr{cursor:pointer} .book tr:hover td{background:var(--mono-bg)}
@media (max-width:520px){.code{grid-template-columns:1fr}.code .num{grid-row:auto}}
@media (prefers-reduced-motion:no-preference){.code{animation:rise .18s ease-out both}}
@keyframes rise{from{transform:translateY(3px)}to{transform:none}}
"""

BODY = r"""
<div class="dec-wrap">
  <header class="dec-head"><h1>ErrCode decoder</h1><span class="ver" id="dec-ver"></span></header>
  <section class="panel">
    <label class="lbl" for="dec-in">Paste a report, QR text or quick codes</label>
    <textarea id="dec-in" spellcheck="false" autocomplete="off"
      placeholder="EC2-34739 02382 ...   or several QR parts, one per line   or   E102 W706"></textarea>
    <div class="row">
      <button class="primary" id="dec-go" type="button">Decode</button>
      <button id="dec-ex" type="button">Load an example</button>
      <span class="hint">Spaces and dashes are ignored. Nothing leaves this page.</span>
    </div>
  </section>
  <div id="dec-out" class="codes" aria-live="polite"></div>
  <section class="panel">
    <label class="lbl" for="dec-q">Code book</label>
    <div class="book-tools">
      <input id="dec-q" type="search" placeholder="Search 102, tkinter, dialout, ESP32...">
      <select id="dec-dom" aria-label="Domain"></select>
    </div>
    <div class="book"><table><thead><tr><th>Code</th><th>Level</th><th>Meaning</th></tr></thead><tbody id="dec-book"></tbody></table></div>
    <p class="hint" id="dec-count"></p>
  </section>
</div>
"""

JS = r"""
(function(){
const D = window.ERRCODE_DATA;
const SEV = ["OK","WARN","ERROR","FATAL"];
const BY = new Map(D.entries.map(e => [e.code, e]));
const BYDI = new Map(D.entries.map(e => [e.domain*1000+e.id, e]));
const DAMM=[[0,3,1,7,5,9,8,6,4,2],[7,0,9,2,1,5,4,8,6,3],[4,2,0,6,8,7,1,3,5,9],[1,7,5,0,9,8,3,4,2,6],
 [6,1,2,3,0,4,5,9,7,8],[3,6,7,4,2,0,9,5,8,1],[5,8,6,9,7,2,0,1,3,4],[8,9,4,5,3,6,2,0,1,7],
 [9,4,3,8,6,1,7,2,0,5],[2,5,8,1,4,3,6,7,9,0]];
const EPOCH = Date.UTC(2026,0,1);
const CAP = []; for (let k=0;k<=19;k++){let b=0; while ((2n**BigInt(b+1)) <= (10n**BigInt(k))) b++; CAP.push(b);}
const LETTERS="abcdefghijklmnopqrstuvwxyz", DIG="0123456789", PUNCT=D.alphabet.punct;
const CHAR={}; for(let i=0;i<26;i++)CHAR[4+i]=LETTERS[i]; for(let i=0;i<10;i++)CHAR[30+i]=DIG[i];
for(let i=0;i<PUNCT.length;i++)CHAR[40+i]=PUNCT[i];
const B32="0123456789ABCDEFGHJKMNPQRSTVWXYZ";
class Bad extends Error{constructor(m,blk){super(m);this.blk=blk}}
const damm = s => {let i=0; for (const c of s) i=DAMM[i][c.charCodeAt(0)-48]; return i;};
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function pieces(text){
  const out=[], re=/EC2(?:\/([1-9])([1-9])(\d{3}))?-?([\d\s.\-_]*)/gi; let m;
  while ((m=re.exec(text))){const d=m[4].replace(/\D/g,""); if(!d) continue;
    out.push(m[1]?{i:+m[1],n:+m[2],set:m[3],d}:{i:1,n:1,set:"",d});}
  return out;
}
function joinParts(ps){
  if (ps.length===1 && ps[0].n===1) return ps[0].d;
  const n=ps[0].n, have={};
  for (const p of ps){ if (p.n!==n || p.set!==ps[0].set) throw new Bad("These parts come from different reports."); have[p.i]=p.d; }
  const miss=[]; for(let i=1;i<=n;i++) if(!(i in have)) miss.push(i);
  if (miss.length) throw new Bad("Still need part "+miss.join(", ")+" of "+n+" - scan the other QR code"+(miss.length>1?"s":"")+".");
  let s=""; for(let i=1;i<=n;i++) s+=have[i]; return s;
}
function toBits(digits){
  if (digits.length % 20 === 1) throw new Bad("The last block is 1 digit long - a digit is missing or extra somewhere.");
  let bits="";
  for (let s=0, b=0; s<digits.length; s+=20, b++){
    const blk=digits.slice(s,s+20);
    if (damm(blk)!==0) throw new Bad("Block "+(b+1)+" (digits "+(s+1)+"-"+(s+blk.length)+") fails its check digit. Re-read or re-scan those digits.", b);
    const k=blk.length-1, nb = k===19?63:CAP[k]; const v=BigInt(blk.slice(0,k));
    if (v >= (1n<<BigInt(nb))) throw new Bad("Block "+(b+1)+" is not valid.", b);
    bits += v.toString(2).padStart(nb,"0");
  }
  return bits;
}
function reader(bits){
  let p=0;
  const need=n=>{ if(p+n>bits.length) throw new Bad("The report is cut short - a part or block may be missing."); };
  const get=n=>{ need(n); const v=n?parseInt(bits.slice(p,p+n),2):0; p+=n; return v; };
  const gamma=()=>{ let z=0; while(true){ need(1); if(bits[p]==="1") break; z++; p++; if(z>52) throw new Bad("Damaged report."); } return get(z+1)-1; };
  const text=()=>{ const n=gamma(); let out="", caps=false, shift=false;
    for(let i=0;i<n;i++){ const s=get(6);
      if(s===0) shift=true; else if(s===1) caps=!caps;
      else if(s===2){ const w=get(8); out+= D.words[w] ?? ("<word "+w+">"); shift=false; }
      else if(s===3){ out+=String.fromCharCode(get(8)); shift=false; }
      else { let c=CHAR[s]; if (/[a-z]/.test(c) && (caps!==shift)) c=c.toUpperCase(); out+=c; shift=false; } }
    return out; };
  return {get,gamma,text,rest:()=>bits.slice(p)};
}
function decodeEC2(text){
  const ps=pieces(text.toUpperCase()); if(!ps.length) throw new Bad("No EC2 report found.");
  const digits=joinParts(ps), r=reader(toBits(digits));
  const rev=r.gamma(), minute=r.get(25), session=r.get(15), fa=r.get(1), fs=r.get(1), fo=r.get(1);
  const app=fa?r.text():null, stats=fs?[r.gamma(),r.gamma(),r.gamma()]:null, omitted=fo?r.gamma():0;
  const n=r.gamma(), codes=[];
  for(let i=0;i<n;i++){ const code=r.get(10); if(code>999) throw new Bad("Code "+code+" needs a newer decoder.");
    const sev=r.get(2), count=r.gamma()+1, tag=r.get(2); let detail=null;
    if(tag===1) detail=r.gamma(); else if(tag===2) detail=r.text(); else if(tag===3) detail=-r.gamma()-1;
    codes.push({code,sev,count,detail}); }
  if (/1/.test(r.rest())) throw new Bad("Extra data after the last code - parts from different reports mixed?");
  return {fmt:"EC2", rev, when:new Date(EPOCH+minute*60000), session:String(session).padStart(5,"0"), app, stats, omitted, codes, digits};
}
function b32(s){ let v=0; for (const ch of s){ const c={O:"0",I:"1",L:"1"}[ch]||ch; const i=B32.indexOf(c); if(i<0) throw new Bad("Invalid character "+ch); v=v*32+i; } return v; }
function ec1code(c){ const v=b32(c), body=v>>3, chk=v&7; let x=body, f=0; while(x){f^=x&7;x>>=3;}
  const dom=body>>14, sev=(body>>12)&3, id=body&0xFFF, e=BYDI.get(dom*1000+id);
  return {code:e?e.code:null, raw:c, sev, count:1, detail:null, ok:f===chk, entry:e, dom, id}; }
function decodeAny(text){
  const t=text.trim(); const up=t.toUpperCase();
  if (/EC2/.test(up)) return decodeEC2(up);
  if (/^EC1-/.test(up)){ const parts=up.split("-"); if(parts.length!==3) throw new Bad("Not an EC1 string.");
    const st=parts[1].replace(/[\s._]/g,""), cs=parts[2].replace(/[\s._]/g,"");
    if(st.length!==8 || cs.length%4) throw new Bad("Not an EC1 string.");
    const codes=[]; for(let i=0;i<cs.length;i+=4) codes.push(ec1code(cs.slice(i,i+4)));
    return {fmt:"EC1", when:new Date(EPOCH+b32(st.slice(0,5))*60000), session:st.slice(5), codes}; }
  const q=up.match(/[OWEF]?\d{3}/g);
  if (q && /^(?:[OWEF]?\d{3}[\s,;]*)+$/.test(up)) return {fmt:"codes", codes:q.map(tok=>{ const n=+tok.slice(-3), e=BY.get(n);
    return {code:n, sev:/[OWEF]/.test(tok[0])?"OWEF".indexOf(tok[0]):(e?e.severity:2), count:1, detail:null}; })};
  const compact=up.replace(/[\s.\-_]/g,"");
  if (compact && compact.length%4===0 && /^[0-9A-Z]+$/.test(compact)){ const codes=[]; for(let i=0;i<compact.length;i+=4) codes.push(ec1code(compact.slice(i,i+4))); return {fmt:"EC1", codes}; }
  throw new Bad("This does not look like an ErrCode report. Expected EC2 digits, quick codes such as E102, or an EC1 string.");
}
const fmtWhen = d => { const p=n=>String(n).padStart(2,"0");
  const utc=d.getUTCFullYear()+"-"+p(d.getUTCMonth()+1)+"-"+p(d.getUTCDate())+" "+p(d.getUTCHours())+":"+p(d.getUTCMinutes())+" UTC";
  const loc=d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate())+" "+p(d.getHours())+":"+p(d.getMinutes());
  return utc+"  ("+loc+" your time)"; };
function rowHTML(c){
  const e = c.entry || (c.code!=null ? BY.get(c.code) : null);
  const num = c.code!=null ? String(c.code).padStart(3,"0") : esc(c.raw);
  const dom = c.code!=null ? Math.floor(c.code/100) : c.dom;
  const key = e ? e.key : ((D.domains[dom]||{key:"?"}).key+".#"+(c.code!=null?c.code%100:c.id));
  let what = e ? esc(e.message) : (dom===9 ? "App-defined code. Its meaning is in the sending program's documentation." :
              "Not in this dictionary (revision "+D.revision+"). The sender may be newer. The level is still valid.");
  if (c.ok===false) what = "Check bits do not match. This code was probably mistyped.";
  const det = (c.detail!==null && c.detail!=="") ? ' <span class="detail">'+esc(c.detail)+'</span>' : "";
  const cnt = c.count>1 ? ' <span class="hint">x'+c.count+'</span>' : "";
  const fix = (e && e.fix && c.sev>=1 && c.ok!==false) ? '<div class="fix"><b>Fix:</b> '+esc(e.fix)+'</div>' : "";
  return '<div class="code s'+c.sev+'"><div class="num">'+num+'</div><div class="top"><span class="chip s'+c.sev+'">'+SEV[c.sev]+
    '</span><span class="key">'+esc(key)+'</span>'+cnt+'</div><div class="what">'+what+det+'</div>'+fix+'</div>';
}
function blocksHTML(digits, bad){
  let out=""; for(let s=0,b=0;s<digits.length;s+=20,b++){ const blk=digits.slice(s,s+20).replace(/(\d{5})(?=\d)/g,"$1 ");
    out+=(b===bad?'<span class="badblk">'+blk+'</span>':blk)+"\n"; } return out;
}
const out=document.getElementById("dec-out"), input=document.getElementById("dec-in");
function run(){
  const t=input.value; if(!t.trim()){ out.innerHTML=""; return; }
  try{
    const r=decodeAny(t); let h="";
    const meta=[];
    if (r.when) meta.push("Made <b>"+esc(fmtWhen(r.when))+"</b>");
    if (r.app) meta.push("App <b>"+esc(r.app)+"</b>");
    if (r.session) meta.push("Session <b>"+esc(r.session)+"</b>");
    if (r.stats) meta.push("Log <b>"+r.stats[0]+"</b> lines, "+r.stats[1]+" noise and "+r.stats[2]+" repeats ignored");
    meta.push("Format <b>"+r.fmt+"</b>");
    h+='<div class="meta">'+meta.map(m=>'<span class="mi">'+m+'</span>').join("")+'</div>';
    h+=r.codes.map(rowHTML).join("");
    if (r.omitted) h+='<p class="hint">+'+r.omitted+' lower-priority code(s) were left out by the sender to fit the space.</p>';
    if (r.rev>D.revision) h+='<p class="msg">Sent with dictionary revision '+r.rev+'; this page has '+D.revision+'. Newer codes may show as unknown.</p>';
    out.innerHTML=h;
  }catch(err){
    if(!(err instanceof Bad)) throw err;
    let h='<p class="msg bad">'+esc(err.message)+'</p>';
    if (err.blk!==undefined){ try{ const d=joinParts(pieces(t.toUpperCase())); h+='<div class="panel"><div class="blocks">'+blocksHTML(d,err.blk)+'</div></div>'; }catch(e){} }
    out.innerHTML=h;
  }
}
document.getElementById("dec-go").addEventListener("click", run);
document.getElementById("dec-ex").addEventListener("click", ()=>{ input.value=D.example; run(); });
input.addEventListener("keydown", e=>{ if(e.key==="Enter" && (e.ctrlKey||e.metaKey)) run(); });
document.getElementById("dec-ver").textContent = "dictionary revision "+D.revision+" | "+D.entries.length+" codes | errcode "+D.version;
// code book
const sel=document.getElementById("dec-dom"), q=document.getElementById("dec-q"), book=document.getElementById("dec-book");
sel.innerHTML='<option value="">All areas</option>'+Object.entries(D.domains).map(([i,d])=>'<option value="'+i+'">'+i+'xx '+esc(d.title)+'</option>').join("");
function fill(){
  const s=q.value.trim().toLowerCase(), dom=sel.value; let n=0, h="";
  for (const e of D.entries){
    if (dom!=="" && String(e.domain)!==dom) continue;
    if (s && !(String(e.code).padStart(3,"0").startsWith(s) || e.key.toLowerCase().includes(s) || e.message.toLowerCase().includes(s) || e.fix.toLowerCase().includes(s) || e.patterns.join(" ").toLowerCase().includes(s))) continue;
    n++; h+='<tr data-c="'+e.code+'"><td class="c">'+String(e.code).padStart(3,"0")+'</td><td><span class="chip s'+e.severity+'">'+SEV[e.severity]+'</span></td><td><span class="key">'+esc(e.key)+'</span><br>'+esc(e.message)+'</td></tr>';
  }
  book.innerHTML=h; document.getElementById("dec-count").textContent=n+" of "+D.entries.length+" codes shown. Tap a row to see its fix.";
}
book.addEventListener("click", ev=>{ const tr=ev.target.closest("tr"); if(!tr) return; const e=BY.get(+tr.dataset.c);
  input.value=(["O","W","E","F"][e.severity])+String(e.code).padStart(3,"0"); run(); input.scrollIntoView({block:"nearest"}); });
q.addEventListener("input", fill); sel.addEventListener("change", fill); fill();
// a QR made with --link opens this page with the report after '#'
const h=decodeURIComponent((location.hash||"").slice(1));
if (/EC[12]/i.test(h)) { input.value=h; run(); }
window.ERRCODE_DECODE = decodeAny;
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600'
         '&family=IBM+Plex+Sans:wght@400;600&display=swap">')


def data_script(data: dict, example: str) -> str:
    d = dict(data)
    d["example"] = example
    blob = json.dumps(d, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return "<script>window.ERRCODE_DATA=%s;</script>" % blob


def _example() -> str:
    from .plugin import scan
    from .samples import SAMPLES
    rep = scan(SAMPLES["Windows: missing C++ runtime"], app="demo", minute=444000, session=12345)
    return rep.payload


def build(data: dict) -> str:
    """A complete, self-contained HTML document."""
    from . import ec2
    data = dict(data)
    data["alphabet"] = {"punct": ec2._PUNCT}
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
            "<title>ErrCode decoder</title>"
            "<!-- Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight) -->"
            "<!-- Licensed under the PolyForm Noncommercial License 1.0.0. No warranty. -->"
            + FONTS + "<style>" + CSS + "</style></head><body>" + BODY
            + data_script(data, _example()) + "<script>" + JS + "</script></body></html>\n")
