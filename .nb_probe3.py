
import json, time, subprocess, urllib.request, websocket, tempfile, shutil
PORT=9413; udd=tempfile.mkdtemp()
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
p=subprocess.Popen([CHROME,"--headless=new",f"--remote-debugging-port={PORT}",f"--user-data-dir={udd}",
 "--no-first-run","--disable-gpu","--remote-allow-origins=*","--hide-scrollbars","--window-size=1280,500",
 "http://localhost:8020/widgets/nowbar.html"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
tgt=None
for _ in range(60):
    try:
        for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")):
            if t["type"]=="page" and "nowbar" in t.get("url",""): tgt=t
        if tgt: break
    except Exception: pass
    time.sleep(0.5)
ws=websocket.create_connection(tgt["webSocketDebuggerUrl"],timeout=30,suppress_origin=True)
i=[0]
def send(method,params=None):
    i[0]+=1
    ws.send(json.dumps({"id":i[0],"method":method,"params":params or {}}))
    while True:
        m=json.loads(ws.recv())
        if m.get("id")==i[0]: return m.get("result",{})
def ev(e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True,"awaitPromise":True})
    if r.get("exceptionDetails"): return "EXC "+json.dumps(r["exceptionDetails"])[:300]
    return r["result"].get("value")
time.sleep(3)
ev("""window.__RD=Date; window.__setNow=function(iso){const fx=new window.__RD(iso);
 function F(...a){return a.length?new window.__RD(...a):fx;} F.prototype=window.__RD.prototype;
 F.now=()=>fx.getTime(); F.parse=window.__RD.parse; F.UTC=window.__RD.UTC; window.Date=F;};""")
def probe(iso,w):
    send("Emulation.setDeviceMetricsOverride",{"width":w,"height":500,"deviceScaleFactor":1,"mobile":False})
    ev(f"window.__setNow('{iso}'); render();"); time.sleep(0.5)
    return ev("""(()=>{const b=document.getElementById('bar'),r=b.getBoundingClientRect();
      const nm=document.querySelector('.name');
      return {t:b.getAttribute('data-state'),h:Math.round(r.height),w:Math.round(r.width),
      ovx:b.scrollWidth>b.clientWidth+1,fs:nm?getComputedStyle(nm).fontSize:null,
      txt:b.innerText.replace(/\\n/g,' | ')};})()""")
cases=[("2026-09-08T07:30:00-04:00",[1280,900,680,520]),
       ("2026-09-08T11:05:00-04:00",[1280,900,680,520]),
       ("2026-09-08T13:34:00-04:00",[1280,900,680,520]),
       ("2026-09-08T22:05:00-04:00",[1280,680]),
       ("2026-09-08T23:00:00-04:00",[1280])]
mx=0
for iso,ws_ in cases:
    for w in ws_:
        r=probe(iso,w)
        if not isinstance(r,dict): print('ERR',r); continue
        mx=max(mx,r['h'])
        print(f"{iso[11:16]} @{w:>4}  [{r['t']:<6}] h={r['h']:>3} ovx={r['ovx']} nameFS={r['fs']}")
        if w in (1280,520): print("        "+r['txt'][:200])
print("MAX HEIGHT ACROSS ALL:",mx)
ws.close(); p.kill(); shutil.rmtree(udd,ignore_errors=True)
