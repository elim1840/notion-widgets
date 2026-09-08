
import json, time, subprocess, urllib.request, websocket, tempfile, shutil
PORT=9414; udd=tempfile.mkdtemp()
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
p=subprocess.Popen([CHROME,"--headless=new",f"--remote-debugging-port={PORT}",f"--user-data-dir={udd}",
 "--no-first-run","--disable-gpu","--remote-allow-origins=*","--hide-scrollbars","--window-size=1280,600",
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
    if r.get("exceptionDetails"): return "EXC "+json.dumps(r["exceptionDetails"])[:250]
    return r["result"].get("value")
time.sleep(3)
print("baseline:", ev("document.getElementById('bar').getAttribute('data-state')"))
ev("window.__RD=window.__RD||Date;")
def probe(iso,w):
    send("Emulation.setDeviceMetricsOverride",{"width":w,"height":600,"deviceScaleFactor":1,"mobile":False})
    r=ev("(function(){var fx=new window.__RD('"+iso+"');"
         "function F(){return arguments.length?new (Function.prototype.bind.apply(window.__RD,[null].concat(Array.prototype.slice.call(arguments)))) : fx;}"
         "F.prototype=window.__RD.prototype;F.now=function(){return fx.getTime();};"
         "F.parse=window.__RD.parse;F.UTC=window.__RD.UTC;window.Date=F;"
         "render();return new Date().toISOString()+' probe='+new Date('2026-09-08T11:00:00.000-04:00').toISOString();})()")
    time.sleep(0.45)
    return ev("(function(){var b=document.getElementById('bar'),r=b.getBoundingClientRect();"
      "var nm=document.querySelector('.name');"
      "return {t:b.getAttribute('data-state'),h:Math.round(r.height),w:Math.round(r.width),"
      "ovx:b.scrollWidth>b.clientWidth+1,fs:nm?getComputedStyle(nm).fontSize:null,"
      "txt:b.innerText.split(String.fromCharCode(10)).join(' | ')};})()"), r
mx=0
for iso in ["2026-09-08T07:30:00-04:00","2026-09-08T09:03:00-04:00","2026-09-08T11:05:00-04:00",
            "2026-09-08T13:15:00-04:00","2026-09-08T13:34:00-04:00","2026-09-08T15:04:00-04:00",
            "2026-09-08T19:30:00-04:00","2026-09-08T22:05:00-04:00","2026-09-08T23:00:00-04:00"]:
    for w in [1280,900,680,520]:
        r,chk=probe(iso,w)
        if not isinstance(r,dict): print("ERR",r,chk); continue
        mx=max(mx,r['h'])
        flag="  <<< OVER 150" if r['h']>150 else ""
        print(f"{iso[11:16]} @{w:>4} [{r['t']:<6}] h={r['h']:>3} ovx={r['ovx']} fs={r['fs']}{flag}")
        if w==1280: print("        "+r['txt'][:210])
print("MAX HEIGHT:",mx)
ws.close(); p.kill(); shutil.rmtree(udd,ignore_errors=True)
