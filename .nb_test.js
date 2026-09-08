
const {buildTimed,compute,dur,hhmm}=require("./.nb_core.js");
const data=require("./docs/data/tasks.json");
const s=buildTimed(data.today_items);
for(const t of ["07:30","09:03","11:05","13:15","13:34","15:00","15:04","19:30","22:05","23:00"]){
  const now=new Date("2026-09-08T"+t+":00.000-04:00"), st=compute(now,s);
  console.log(t+" ["+st.state+"] "+st.chip+" :: "+st.headline.slice(0,60)+" :: "+(st.meta||[]).map(x=>x.v).join(" | ")+(st.room?" @"+st.room:"")+" || NEXT "+(st.next?"in "+dur(st.next.start-now)+" "+st.next.name.slice(0,32):"—"));
}
console.log("EMPTY:",compute(new Date(),[]).chip, "|", compute(new Date(),[]).headline);
