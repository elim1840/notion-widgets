"use strict";
var DATA=null, LONG=["SUN","MON","TUE","WED","THU","FRI","SAT"],
    MON=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];

/* ---------- helpers (pure, testable) ---------- */
function pad(n){return (n<10?"0":"")+n;}
function hhmm(d){return pad(d.getHours())+":"+pad(d.getMinutes());}
/* 'in 45m' / 'in 2h05' / 'in <1m' */
function dur(ms){
  var m=Math.floor(ms/60000);
  if(m<1) return "<1m";
  if(m<60) return m+"m";
  return Math.floor(m/60)+"h"+pad(m%60);
}
function parseLocal(s){
  /* ISO with offset -> Date; date-only -> null (all-day, no time) */
  if(!s) return null;
  if(/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  var d=new Date(s);
  return isNaN(d.getTime())?null:d;
}
/* Build the timed schedule. Never fabricates a duration:
   end is used only when it is strictly after start. */
function buildTimed(items){
  var out=[];
  for(var i=0;i<items.length;i++){
    var it=items[i], s=parseLocal(it.date);
    if(!s) continue;
    var e=parseLocal(it.end);
    if(e && e.getTime()<=s.getTime()) e=null;
    out.push({
      name:(it.name||"Untitled").trim(),
      start:s, end:e, hasEnd:!!e,
      done:!!it.done,
      room:(it.location||"").trim(),
      kind:(it.type||it.meeting_type||"").trim()
    });
  }
  out.sort(function(a,b){return a.start-b.start;});
  return out;
}
/* The whole state machine. now = Date. Returns a render spec. */
function compute(now, sched){
  var t=now.getTime(), i, ev;
  var timed=sched.filter(function(e){return !e.done;});

  /* 1. LATE — a not-done event whose end passed 3-45m ago (3m grace so a
        cleanly-finished event does not flash red the instant it ends) */
  var late=null;
  for(i=0;i<timed.length;i++){
    ev=timed[i];
    var over=t-ev.end;
    if(ev.hasEnd && over>=3*60000 && over<45*60000){
      if(!late || ev.end>late.end) late=ev;
    }
  }
  /* 2. NOW — inside a not-done event with a real end */
  var cur=null;
  for(i=0;i<timed.length;i++){
    ev=timed[i];
    if(ev.hasEnd && ev.start.getTime()<=t && t<ev.end.getTime()){
      /* latest start wins; tie broken by later end (the anchoring commitment) */
      if(!cur || ev.start>cur.start || (+ev.start===+cur.start && ev.end>cur.end)) cur=ev;
    }
  }
  /* 2b. point-in-time item (no end) that just came due, 10m grace */
  var pt=null;
  if(!cur){
    for(i=0;i<timed.length;i++){
      ev=timed[i];
      if(!ev.hasEnd && ev.start.getTime()<=t && t-ev.start.getTime()<10*60000){
        if(!pt || ev.start>pt.start) pt=ev;
      }
    }
  }
  /* 3. NEXT — first not-done start strictly ahead */
  var next=null;
  for(i=0;i<timed.length;i++){
    if(timed[i].start.getTime()>t){next=timed[i];break;}
  }
  /* tallies */
  var missed=0;
  for(i=0;i<timed.length;i++){
    ev=timed[i];
    var eff=ev.hasEnd?ev.end.getTime():ev.start.getTime();
    if(eff<=t) missed++;
  }
  var anyTimed=sched.length>0;
  var lastEnd=null;
  for(i=0;i<sched.length;i++){
    ev=sched[i];
    var z=ev.hasEnd?ev.end.getTime():ev.start.getTime();
    if(lastEnd===null||z>lastEnd) lastEnd=z;
  }

  var st;
  if(!anyTimed){
    st={state:"EMPTY",accent:"var(--faint)",chip:"Nothing scheduled",
        headline:"No timed items today",meta:[]};
  } else if(late && (!cur || late.end.getTime()>=cur.start.getTime())){
    st={state:"LATE",accent:"var(--red)",chip:"Running late",ev:late,
        headline:late.name,
        meta:[{k:"ended",v:hhmm(late.end)},{k:"over",v:dur(t-late.end.getTime())}],
        room:late.room};
  } else if(cur){
    st={state:"NOW",accent:"var(--blue)",chip:"You are here",ev:cur,
        headline:cur.name,
        meta:[{k:"range",v:hhmm(cur.start)+"\u2013"+hhmm(cur.end)},
              {k:"left",v:dur(cur.end.getTime()-t)+" left"}],
        room:cur.room};
  } else if(pt){
    st={state:"DUE",accent:"var(--amber)",chip:"Due now",ev:pt,
        headline:pt.name,
        meta:[{k:"at",v:hhmm(pt.start)}],
        room:pt.room};
  } else if(next && !sched.some(function(e){return e.start.getTime()<=t;})){
    st={state:"BEFORE",accent:"var(--green)",chip:"Day not started",
        headline:"First up "+hhmm(next.start),
        meta:[{k:"in",v:"in "+dur(next.start.getTime()-t)}]};
  } else if(next){
    st={state:"GAP",accent:"var(--green)",chip:"Clear right now",
        headline:"Free until "+hhmm(next.start),
        meta:[{k:"gap",v:dur(next.start.getTime()-t)+" of gap"}]};
  } else {
    st={state:"AFTER",accent:"var(--faint)",chip:"Day is clear from here",
        headline:"Nothing left today",
        meta:lastEnd?[{k:"last",v:"last item "+hhmm(new Date(lastEnd))}]:[]};
  }
  st.next=next;
  st.missed=missed;
  st.lastEnd=lastEnd;
  return st;
}

/* ---------- render ---------- */
function esc(s){return String(s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function nameCls(s){var n=s.length; return n>110?"name xs":(n>46?"name sm":"name");}

var RAIL_A=6, RAIL_B=24; /* 0600 -> 2400 */
function railPct(d){
  var h=d.getHours()+d.getMinutes()/60;
  return Math.max(0,Math.min(100,(h-RAIL_A)/(RAIL_B-RAIL_A)*100));
}

function render(){
  var bar=document.getElementById("bar");
  if(!DATA){return;}
  var now=new Date();
  var sched=buildTimed(DATA.today_items||[]);
  var allday=(DATA.today_items||[]).filter(function(i){return !parseLocal(i.date);});
  var st=compute(now,sched);

  var h=[];
  /* clock */
  h.push('<div class="cell c-clock"><div class="clock"><span>'+hhmm(now)+
    '</span><span class="sec">:'+pad(now.getSeconds())+'</span></div>'+
    '<div class="dateline">'+LONG[now.getDay()]+" "+pad(now.getDate())+" "+MON[now.getMonth()]+'</div></div>');

  /* state */
  var m=[];
  if(st.room) m.push('<span class="rm">'+esc(st.room)+'</span>');
  (st.meta||[]).forEach(function(x){
    if(x.k==="left"||x.k==="over"||x.k==="in"||x.k==="gap") m.push('<span class="left">'+esc(x.v)+'</span>');
    else m.push('<b>'+esc(x.v)+'</b>');
  });
  h.push('<div class="cell c-state"><div class="chip"><span class="dot"></span>'+esc(st.chip)+'</div>'+
    '<div class="'+nameCls(st.headline)+'">'+esc(st.headline)+'</div>'+
    (m.length?'<div class="meta">'+m.join("")+'</div>':'')+'</div>');

  /* next */
  if(st.next){
    var gap=st.next.start.getTime()-now.getTime();
    var rng=hhmm(st.next.start)+(st.next.hasEnd?"\u2013"+hhmm(st.next.end):"");
    h.push('<div class="cell c-next"><div class="lab">Next</div>'+
      '<div class="cd'+(gap<15*60000?" warn":"")+'">in '+dur(gap)+'</div>'+
      '<div class="nname">'+esc(st.next.name)+'</div>'+
      '<div class="nmeta">'+rng+(st.next.room?' \u00b7 <span class="rm">'+esc(st.next.room)+'</span>':"")+'</div></div>');
  } else {
    h.push('<div class="cell c-next"><div class="lab">Next</div>'+
      '<div class="cd" style="color:var(--faint)">\u2014</div>'+
      '<div class="nname">Nothing further scheduled today</div></div>');
  }

  /* tally */
  var doneN=(DATA.today_items||[]).filter(function(i){return i.done;}).length;
  h.push('<div class="cell c-tally"><div class="tally">'+
    '<div class="trow"><span class="tnum'+(st.missed?" red":"")+'">'+st.missed+'</span>past due</div>'+
    '<div class="trow"><span class="tnum green">'+doneN+'</span>done of '+(DATA.today_items||[]).length+'</div>'+
    (allday.length?'<div class="trow"><span class="tnum">'+allday.length+'</span>all-day</div>':'')+
    '</div></div>');

  /* rail */
  var ticks="";
  sched.forEach(function(e){
    var cls="tick"+(e.done?" done":(((e.hasEnd?e.end:e.start).getTime()<=now.getTime())?" miss":""));
    ticks+='<div class="'+cls+'" style="left:'+railPct(e.start).toFixed(2)+'%"></div>';
  });
  h.push('<div class="rail"><div class="railtrack"></div>'+
    '<div class="railfill" style="width:'+railPct(now).toFixed(2)+'%"></div>'+ticks+
    '<div class="now" style="left:'+railPct(now).toFixed(2)+'%"></div>'+
    '<div class="railend l">0600</div><div class="railend r">2400</div></div>');

  bar.style.setProperty("--accent",st.accent);
  bar.setAttribute("data-state",st.state);
  bar.innerHTML=h.join("");
}

function tickClock(){
  var el=document.querySelector(".clock");
  if(!el) return;
  var n=new Date();
  el.innerHTML='<span>'+hhmm(n)+'</span><span class="sec">:'+pad(n.getSeconds())+'</span>';
}

fetch("../data/tasks.json",{cache:"no-store"})
  .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
  .then(function(j){
    DATA=j; render();
    setInterval(tickClock,1000);
    setInterval(render,20000);
  })
  .catch(function(e){
    document.getElementById("bar").innerHTML='<div class="err">Data unavailable \u2014 '+esc(e.message)+'</div>';
  });