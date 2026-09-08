
import json, time, subprocess, urllib.request, websocket, os, shutil, tempfile

PORT=9411
udd=tempfile.mkdtemp(prefix="nbchrome")
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
p=subprocess.Popen([CHROME,"--headless=new",f"--remote-debugging-port={PORT}",
    f"--user-data-dir={udd}","--no-first-run","--no-default-browser-check",
    "--disable-gpu","--remote-allow-origins=*","--hide-scrollbars","--window-size=1280,400",
    "http://localhost:8020/widgets/nowbar.html"],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
tgt=None
for _ in range(60):
    try:
        js=json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
        for t in js:
            if t["type"]=="page" and "nowbar" in t.get("url",""): tgt=t; break
        if tgt: break
    except Exception: pass
    time.sleep(0.5)
if not tgt:
    print("NO TARGET"); p.kill(); raise SystemExit(1)
ws=websocket.create_connection(tgt["webSocketDebuggerUrl"],timeout=30,suppress_origin=True)
i=[0]
def ev(expr):
    i[0]+=1
    ws.send(json.dumps({"id":i[0],"method":"Runtime.evaluate",
        "params":{"expression":expr,"returnByValue":True,"awaitPromise":True}}))
    while True:
        m=json.loads(ws.recv())
        if m.get("id")==i[0]:
            return m["result"]["result"].get("value")
time.sleep(3)
expr = """(() => {
  const b=document.getElementById('bar');
  if(!b) return {err:'no bar'};
  const r=b.getBoundingClientRect();
  const nm=document.querySelector('.name');
  return {
    state:b.getAttribute('data-state'),
    accent:getComputedStyle(b).getPropertyValue('--accent'),
    barH:Math.round(r.height), barW:Math.round(r.width),
    docH:document.documentElement.scrollHeight,
    bodyH:Math.round(document.body.getBoundingClientRect().height),
    overflowX:b.scrollWidth>b.clientWidth+1,
    text:b.innerText,
    nameFS: nm?getComputedStyle(nm).fontSize:null,
    nameH: nm?Math.round(nm.getBoundingClientRect().height):null,
    cells:[...document.querySelectorAll('.cell')].map(c=>({cls:c.className,w:Math.round(c.getBoundingClientRect().width)})),
    tabnum: getComputedStyle(document.querySelector('.clock')).fontVariantNumeric,
    ticks: document.querySelectorAll('.tick').length,
    nowLeft: document.querySelector('.now')?document.querySelector('.now').style.left:null
  };
})()"""
print(json.dumps(ev(expr),indent=1))
c1=ev("document.querySelector('.clock').innerText")
time.sleep(2.5)
c2=ev("document.querySelector('.clock').innerText")
print("CLOCK t0:",repr(c1)," t+2.5s:",repr(c2)," ticking:",c1!=c2)
ws.close(); p.kill(); shutil.rmtree(udd,ignore_errors=True)
