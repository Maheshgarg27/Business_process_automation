"""
Builds a read-only MAILBOX page (runtime/mailbox.html) from the mail server data:
Inbox = what candidates / approvers sent (attachments readable), Sent = what the platform mailed.
Open the file in any browser. The pipeline never opens it; it is only for viewing.
"""
import base64, json
from datetime import datetime
from core.common import RUNTIME
from core.docparse import read_text
from core.translate import to_english
from services import store

TEMPLATE = r"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>Payroll Automation - Mailbox</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#f6f8fc;--panel:#fff;--line:#e3e6ec;--txt:#1f2328;--mut:#6b7280;--acc:#1a73e8;--sel:#d3e3fd}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,"Segoe UI","Hiragino Sans","Yu Gothic",sans-serif;background:var(--bg);color:var(--txt);height:100vh;display:flex;flex-direction:column}
header{background:#fff;border-bottom:1px solid var(--line);padding:10px 18px;display:flex;align-items:center;gap:16px}
header h1{font-size:18px;margin:0;font-weight:600}header .sub{color:var(--mut);font-size:12px}
header input{margin-left:auto;width:320px;padding:8px 12px;border:1px solid var(--line);border-radius:20px;background:var(--bg)}
main{flex:1;display:flex;min-height:0}
nav{width:220px;padding:14px 10px;border-right:1px solid var(--line);background:var(--bg);overflow:auto}
nav h4{margin:14px 10px 6px;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
nav a{display:flex;justify-content:space-between;padding:7px 12px;border-radius:16px;cursor:pointer;color:var(--txt)}
nav a:hover{background:#e8ecf3}nav a.on{background:var(--sel);font-weight:600}nav a span{color:var(--mut);font-weight:400}
#list{width:400px;background:var(--panel);border-right:1px solid var(--line);overflow:auto}
.row{padding:11px 14px;border-bottom:1px solid var(--line);cursor:pointer}.row:hover{background:#f2f6fc}.row.on{background:var(--sel)}
.row .top{display:flex;justify-content:space-between;gap:8px}.row .who{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .date{color:var(--mut);font-size:12px;white-space:nowrap}.row .subj{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .snip{color:var(--mut);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#read{flex:1;overflow:auto;padding:22px 28px}
.msg{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 22px;margin-bottom:14px;max-width:860px}
.msg h2{margin:0 0 10px;font-size:19px;font-weight:600}.meta{color:var(--mut);font-size:13px;margin-bottom:12px}.meta b{color:var(--txt)}
.body{white-space:pre-wrap;line-height:1.7}.tag{display:inline-block;font-size:11px;padding:2px 9px;border-radius:10px;margin-left:6px;font-weight:600}
.APPROVED{background:#c6efce;color:#0b5a1f}.REJECTED{background:#ffc7ce;color:#8a1020}.NEEDS_REVIEW{background:#ffeb9c;color:#7a5b00}.ERROR,.none{background:#e5e7eb;color:#444}
.tool{border-left:4px solid var(--acc)}.att{margin-top:14px}.att summary{cursor:pointer;padding:6px 10px;background:var(--bg);border:1px solid var(--line);border-radius:6px;margin-top:6px}
.att pre{margin:0;padding:10px 14px;background:#fbfbfd;border:1px solid var(--line);border-top:0;border-radius:0 0 6px 6px;font:13px/1.6 inherit;white-space:pre-wrap}
.thr{max-width:860px;color:var(--mut);font-size:12px;margin:2px 0 8px}.empty{color:var(--mut);text-align:center;margin-top:80px}
</style></head><body>
<header><h1>📬 Payroll Automation Mailbox</h1><span class="sub" id="gen"></span><input id="q"></header>
<main><nav id="nav"></nav><div id="list"></div><div id="read"><div class="empty" id="hint"></div></div></main>
<script>
const DATA=__DATA__;
const EN=DATA.lang==="en";
const T=EN?{inbox:"Inbox",sent:"Sent",bytype:"Sent (by type)",pick:"← select a mail",search:"search (name, subject, text)",replied:"✔ replied",
 toolreply:"↩ Reply from the automation tool",noreply:"No reply yet",tool:"Automation tool",case:"Case ID",none:"No mails",orig:"↪ Original mail",to:"To: "}:
{inbox:"受信箱",sent:"送信済み",bytype:"送信済み（種別）",pick:"← メールを選択してください",search:"検索（名前・件名・本文）",replied:"✔ 返信済",
 toolreply:"↩ ツールの返信",noreply:"まだ返信がありません",tool:"自動処理ツール",case:"案件ID",none:"メールなし",orig:"↪ 元のメール",to:"To: "};
const KIND=EN?{onboarding_result:"Onboarding",leave_result:"Leave",expense_result:"Expense",invoice_query:"Invoice query",purchase_order:"Purchase order",
 approval_request:"Approval request",approval_reminder:"Approval reminder",approval_escalation:"Approval escalation"}:
{onboarding_result:"入社手続き",leave_result:"休暇申請",expense_result:"経費精算",invoice_query:"請求書照会",purchase_order:"発注",
 approval_request:"承認依頼",approval_reminder:"承認リマインド",approval_escalation:"承認エスカレーション"};
const byId={};DATA.mails.forEach(m=>byId[m.id]=m);
let folder="inbox",kind="",sel=null;
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const inbox=DATA.mails.filter(m=>m.direction==="in"),sent=DATA.mails.filter(m=>m.direction==="out");
const repliesTo=id=>sent.filter(m=>m.in_reply_to===id);
const tag=c=>{const s=DATA.status[c]||"";return s?`<span class="tag ${s}">${s}</span>`:""};
function nav(){const kinds={};sent.forEach(m=>kinds[m.kind]=(kinds[m.kind]||0)+1);
 let h=`<a class="${folder==="inbox"?"on":""}" onclick="go('inbox','')">📥 ${T.inbox} <span>${inbox.length}</span></a>
 <a class="${folder==="sent"&&!kind?"on":""}" onclick="go('sent','')">📤 ${T.sent} <span>${sent.length}</span></a><h4>${T.bytype}</h4>`;
 Object.keys(kinds).forEach(k=>h+=`<a class="${folder==="sent"&&kind===k?"on":""}" onclick="go('sent','${k}')">${KIND[k]||k} <span>${kinds[k]}</span></a>`);
 document.getElementById("nav").innerHTML=h}
function go(f,k){folder=f;kind=k;sel=null;render();document.getElementById("read").innerHTML='<div class="empty">'+T.pick+'</div>'}
function render(){nav();const q=document.getElementById("q").value.toLowerCase();
 let ms=(folder==="inbox"?inbox:sent).filter(m=>!kind||m.kind===kind).filter(m=>!q||JSON.stringify(m).toLowerCase().includes(q));
 ms.sort((a,b)=>(b.received_at||b.sent_at||"").localeCompare(a.received_at||a.sent_at||""));
 document.getElementById("list").innerHTML=ms.map(m=>{const who=folder==="inbox"?(m.from_name||m.from)+" <"+m.from+">":T.to+m.to;
  const st=folder==="inbox"?(m.replied?T.replied+" ":"")+tag(m.case_ref):tag(m.case_ref);
  return `<div class="row ${sel===m.id?"on":""}" onclick="show('${m.id}')"><div class="top"><span class="who">${esc(who)}</span><span class="date">${esc((m.received_at||m.sent_at||"").slice(0,10))}</span></div>
  <div class="subj">${esc(m.subject)} ${st}</div><div class="snip">${esc(m.body.replace(/\n/g," ").slice(0,90))}</div></div>`}).join("")||'<div class="empty">'+T.none+'</div>'}
function card(m,isTool){const att=(m.attachments||[]).map(a=>`<details class="att"><summary>📎 ${esc(a.filename)} （${esc(a.label)}）</summary><pre>${esc(a.content)}</pre></details>`).join("");
 return `<div class="msg ${isTool?"tool":""}"><h2>${esc(m.subject)} ${tag(m.case_ref)}</h2>
 <div class="meta"><b>${isTool?T.tool:esc(m.from_name||m.from)}</b> &lt;${esc(m.from)}&gt; → ${esc(m.to)}<br>${esc(m.received_at||m.sent_at||"")}　${T.case}: ${esc(m.case_ref)}　${m.id}</div>
 <div class="body">${esc(m.body)}</div>${att}</div>`}
function show(id){sel=id;const m=byId[id];let h="";
 if(m.direction==="in"){h+=card(m,false);const r=repliesTo(id);
  h+=r.length?`<div class="thr">${T.toolreply} (${r.length})</div>`+r.map(x=>card(x,true)).join(""):`<div class="thr">${T.noreply}</div>`}
 else{if(m.in_reply_to&&byId[m.in_reply_to])h+=`<div class="thr">${T.orig}</div>`+card(byId[m.in_reply_to],false)+`<div class="thr">${T.toolreply}</div>`;h+=card(m,true)}
 document.getElementById("read").innerHTML=h;render()}
document.documentElement.lang=EN?"en":"ja";document.getElementById("q").placeholder=T.search;document.getElementById("hint").textContent=T.pick;
document.getElementById("q").oninput=render;document.getElementById("gen").textContent=(EN?"English view · ":"日本語 · ")+"generated "+DATA.generated;render();
</script></body></html>"""


def render(lang="ja"):
    """Return the mailbox page as a string. lang='en' translates mails and attachments on the fly."""
    en = lang == "en"
    mails = store.rows("mail")
    for m in mails:
        atts = []
        for a in m.get("attachments", []):
            content = read_text(a["filename"], base64.b64decode(a["content_b64"]))
            label = content.split("\n")[0].replace("【書類種別】", "")
            if en:
                content, label = to_english(content), to_english(label)
            atts.append({"doc_type": a["doc_type"], "filename": a["filename"] if not en else to_english(a["filename"]), "content": content, "label": label})
        m["attachments"] = atts
        if en:
            for k in ("subject", "body", "from_name"):
                if m.get(k):
                    m[k] = to_english(m[k])
    status = {}
    audit = RUNTIME / "audit_log.jsonl"
    if audit.exists():
        for line in audit.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            status[e["case_id"]] = e["status"]
    data = {"mails": mails, "status": status, "lang": lang, "generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    return TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def build(path=None, lang="ja"):
    out = path or RUNTIME / ("mailbox.html" if lang == "ja" else f"mailbox_{lang}.html")
    out.write_text(render(lang), encoding="utf-8")
    return out


if __name__ == "__main__":
    print("Mailbox pages written to:", build(), build(lang="en"))
