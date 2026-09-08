
import json, time, subprocess, urllib.request, websocket, tempfile, shutil
PORT=9412; udd=tempfile.mkdtemp()
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
def ev(e):
    i[0]+=1
    ws.send(json.dumps({"id":i[0],"method":"Runtime.evaluate","params":{"expression":e,"returnByValue":True,"awaitPromise":True}}))
    while True:
        m=json.loads(ws.recv())
        if m.get("id")==i[0]:
            r=m["result"]["result"]
            if m["result"].get("exceptionDetails"): return "EXC "+str(m["result"]["exceptionDetails"])
            return r.get("value")
time.sleep(3)
# freeze Date at a chosen wall time
ev("""window.__RD=Date; window.__setNow=function(iso){
  const fx=new window.__RD(iso);
  function F(...a){ if(a.length) return new window.__RD(...a); return fx; }
  F.prototype=window.__RD.prototype; F.now=()=>fx.getTime(); F.parse=window.__RD.parse; F.UTC=window.__RD.UTC;
  window.Date=F; };""")
def probe(iso,width):
    ev(f"window.__setNow('{iso}'); document.documentElement.style.width='{width}px'; render();")
    time.sleep(0.4)
    return ev("""(()=>{const b=document.getElementById('bar');const r=b.getBoundingClientRect();
      return {t:b.getAttribute('data-state'),accent:getComputedStyle(b).getPropertyValue('--accent'),
      h:Math.round(r.height),w:Math.round(r.width),ovx:b.scrollWidth>b.clientWidth+1,
      txt:b.innerText.replace(/\\n/g,' | ')};})()""")
for iso,w in [("2026-09-08T07:30:00-04:00",1280),("2026-09-08T11:05:00-04:00",1280),
              ("2026-09-08T13:15:00-04:00",1280),("2026-09-08T13:34:00-04:00",1280),
              ("2026-09-08T15:04:00-04:00",1280),("2026-09-08T19:30:00-04:00",1280),
              ("2026-09-08T22:05:00-04:00",1280),("2026-09-08T23:00:00-04:00",1280),
              ("2026-09-08T07:30:00-04:00",860),("2026-09-08T07:30:00-04:00",680),
              ("2026-09-08T13:34:00-04:00",680)]:
    r=probe(iso,w)
    print(f"{iso[11:16]} @{w}px  [{r['t']}] h={r['h']} ovx={r['ovx']} accent={r['accent'].strip()}")
    print("      "+r['txt'][:230])
ws.close(); p.kill(); shutil.rmtree(udd,ignore_errors=True)
