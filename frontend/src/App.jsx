import { useState, useMemo, useEffect, useRef } from "react";

// ── CONSTANTS ─────────────────────────────────────────────────────────────
const DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
const PALETTES = [
  { label:"Rose",       value:"#b76e79" },
  { label:"Sage",       value:"#7a9e7e" },
  { label:"Dusty Blue", value:"#6a8caf" },
  { label:"Terracotta", value:"#c4714f" },
  { label:"Lavender",   value:"#8e7ab5" },
  { label:"Marigold",   value:"#c9972a" },
];
const TEMPLATES = [
  { id:"morning-light", label:"🌸 Morning Light" },
  { id:"caring-hands",  label:"🤍 Caring Hands"  },
  { id:"garden",        label:"🌿 Garden"         },
];

// ── HELPERS ───────────────────────────────────────────────────────────────
function tint(hex, alpha) {
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${alpha})`;
}
function pad(n) { return String(n).padStart(2,"0"); }

function deriveSaveFolder(fullName) {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return `~/Documents/${(parts[0]||"user").toLowerCase()}-invoices`;
  const first = parts[0].toLowerCase();
  const last  = parts[parts.length-1];
  return `~/Documents/${first}-${last[0].toLowerCase()}-invoices`;
}

function weeklyPath(base, invNum)  { return `${base}/weekly/${invNum}.pdf`; }
function monthlyPath(base, y, m)   { return `${base}/monthly/RPT-${y}-${pad(m+1)}.pdf`; }

// Returns week object for a given Monday-offset from the current week
function getWeekRange(weekOffset = 0) {
  const now = new Date();
  const day = now.getDay();
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day+6)%7) + weekOffset*7);
  monday.setHours(0,0,0,0);
  const sunday = new Date(monday); sunday.setDate(monday.getDate()+6);
  const fmt     = d => d.toLocaleDateString("en-US",{month:"long", day:"numeric"});
  const fmtFull = d => d.toLocaleDateString("en-US",{month:"long", day:"numeric", year:"numeric"});
  const invNum  = `INV-${monday.getFullYear()}${pad(monday.getMonth()+1)}${pad(monday.getDate())}`;
  // Day numbers for the table: Mon=date, Tue=date+1, etc.
  const dayDates = {};
  DAYS.forEach((name,i) => {
    const d = new Date(monday); d.setDate(monday.getDate()+i);
    dayDates[name] = d.toLocaleDateString("en-US",{month:"short", day:"numeric"});
  });
  return { start:fmt(monday), end:fmtFull(sunday), invNum, monday, sunday, dayDates };
}

function getWeeksForMonth(year, month) {
  const firstDay = new Date(year, month, 1);
  const lastDay  = new Date(year, month+1, 0);
  const startDay = new Date(firstDay);
  startDay.setDate(firstDay.getDate() - ((firstDay.getDay()+6)%7));
  const weeks = [];
  let cur = new Date(startDay);
  while (cur <= lastDay) {
    const monday = new Date(cur);
    const sunday = new Date(cur); sunday.setDate(cur.getDate()+6);
    const fmt = (d,sy) => d.toLocaleDateString("en-US",{month:"short",day:"numeric",...(sy?{year:"numeric"}:{})});
    const invNum = `INV-${monday.getFullYear()}${pad(monday.getMonth()+1)}${pad(monday.getDate())}`;
    weeks.push({ monday, sunday, label:`${fmt(monday)} – ${fmt(sunday,true)}`, invNum });
    cur.setDate(cur.getDate()+7);
  }
  return weeks;
}

const defaultConfig = {
  name:           "Jane Doe",
  address:        "123 Main Street, Denver, CO 80201",
  personalEmail:  "jane@email.com",
  rate:           18.0,
  clientName:     "Sunrise Home Health Agency",
  clientEmail:    "billing@clientagency.com",
  accountantEmail:"accountant@cpa.com",
  accent:         "#b76e79",
  invoiceNote:    "Thank you for the privilege of caring for your clients.",
  saveFolder:     deriveSaveFolder("Jane Doe"),
};

// ── CHROME ────────────────────────────────────────────────────────────────
const chrome = {
  titleBar:"#2e2218", toolbar:"#241a12", previewBg:"#c8b8ac",
  border:"#4a3828", mutedText:"#a08878", brightText:"#e8d8cc",
};

// ── SHARED: HOUR INPUT ROW ────────────────────────────────────────────────
function HourRow({ label, sublabel, value, onChange, accent }) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState(String(value));
  const commit = () => {
    const n = parseInt(raw,10);
    onChange(isNaN(n) ? value : Math.max(0, Math.min(168, n)));
    setEditing(false);
  };
  return (
    <div className="day-row" style={{display:"flex",alignItems:"center",padding:"5px 3px",borderBottom:"1px solid #f0e6e0",transition:"background 0.1s",borderRadius:4}}>
      <div style={{flex:1,minWidth:0}}>
        <div style={{fontSize:13,color:"#4a3028",fontWeight:value>0?700:400}}>{label}</div>
        {sublabel && <div style={{fontSize:10,color:"#b0988a",marginTop:1}}>{sublabel}</div>}
      </div>
      <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0,marginLeft:8}}>
        <button onClick={()=>onChange(Math.max(0,value-1))}
          style={{width:21,height:21,borderRadius:"50%",border:`1.5px solid ${accent}`,background:"white",color:accent,fontSize:14,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>−</button>
        {editing ? (
          <input value={raw} onChange={e=>setRaw(e.target.value)}
            onBlur={commit} onKeyDown={e=>{if(e.key==="Enter")commit();if(e.key==="Escape")setEditing(false);}}
            style={{width:34,textAlign:"center",fontFamily:"'Playfair Display',serif",fontSize:15,border:`1.5px solid ${accent}`,borderRadius:5,padding:"1px 2px",color:"#2c1810",outline:"none"}} autoFocus/>
        ) : (
          <span onClick={()=>{setRaw(String(value));setEditing(true);}} title="Click to type"
            style={{fontFamily:"'Playfair Display',serif",fontSize:16,color:value>0?"#2c1810":"#ccc",width:28,textAlign:"center",cursor:"text",borderBottom:`1px dashed ${value>0?"#c8b0a8":"#ddd"}`}}>
            {value}
          </span>
        )}
        <button onClick={()=>onChange(Math.min(168,value+1))}
          style={{width:21,height:21,borderRadius:"50%",border:`1.5px solid ${accent}`,background:accent,color:"white",fontSize:14,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>+</button>
        {!sublabel && <span style={{fontSize:10,color:"#c0a898",width:18}}>hr</span>}
      </div>
    </div>
  );
}

// ── CONFIRM MODAL ─────────────────────────────────────────────────────────
function ConfirmModal({ savedPath, onConfirm, onCancel }) {
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.5)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:300,padding:16}}>
      <div style={{background:"white",borderRadius:16,maxWidth:360,width:"100%",overflow:"hidden",boxShadow:"0 8px 48px rgba(0,0,0,0.25)"}}>
        <div style={{background:chrome.titleBar,padding:"16px 22px"}}>
          <div style={{fontSize:10,letterSpacing:3,textTransform:"uppercase",color:"#e0c090",marginBottom:4}}>⚠ Already Sent</div>
          <div style={{fontSize:13,color:chrome.mutedText}}>This document appears to have been sent already.</div>
        </div>
        <div style={{padding:"18px 22px"}}>
          <div style={{fontSize:13,color:"#4a3028",lineHeight:1.6,marginBottom:16}}>
            A file was already saved at:<br/>
            <span style={{fontFamily:"monospace",fontSize:11,color:"#7a5030",background:"#fdf0e8",padding:"3px 7px",borderRadius:4,display:"inline-block",marginTop:4}}>{savedPath}</span>
            <br/><br/>Send again and overwrite it?
          </div>
          <div style={{display:"flex",gap:9}}>
            <button onClick={onCancel} style={{flex:1,fontSize:13,fontWeight:700,padding:"10px 0",borderRadius:9,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:"pointer"}}>Cancel</button>
            <button onClick={onConfirm} style={{flex:1,fontSize:13,fontWeight:700,padding:"10px 0",borderRadius:9,border:"none",background:"#c4714f",color:"white",cursor:"pointer"}}>Send Anyway</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── MONTHLY SCAN POPUP ────────────────────────────────────────────────────
function ScanPopup({ results, onClose }) {
  // results: [{ label, invNum, found }]
  const foundCount = results.filter(r=>r.found).length;
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:300,padding:16}}>
      <div style={{background:"white",borderRadius:16,maxWidth:400,width:"100%",overflow:"hidden",boxShadow:"0 8px 48px rgba(0,0,0,0.25)"}}>
        <div style={{background:chrome.titleBar,padding:"16px 22px"}}>
          <div style={{fontSize:10,letterSpacing:3,textTransform:"uppercase",color:"#a8c8d8",marginBottom:4}}>📁 Weekly Invoice Scan</div>
          <div style={{fontSize:13,color:chrome.mutedText}}>
            Found {foundCount} of {results.length} weekly invoices in your folder.
            {foundCount>0 && " Hours pre-filled from found files."}
          </div>
        </div>
        <div style={{padding:"16px 22px",maxHeight:300,overflowY:"auto"}}>
          {results.map((r,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"7px 0",borderBottom:i<results.length-1?"1px solid #f0ece8":"none"}}>
              <span style={{fontSize:15,flexShrink:0}}>{r.found?"✅":"❌"}</span>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontSize:12,fontWeight:600,color:"#2c1810"}}>Week {i+1} — {r.label}</div>
                <div style={{fontSize:10,fontFamily:"monospace",color:"#9a7060",marginTop:2,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.invNum}.pdf</div>
              </div>
              <span style={{fontSize:11,fontWeight:700,color:r.found?"#4a7a50":"#c07050",flexShrink:0}}>{r.found?"found":"not found"}</span>
            </div>
          ))}
        </div>
        <div style={{padding:"12px 22px",borderTop:"1px solid #f0ece8"}}>
          {foundCount < results.length && (
            <div style={{fontSize:11,color:"#9a8070",fontStyle:"italic",marginBottom:10}}>
              Missing weeks defaulted to 0 hrs — adjust manually if needed.
            </div>
          )}
          <button onClick={onClose} style={{width:"100%",fontSize:13,fontWeight:700,padding:"10px 0",borderRadius:9,border:"none",background:chrome.titleBar,color:"white",cursor:"pointer"}}>Got it</button>
        </div>
      </div>
    </div>
  );
}

// ── INVOICE TEMPLATES ─────────────────────────────────────────────────────
function InvoiceTable({ hours, config, rowEven, rowOdd, textColor, accentColor, dayDates }) {
  return (
    <table style={{width:"100%",borderCollapse:"collapse",fontSize:14,fontFamily:"sans-serif"}}>
      <thead><tr>{["Day","Hours","Rate","Amount"].map(h=>(
        <th key={h} style={{padding:`11px 38px 11px ${h==="Day"?"38px":"0"}`,textAlign:h==="Day"?"left":"right",fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:accentColor,fontWeight:700,borderBottom:"1.5px solid #e0e8e0"}}>{h}</th>
      ))}</tr></thead>
      <tbody>{DAYS.filter(d=>hours[d]>0).map((day,i)=>(
        <tr key={day} style={{background:i%2===0?rowEven:rowOdd}}>
          <td style={{padding:"12px 38px",color:textColor,fontSize:14}}>
            <span>{day}</span>
            {dayDates && <span style={{fontSize:11,color:accentColor,opacity:0.7,marginLeft:8}}>{dayDates[day]}</span>}
          </td>
          <td style={{padding:"12px 0",textAlign:"right",color:textColor,fontSize:14}}>{hours[day]}</td>
          <td style={{padding:"12px 0",textAlign:"right",color:accentColor,fontSize:14,opacity:0.7}}>${config.rate.toFixed(2)}</td>
          <td style={{padding:"12px 38px 12px 0",textAlign:"right",color:textColor,fontWeight:600,fontSize:14}}>${(hours[day]*config.rate).toFixed(2)}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

const ML_ACC="#b76e79";
function TemplateMorningLight({ config, hours, week, totalHours, totalPay }) {
  return (
    <div style={{fontFamily:"'Georgia',serif",background:"white",width:"100%",minHeight:"100%"}}>
      <div style={{background:`linear-gradient(135deg,${ML_ACC}28,${ML_ACC}48)`,borderBottom:`4px solid ${ML_ACC}`,padding:"34px 38px 28px",position:"relative"}}>
        <div style={{fontSize:13,color:ML_ACC,letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7,fontFamily:"sans-serif"}}><span style={{fontSize:15}}>🌸</span> Home Health Invoice</div>
        <h1 style={{margin:0,fontSize:27,fontWeight:700,color:"#2c1810",letterSpacing:-0.5}}>{config.name}</h1>
        <p style={{margin:"7px 0 3px",fontSize:13,color:"#6a4a40",fontFamily:"sans-serif"}}>{config.address}</p>
        <p style={{margin:0,fontSize:13,color:"#6a4a40",fontFamily:"sans-serif"}}>{config.personalEmail}</p>
        <div style={{position:"absolute",right:38,top:34,textAlign:"right"}}>
          <div style={{fontSize:10,fontFamily:"sans-serif",letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC}}>Invoice</div>
          <div style={{fontSize:16,color:"#2c1810",fontWeight:700,fontFamily:"monospace",marginTop:4}}>{week.invNum}</div>
          <div style={{fontSize:13,fontFamily:"sans-serif",color:"#9a8070",marginTop:6}}>{week.end}</div>
        </div>
      </div>
      <div style={{background:`${ML_ACC}0a`,padding:"26px 38px 22px",borderBottom:`1px solid ${ML_ACC}22`,display:"flex",gap:52}}>
        <div><div style={{fontSize:10,fontFamily:"sans-serif",letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC,marginBottom:7}}>Billed To</div>
          <div style={{fontSize:15,fontWeight:700,color:"#2c1810",fontFamily:"sans-serif"}}>{config.clientName}</div>
          <div style={{fontSize:13,fontFamily:"sans-serif",color:"#6a4a40",marginTop:3}}>{config.clientEmail}</div></div>
        <div><div style={{fontSize:10,fontFamily:"sans-serif",letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC,marginBottom:7}}>Week Of</div>
          <div style={{fontSize:14,color:"#2c1810",fontFamily:"sans-serif"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="white" rowOdd="#fdf8f4" accentColor={ML_ACC} textColor="#2c1810" dayDates={week.dayDates}/></div>
      <div style={{margin:"0 38px",borderTop:`2px solid ${ML_ACC}44`,marginTop:8,paddingTop:20,paddingBottom:14,display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
        <div style={{fontFamily:"sans-serif",fontSize:13,color:"#9a8070"}}>{totalHours} hrs · ${config.rate.toFixed(2)}/hr</div>
        <div style={{textAlign:"right"}}>
          <div style={{fontFamily:"sans-serif",fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC,marginBottom:4}}>Total Due</div>
          <div style={{fontSize:30,fontWeight:700,color:ML_ACC,fontFamily:"'Georgia',serif"}}>${totalPay}</div>
        </div>
      </div>
      <div style={{background:`${ML_ACC}12`,borderTop:`1px solid ${ML_ACC}22`,padding:"15px 38px",fontFamily:"sans-serif",fontSize:12,color:"#9a8070",fontStyle:"italic",textAlign:"center"}}>{config.invoiceNote}</div>
    </div>
  );
}

const CH_ACC="#7ab5a8";
function TemplateCaringHands({ config, hours, week, totalHours, totalPay }) {
  return (
    <div style={{fontFamily:"sans-serif",background:"white",width:"100%",minHeight:"100%"}}>
      <div style={{background:"#1a2a3a",padding:"34px 38px 28px",position:"relative"}}>
        <div style={{fontSize:13,color:CH_ACC,letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7}}><span style={{fontSize:15}}>🤍</span> Home Health Invoice</div>
        <div style={{fontSize:27,fontWeight:700,color:"white",marginBottom:7}}>{config.name}</div>
        <div style={{fontSize:13,color:"#8aacaa"}}>{config.address}</div>
        <div style={{fontSize:13,color:"#8aacaa",marginTop:2}}>{config.personalEmail}</div>
        <div style={{position:"absolute",right:38,top:34,textAlign:"right"}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC}}>Invoice</div>
          <div style={{fontSize:16,color:"white",fontWeight:700,fontFamily:"monospace",marginTop:4}}>{week.invNum}</div>
          <div style={{fontSize:13,color:"#8aacaa",marginTop:6}}>{week.end}</div>
        </div>
      </div>
      <div style={{height:4,background:`linear-gradient(90deg,${CH_ACC},${CH_ACC}66)`}}/>
      <div style={{background:"#f4f8f8",padding:"24px 38px 22px",display:"flex",gap:52,borderBottom:"1px solid #e0eeec"}}>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC,marginBottom:7}}>Billed To</div>
          <div style={{fontSize:15,fontWeight:700,color:"#1a2a3a"}}>{config.clientName}</div>
          <div style={{fontSize:13,color:"#4a6a60",marginTop:3}}>{config.clientEmail}</div></div>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC,marginBottom:7}}>Service Period</div>
          <div style={{fontSize:14,color:"#1a2a3a"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="white" rowOdd="#f4f9f8" accentColor={CH_ACC} textColor="#1a2a3a" dayDates={week.dayDates}/></div>
      <div style={{margin:"26px 38px 18px",display:"flex",justifyContent:"flex-end"}}>
        <div style={{background:"#1a2a3a",borderRadius:10,padding:"16px 28px",textAlign:"right"}}>
          <div style={{fontSize:11,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC,marginBottom:6}}>{totalHours} hours · Total Due</div>
          <div style={{fontSize:30,fontWeight:700,color:"white"}}>${totalPay}</div>
        </div>
      </div>
      <div style={{borderTop:"1px solid #d8eae8",padding:"15px 38px",fontSize:12,color:"#7a9a90",fontStyle:"italic",textAlign:"center"}}>{config.invoiceNote}</div>
    </div>
  );
}

const GD_ACC="#5a8a5a";
function TemplateGarden({ config, hours, week, totalHours, totalPay }) {
  return (
    <div style={{fontFamily:"sans-serif",background:"#fffef8",width:"100%",minHeight:"100%"}}>
      <div style={{background:"linear-gradient(135deg,#2d4a2d,#3d6b3d)",padding:"34px 38px 28px",position:"relative"}}>
        <div style={{fontSize:13,color:"#a8d8a0",letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7}}><span style={{fontSize:15}}>🌿</span> Home Health Invoice</div>
        <div style={{fontSize:27,fontWeight:400,color:"#e8f5e4",letterSpacing:0.5}}>{config.name}</div>
        <div style={{fontSize:13,color:"#a8c8a0",marginTop:6}}>{config.address}</div>
        <div style={{fontSize:13,color:"#a8c8a0",marginTop:2}}>{config.personalEmail}</div>
        <div style={{position:"absolute",right:38,top:34,background:"rgba(255,255,255,0.1)",borderRadius:10,padding:"13px 20px",textAlign:"right"}}>
          <div style={{fontSize:10,color:"#a8d8a0",letterSpacing:1.5,textTransform:"uppercase",marginBottom:4}}>Invoice</div>
          <div style={{fontSize:16,color:"white",fontWeight:700,fontFamily:"monospace"}}>{week.invNum}</div>
          <div style={{fontSize:13,color:"#a8c8a0",marginTop:4}}>{week.end}</div>
        </div>
      </div>
      <div style={{background:"#5a8a5a",padding:"6px 38px",fontSize:11,color:"#c8e8c0",letterSpacing:4}}>✦ ✦ ✦</div>
      <div style={{background:"#f6fbf4",padding:"24px 38px 22px",borderBottom:"1px solid #d0e8c8",display:"flex",gap:52}}>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:GD_ACC,marginBottom:7}}>Billed To</div>
          <div style={{fontSize:15,fontWeight:700,color:"#2d4a2d"}}>{config.clientName}</div>
          <div style={{fontSize:13,color:"#6a8a60",marginTop:3}}>{config.clientEmail}</div></div>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:GD_ACC,marginBottom:7}}>Service Week</div>
          <div style={{fontSize:14,color:"#2d4a2d"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="#fffef8" rowOdd="#f4f8f0" accentColor={GD_ACC} textColor="#2d4a2d" dayDates={week.dayDates}/></div>
      <div style={{margin:"0 38px",borderTop:"2px dashed #b8d8b0",marginTop:8,paddingTop:20,paddingBottom:14,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div style={{fontSize:13,color:"#7a9a70"}}>{totalHours} hrs · ${config.rate.toFixed(2)}/hr</div>
        <div style={{textAlign:"right"}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:GD_ACC,marginBottom:4}}>Total Due</div>
          <div style={{fontSize:30,fontWeight:700,color:"#2d4a2d"}}>${totalPay}</div>
        </div>
      </div>
      <div style={{background:"#f0f8ec",borderTop:"1px solid #c0d8b8",padding:"15px 38px",fontSize:12,color:"#7a9a70",fontStyle:"italic",textAlign:"center"}}>{config.invoiceNote}</div>
    </div>
  );
}

// ── MONTHLY REPORT PDF ────────────────────────────────────────────────────
function MonthlyReportPDF({ config, weekData, monthLabel }) {
  const totalHours = weekData.reduce((s,w)=>s+w.hours,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const worked     = weekData.filter(w=>w.hours>0);
  return (
    <div style={{fontFamily:"sans-serif",background:"white",width:"100%",minHeight:"100%"}}>
      <div style={{background:"linear-gradient(135deg,#2c3e50,#3d5468)",padding:"34px 38px 28px",position:"relative"}}>
        <div style={{fontSize:13,color:"#a8c8d8",letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7}}><span style={{fontSize:15}}>📋</span> Monthly Hours Summary</div>
        <div style={{fontSize:27,fontWeight:700,color:"white",marginBottom:7}}>{config.name}</div>
        <div style={{fontSize:13,color:"#8aacbc"}}>{config.address}</div>
        <div style={{fontSize:13,color:"#8aacbc",marginTop:2}}>{config.personalEmail}</div>
        <div style={{position:"absolute",right:38,top:34,textAlign:"right"}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#a8c8d8"}}>Report Period</div>
          <div style={{fontSize:18,color:"white",fontWeight:700,marginTop:4}}>{monthLabel}</div>
        </div>
      </div>
      <div style={{height:4,background:"linear-gradient(90deg,#7ab5c8,#7ab5c888)"}}/>
      <div style={{background:"#f4f8fa",padding:"22px 38px 20px",display:"flex",gap:52,borderBottom:"1px solid #d8eaf0"}}>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:7}}>Submitted To</div>
          <div style={{fontSize:13,fontWeight:700,color:"#1a2a3a"}}>{config.clientName}</div>
          <div style={{fontSize:12,color:"#4a6a70",marginTop:2}}>{config.clientEmail}</div></div>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:7}}>Prepared For</div>
          <div style={{fontSize:13,fontWeight:700,color:"#1a2a3a"}}>Accountant of Record</div>
          <div style={{fontSize:12,color:"#4a6a70",marginTop:2}}>{config.accountantEmail}</div></div>
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:7}}>Rate</div>
          <div style={{fontSize:16,fontWeight:700,color:"#1a2a3a"}}>${config.rate.toFixed(2)}<span style={{fontSize:11,fontWeight:400,color:"#5a8090"}}>/hr</span></div></div>
      </div>
      <div style={{paddingTop:6}}>
        <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
          <thead><tr>{["Week","Period","Hours","Rate","Amount"].map(h=>(
            <th key={h} style={{padding:`10px 38px 10px ${h==="Week"?"38px":"0"}`,textAlign:h==="Week"||h==="Period"?"left":"right",fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",fontWeight:700,borderBottom:"1.5px solid #d8eaf0"}}>{h}</th>
          ))}</tr></thead>
          <tbody>{weekData.map((w,i)=>(
            <tr key={i} style={{background:i%2===0?"white":"#f6fbfd",opacity:w.hours===0?0.4:1}}>
              <td style={{padding:"12px 38px",color:"#1a2a3a",fontWeight:600}}>Week {i+1}</td>
              <td style={{padding:"12px 0",color:"#4a6a70",fontSize:12}}>{w.label}</td>
              <td style={{padding:"12px 0",textAlign:"right",color:"#1a2a3a"}}>{w.hours}</td>
              <td style={{padding:"12px 0",textAlign:"right",color:"#5a90a8",opacity:0.8}}>${config.rate.toFixed(2)}</td>
              <td style={{padding:"12px 38px 12px 0",textAlign:"right",color:w.hours>0?"#1a2a3a":"#aaa",fontWeight:w.hours>0?600:400}}>
                {w.hours>0?`$${(w.hours*config.rate).toFixed(2)}`:"—"}
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div style={{margin:"20px 38px 18px",display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
        <div style={{fontSize:13,color:"#7a9aaa"}}>{worked.length} week{worked.length!==1?"s":""} worked · ${config.rate.toFixed(2)}/hr</div>
        <div style={{background:"#2c3e50",borderRadius:10,padding:"16px 28px",textAlign:"right"}}>
          <div style={{fontSize:11,letterSpacing:1.5,textTransform:"uppercase",color:"#a8c8d8",marginBottom:6}}>{totalHours} total hours · Amount Due</div>
          <div style={{fontSize:30,fontWeight:700,color:"white"}}>${totalPay}</div>
        </div>
      </div>
      <div style={{margin:"0 38px 20px",borderTop:"1px dashed #c8dce8",paddingTop:16,display:"flex",gap:48}}>
        <div style={{flex:1}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:20}}>Provider Signature</div>
          <div style={{borderBottom:"1px solid #1a2a3a",height:1,width:"80%"}}/>
          <div style={{fontSize:11,color:"#7a9aaa",marginTop:5}}>{config.name}</div>
        </div>
        <div style={{flex:1}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:20}}>Date</div>
          <div style={{borderBottom:"1px solid #1a2a3a",height:1,width:"60%"}}/>
        </div>
      </div>
      <div style={{background:"#f4f8fa",borderTop:"1px solid #d8eaf0",padding:"13px 38px",fontSize:11,color:"#7a9aaa",textAlign:"center",fontStyle:"italic"}}>
        This summary is provided for accounting and tax purposes. Weekly invoices are available upon request.
      </div>
    </div>
  );
}

// ── SHELL ─────────────────────────────────────────────────────────────────
function Shell({ config, title, subtitle, onBack, children }) {
  return (
    <div style={{height:"100vh",display:"flex",flexDirection:"column",background:chrome.titleBar,overflow:"hidden"}}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap');*{box-sizing:border-box}.day-row:hover{background:#fbeee8!important}.tmpl-btn,.bsm{transition:all 0.15s}.tmpl-btn:hover,.bsm:hover{opacity:0.85}::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:#d0c0b8;border-radius:3px}`}</style>
      <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"10px 20px",display:"flex",alignItems:"center",gap:14,flexShrink:0}}>
        {onBack && <button onClick={onBack} style={{fontSize:12,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:6,padding:"4px 11px",cursor:"pointer"}}>← Back</button>}
        <span style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:config.accent,display:"flex",alignItems:"center",gap:6}}><span>♥</span> {title}</span>
        {subtitle && <><div style={{width:1,height:14,background:chrome.border}}/><span style={{fontSize:13,color:chrome.brightText}}>{subtitle}</span></>}
      </div>
      {children}
    </div>
  );
}

// ── NOTIFICATION CARD ─────────────────────────────────────────────────────
function NotifCard({ notification, onDismiss }) {
  // Handle error notifications
  if (notification.error) {
    return (
      <div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
          <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#c4714f"}}>Error</div>
          <button onClick={onDismiss} style={{fontSize:11,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
        </div>
        <div style={{background:"#fff5f2",border:"1px solid #f0c8b8",borderRadius:8,padding:"11px 13px"}}>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:15,color:"#4a2010",marginBottom:4}}>⚠ Failed</div>
          <div style={{fontSize:12,color:"#7a4030",lineHeight:1.5}}>{notification.error}</div>
        </div>
      </div>
    );
  }

  // Handle success notifications
  return (
    <div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
        <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#6a9a70"}}>Sent</div>
        <button onClick={onDismiss} style={{fontSize:11,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
      </div>
      <div style={{background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:8,padding:"11px 13px"}}>
        <div style={{fontFamily:"'Playfair Display',serif",fontSize:15,color:"#2d4a2d",marginBottom:7}}>✓ Sent!</div>
        {notification.sent.map(e=><div key={e} style={{fontSize:12,color:"#4a7a50",marginBottom:3}}>✉ {e}</div>)}
        <div style={{fontSize:12,color:"#4a7a50",marginTop:4,paddingTop:6,borderTop:"1px solid #c8e8c8",display:"flex",alignItems:"center",gap:5}}>
          <span>💾</span> {notification.saved}
        </div>
      </div>
    </div>
  );
}

// ── LANDING ───────────────────────────────────────────────────────────────
function LandingPage({ config, onNav }) {
  const acc  = config.accent;
  const week = getWeekRange(0);
  const now  = new Date();
  const monthName = now.toLocaleDateString("en-US",{month:"long",year:"numeric"});
  const cards = [
    { id:"weekly",  emoji:"📄", label:"Weekly Invoice",  desc:`Week of ${week.start} – ${week.end}`, primary:true  },
    { id:"monthly", emoji:"📊", label:"Monthly Report",  desc:monthName,                              primary:false },
    { id:"profile", emoji:"👤", label:"Edit Profile",    desc:"Name, rate, contacts & folder",        primary:false },
  ];
  return (
    <Shell config={config} title="Home Health Invoice" subtitle={config.name}>
      <div style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:14,padding:"32px 24px",background:"linear-gradient(160deg,#f9f3ee,#f2ebe4)"}}>
        <div style={{textAlign:"center",marginBottom:8}}>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:26,color:"#2c1810",fontWeight:700,marginBottom:4}}>
            Good {now.getHours()<12?"Morning":"Afternoon"}, {config.name.split(" ")[0]} 👋
          </div>
          <div style={{fontFamily:"sans-serif",fontSize:13,color:"#9a8070"}}>What would you like to do today?</div>
        </div>
        {cards.map(c=>(
          <button key={c.id} onClick={()=>onNav(c.id)} style={{width:"100%",maxWidth:380,padding:"22px 28px",borderRadius:16,cursor:"pointer",border:c.primary?`2px solid ${acc}`:"2px solid #e8ddd4",background:c.primary?`linear-gradient(135deg,${acc},${tint(acc,0.85)})`:"white",color:c.primary?"white":"#2c1810",textAlign:"left",display:"flex",alignItems:"center",gap:18,boxShadow:c.primary?`0 6px 24px ${tint(acc,0.3)}`:"0 2px 12px rgba(0,0,0,0.06)",transition:"transform 0.1s,box-shadow 0.1s"}}
            onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-2px)";e.currentTarget.style.boxShadow=c.primary?`0 10px 28px ${tint(acc,0.35)}`:"0 6px 20px rgba(0,0,0,0.1)";}}
            onMouseLeave={e=>{e.currentTarget.style.transform="translateY(0)";e.currentTarget.style.boxShadow=c.primary?`0 6px 24px ${tint(acc,0.3)}`:"0 2px 12px rgba(0,0,0,0.06)";}}>
            <span style={{fontSize:32}}>{c.emoji}</span>
            <div>
              <div style={{fontFamily:"'Playfair Display',serif",fontSize:18,fontWeight:700,marginBottom:3}}>{c.label}</div>
              <div style={{fontFamily:"sans-serif",fontSize:13,opacity:0.75}}>{c.desc}</div>
            </div>
            <span style={{marginLeft:"auto",fontSize:18,opacity:0.5}}>→</span>
          </button>
        ))}
        {/* Clickable "Saving to" — navigates to profile folder section */}
        <button onClick={()=>onNav("profile-folder")}
          style={{fontSize:11,color:"#9a8070",background:"none",border:"1px dashed #d0c0b0",borderRadius:8,padding:"6px 14px",cursor:"pointer",marginTop:4,transition:"all 0.15s"}}
          onMouseEnter={e=>{e.currentTarget.style.borderColor=acc;e.currentTarget.style.color=acc;}}
          onMouseLeave={e=>{e.currentTarget.style.borderColor="#d0c0b0";e.currentTarget.style.color="#9a8070";}}>
          📁 Saving to <span style={{fontFamily:"monospace"}}>{config.saveFolder}</span> — click to change
        </button>
      </div>
    </Shell>
  );
}

// ── PROFILE PAGE ──────────────────────────────────────────────────────────
function ProfilePage({ config, onSave, onBack, scrollToFolder }) {
  const [draft, setDraft] = useState(config);
  const [folderOverridden, setFolderOverridden] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const folderRef = useRef(null);
  const acc = draft.accent;

  // Scroll to folder section if requested
  useEffect(()=>{
    if (scrollToFolder && folderRef.current) {
      setTimeout(()=>folderRef.current.scrollIntoView({ behavior:"smooth", block:"center" }), 120);
    }
  },[scrollToFolder]);

  const updateField = (key, value) => {
    setDraft(d => {
      const next = {...d,[key]:value};
      if (key==="name" && !folderOverridden) next.saveFolder = deriveSaveFolder(value);
      return next;
    });
  };

  // Save profile changes to persistent storage via API
  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      // POST updated config to backend for persistence
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft)
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to save configuration`);
      }
      // Update local state only after successful save (pessimistic update for data integrity)
      onSave(draft);
      setSaving(false);
      onBack();
    } catch (error) {
      console.error('Save failed:', error);
      setSaveError(error.message);
      setSaving(false);
    }
  };

  return (
    <Shell config={draft} title="Edit Profile" onBack={onBack}>
      {/* Fixed-height scrollable body — buttons stay inside the scroll area, not pinned outside */}
      <div style={{flex:1,overflowY:"auto",background:"#f9f3ee",padding:"28px 16px 32px"}}>
        <div style={{width:"100%",maxWidth:480,margin:"0 auto"}}>

          <div style={{background:"white",borderRadius:16,overflow:"hidden",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:16}}>
            <div style={{background:chrome.titleBar,padding:"16px 24px"}}>
              <div style={{fontSize:10,letterSpacing:3,textTransform:"uppercase",color:acc,marginBottom:4}}>👤 Invoice Details</div>
              <div style={{fontSize:13,color:chrome.mutedText}}>This info appears on every invoice and report.</div>
            </div>
            <div style={{padding:"20px 24px"}}>
              {[
                {label:"Full Name",            key:"name"},
                {label:"Address",              key:"address"},
                {label:"Personal Email",       key:"personalEmail"},
                {label:"Hourly Rate ($)",       key:"rate",type:"number"},
                {label:"Client / Agency Name", key:"clientName"},
                {label:"Client Email",         key:"clientEmail"},
                {label:"Accountant Email",     key:"accountantEmail"},
                {label:"Invoice Footer Note",  key:"invoiceNote"},
              ].map(({label,key,type})=>(
                <div key={key} style={{marginBottom:13}}>
                  <label style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",display:"block",marginBottom:4}}>{label}</label>
                  <input type={type||"text"} value={draft[key]} onChange={e=>updateField(key,e.target.value)}
                    style={{width:"100%",fontSize:14,border:"1.5px solid #e8ddd8",borderRadius:8,padding:"9px 12px",color:"#2c1810",outline:"none",background:"#fdfaf8"}}/>
                </div>
              ))}

              {/* Save folder — scrollable target */}
              <div ref={folderRef} style={{marginBottom:13,scrollMarginTop:24}}>
                <label style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",display:"block",marginBottom:4}}>
                  Save Folder
                  {!folderOverridden && <span style={{marginLeft:8,fontSize:9,color:"#b0988a",fontStyle:"italic",textTransform:"none"}}>auto-derived from name</span>}
                </label>
                <input value={draft.saveFolder}
                  onChange={e=>{setFolderOverridden(true);setDraft(d=>({...d,saveFolder:e.target.value}));}}
                  style={{width:"100%",fontSize:13,fontFamily:"monospace",border:"1.5px solid #e8ddd8",borderRadius:8,padding:"9px 12px",color:"#5a4030",outline:"none",background:"#fdfaf8"}}/>
                {folderOverridden && (
                  <button onClick={()=>{setFolderOverridden(false);setDraft(d=>({...d,saveFolder:deriveSaveFolder(d.name)}));}}
                    style={{fontSize:11,color:acc,background:"none",border:"none",cursor:"pointer",marginTop:4,padding:0}}>↺ Reset to auto-derived</button>
                )}
                <div style={{background:"#f8f4f0",borderRadius:8,padding:"10px 12px",fontSize:11,color:"#9a8070",marginTop:8}}>
                  📄 Weekly → <span style={{fontFamily:"monospace"}}>{draft.saveFolder}/weekly/</span><br/>
                  📊 Monthly → <span style={{fontFamily:"monospace"}}>{draft.saveFolder}/monthly/</span>
                </div>
              </div>
            </div>
          </div>

          {/* Color picker */}
          <div style={{background:"white",borderRadius:16,padding:"20px 24px",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:20}}>
            <div style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",marginBottom:12}}>Color Palette</div>
            <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
              {PALETTES.map(p=>(
                <button key={p.value} onClick={()=>setDraft(d=>({...d,accent:p.value}))} title={p.label}
                  style={{width:36,height:36,borderRadius:"50%",background:p.value,border:draft.accent===p.value?`3px solid ${chrome.titleBar}`:"3px solid transparent",cursor:"pointer",transition:"all 0.15s"}}/>
              ))}
            </div>
          </div>

          {/* Error message if save failed */}
          {saveError && (
            <div style={{background:"#fef3e8",border:"1.5px solid #e8b060",borderRadius:10,padding:"12px 16px",marginBottom:12}}>
              <div style={{fontSize:11,fontWeight:700,color:"#8a5010",marginBottom:3}}>⚠️ Save Failed</div>
              <div style={{fontSize:11,color:"#a87020"}}>{saveError}</div>
            </div>
          )}

          {/* Buttons — inside scroll area so they're never clipped */}
          <div style={{display:"flex",gap:10}}>
            <button onClick={onBack} disabled={saving} style={{flex:1,fontSize:13,fontWeight:700,padding:"12px 0",borderRadius:10,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:saving?"not-allowed":"pointer",opacity:saving?0.5:1}}>Cancel</button>
            <button onClick={handleSave} disabled={saving} style={{flex:2,fontSize:13,fontWeight:700,padding:"12px 0",borderRadius:10,border:"none",background:acc,color:"white",cursor:saving?"wait":"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`,opacity:saving?0.7:1}}>
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── WEEKLY PAGE ───────────────────────────────────────────────────────────
function WeeklyPage({ config, onBack }) {
  const [weekOffset, setWeekOffset] = useState(0);
  const week  = useMemo(()=>getWeekRange(weekOffset),[weekOffset]);
  const acc   = config.accent;
  const savedPath = weeklyPath(config.saveFolder, week.invNum);

  const [hours, setHours] = useState({Monday:8,Tuesday:8,Wednesday:8,Thursday:8,Friday:8,Saturday:0,Sunday:0});
  const [clientEmail,     setClientEmail]     = useState(config.clientEmail);
  const [accountantEmail, setAccountantEmail] = useState(config.accountantEmail);
  const [zoom,            setZoom]            = useState(0.75);
  const [activeTemplate,  setActiveTemplate]  = useState("morning-light");
  const [notification,    setNotification]    = useState(null);
  const [alreadySaved,    setAlreadySaved]    = useState(false);
  const [savedDate,       setSavedDate]       = useState(null);
  const [showConfirm,     setShowConfirm]     = useState(false);

  // Reset state when week changes, re-default hours to 8/day
  useEffect(()=>{
    setHours({Monday:8,Tuesday:8,Wednesday:8,Thursday:8,Friday:8,Saturday:0,Sunday:0});
    setNotification(null); setAlreadySaved(false);
  },[weekOffset]);

  const totalHours = Object.values(hours).reduce((a,b)=>a+b,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const setHour    = (day,v) => setHours(h=>({...h,[day]:v}));

  const doSend = async () => {
    setNotification(null); setShowConfirm(false);

    try {
      // Build payload for weekly submit API
      const payload = {
        hours,
        clientEmail,
        accountantEmail,
        week: {
          start: week.start,
          end: week.end,
          invNum: week.invNum
        },
        template: activeTemplate
      };

      const response = await fetch('/api/submit/weekly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}: Failed to submit weekly invoice`);
      }

      const data = await response.json();

      // Update UI with actual response data
      const dateStr = new Date().toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
      setNotification({
        sent: data.sent || [clientEmail, accountantEmail],
        saved: data.saved || savedPath
      });
      setAlreadySaved(true);
      setSavedDate(dateStr);

    } catch (error) {
      console.error('Weekly submit failed:', error);
      setNotification({
        error: error.message || 'Failed to submit weekly invoice. Please try again.'
      });
    }
  };

  const handleSubmit = async () => {
    // Pre-flight check: does this invoice already exist?
    try {
      const scanResponse = await fetch(`/api/scan?folder=${encodeURIComponent(config.saveFolder)}&invNum=${week.invNum}`);

      if (scanResponse.ok) {
        const scanData = await scanResponse.json();

        // If PDF already exists, show confirmation dialog before overwriting
        if (scanData.found) {
          setShowConfirm(true);
          return;
        }
      }

      // No existing PDF or scan failed - proceed with submit
      doSend();

    } catch (error) {
      console.error('Pre-flight scan failed:', error);
      // If scan fails, proceed anyway (don't block the user)
      doSend();
    }
  };

  const PreviewComponent = activeTemplate==="morning-light"?TemplateMorningLight:activeTemplate==="caring-hands"?TemplateCaringHands:TemplateGarden;
  const LETTER_W=680, LETTER_H=Math.round(LETTER_W*(11/8.5));

  const isCurrent = weekOffset === 0;
  const weekLabel = isCurrent ? `${week.start} – ${week.end}` : weekOffset < 0 ? `${week.start} – ${week.end} (past)` : `${week.start} – ${week.end} (future)`;

  return (
    <Shell config={config} title="Weekly Invoice" subtitle={weekLabel} onBack={onBack}>
      {showConfirm && <ConfirmModal savedPath={savedPath} onConfirm={doSend} onCancel={()=>setShowConfirm(false)}/>}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        {/* PDF */}
        <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
          {/* Toolbar: templates left | zoom center | week nav right */}
          <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"7px 14px",display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
            <span style={{fontSize:9,letterSpacing:2,textTransform:"uppercase",color:chrome.mutedText,marginRight:2}}>Template</span>
            {TEMPLATES.map(t=>(
              <button key={t.id} className="tmpl-btn" onClick={()=>setActiveTemplate(t.id)} style={{fontFamily:"sans-serif",fontSize:11,padding:"4px 10px",borderRadius:20,border:`1px solid ${activeTemplate===t.id?acc:chrome.border}`,background:activeTemplate===t.id?acc:"transparent",color:activeTemplate===t.id?"white":chrome.mutedText,cursor:"pointer"}}>{t.label}</button>
            ))}
            {/* Zoom — center */}
            <div style={{flex:1,display:"flex",justifyContent:"center",alignItems:"center",gap:5}}>
              <button className="bsm" onClick={()=>setZoom(z=>Math.max(0.4,+(z-0.05).toFixed(2)))} style={{width:24,height:24,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:15,display:"flex",alignItems:"center",justifyContent:"center"}}>−</button>
              <span style={{fontSize:11,color:chrome.mutedText,width:36,textAlign:"center"}}>{Math.round(zoom*100)}%</span>
              <button className="bsm" onClick={()=>setZoom(z=>Math.min(1.4,+(z+0.05).toFixed(2)))} style={{width:24,height:24,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:15,display:"flex",alignItems:"center",justifyContent:"center"}}>+</button>
            </div>
            {/* Week nav — right */}
            <div style={{display:"flex",alignItems:"center",gap:7}}>
              <button className="bsm" onClick={()=>setWeekOffset(o=>o-1)} style={{fontSize:14,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,width:26,height:26,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}>‹</button>
              <span style={{fontSize:12,color:isCurrent?acc:chrome.mutedText,fontWeight:isCurrent?700:400,minWidth:52,textAlign:"center"}}>
                {isCurrent?"This week":weekOffset<0?`${Math.abs(weekOffset)}w ago`:`+${weekOffset}w`}
              </span>
              <button className="bsm" onClick={()=>setWeekOffset(o=>o+1)} style={{fontSize:14,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,width:26,height:26,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}>›</button>
            </div>
          </div>
          <div style={{flex:1,overflowY:"auto",overflowX:"auto",display:"flex",justifyContent:"center",alignItems:"flex-start",padding:"24px 20px",background:chrome.previewBg}}>
            <div style={{width:LETTER_W*zoom,minHeight:LETTER_H*zoom,flexShrink:0,boxShadow:"0 4px 32px rgba(0,0,0,0.25)",background:"white",overflow:"hidden"}}>
              <div style={{transform:`scale(${zoom})`,transformOrigin:"top left",width:LETTER_W}}>
                <PreviewComponent config={config} hours={hours} week={week} totalHours={totalHours} totalPay={totalPay}/>
              </div>
            </div>
          </div>
        </div>
        {/* Editor */}
        <div style={{width:288,background:"#fdf8f4",borderLeft:"1px solid #e8ddd4",display:"flex",flexDirection:"column",overflow:"hidden",flexShrink:0}}>
          <div style={{flex:1,display:"flex",flexDirection:"column",padding:"13px 16px 0",overflow:"hidden"}}>
            <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:5}}>Hours This Week</div>
            <div style={{flex:"0 0 auto"}}>
              {DAYS.map(day=>(
                <HourRow key={day} label={day} value={hours[day]} onChange={v=>setHour(day,v)} accent={acc}/>
              ))}
            </div>
            <div style={{background:"white",borderRadius:8,padding:"8px 12px",margin:"7px 0 5px",display:"flex",justifyContent:"space-between",border:`1px solid ${acc}22`,flexShrink:0}}>
              <div><div style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Hours</div>
                <div style={{fontFamily:"'Playfair Display',serif",fontSize:19,color:"#2c1810",lineHeight:1.1}}>{totalHours}</div></div>
              <div style={{textAlign:"right"}}><div style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Total Due</div>
                <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,color:acc,fontWeight:700,lineHeight:1.1}}>${totalPay}</div></div>
            </div>
            {/* Saved status pill */}
            <div style={{flexShrink:0,marginBottom:6}}>
              {alreadySaved ? (
                <div style={{display:"inline-flex",alignItems:"center",gap:5,background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:20,padding:"3px 10px",fontSize:10,color:"#4a7a50",maxWidth:"100%",overflow:"hidden"}}>
                  <span>💾</span>
                  <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                    Saved · {week.invNum} · {savedDate}
                  </span>
                </div>
              ) : (
                <div style={{display:"inline-flex",alignItems:"center",gap:5,background:"#f5f0eb",border:"1px solid #e0d4cc",borderRadius:20,padding:"3px 10px",fontSize:10,color:"#9a8070"}}>
                  <span style={{fontSize:9}}>○</span> Not yet saved for this week
                </div>
              )}
            </div>
            <div style={{margin:"6px 0 0",flexShrink:0}}>
              {notification ? (
                <NotifCard notification={notification} onDismiss={()=>setNotification(null)}/>
              ) : (
                <div>
                  <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Send To</div>
                  {[{label:"Client",value:clientEmail,set:setClientEmail},{label:"Accountant",value:accountantEmail,set:setAccountantEmail}].map(({label,value,set})=>(
                    <div key={label} style={{marginBottom:7}}>
                      <div style={{fontSize:11,color:"#b0988a",marginBottom:3}}>{label}</div>
                      <input value={value} onChange={e=>set(e.target.value)}
                        style={{width:"100%",fontSize:13,border:"1.5px solid #e8ddd8",borderRadius:6,padding:"6px 9px",color:"#2c1810",outline:"none",background:"white"}}
                        onFocus={e=>{e.target.style.borderColor=acc;e.target.style.boxShadow=`0 0 0 2px ${tint(acc,0.12)}`;}}
                        onBlur={e=>{e.target.style.borderColor="#e8ddd8";e.target.style.boxShadow="none";}}/>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{flex:1}}/>
          </div>
          <div style={{padding:"10px 16px 14px",borderTop:"1px solid #eee0d8",flexShrink:0,background:"#fdf8f4"}}>
            <button onClick={handleSubmit} style={{width:"100%",fontSize:14,fontWeight:700,padding:"12px 0",borderRadius:9,border:"none",background:`linear-gradient(135deg,${acc},${acc}bb)`,color:"white",cursor:"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`}}>
              Save &amp; Submit ✉
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── MONTHLY PAGE ──────────────────────────────────────────────────────────
function MonthlyPage({ config, onBack }) {
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [zoom,  setZoom]  = useState(0.75);
  const [notification, setNotification] = useState(null);
  const [alreadySaved, setAlreadySaved] = useState(false);
  const [showConfirm,  setShowConfirm]  = useState(false);
  const [scanPopup,    setScanPopup]    = useState(null); // null | results[]
  const acc = config.accent;

  const weeks     = useMemo(()=>getWeeksForMonth(year,month),[year,month]);
  const [weekHours, setWeekHours] = useState(()=>weeks.map(()=>0));
  const monthLabel  = new Date(year,month,1).toLocaleDateString("en-US",{month:"long",year:"numeric"});
  const savedPath   = monthlyPath(config.saveFolder, year, month);

  // Scan weekly folder for each week's invoice when month changes
  useEffect(()=>{
    const currentWeeks = getWeeksForMonth(year, month);
    setWeekHours(currentWeeks.map(()=>0));
    setNotification(null); setAlreadySaved(false); setScanPopup(null);

    const abortController = new AbortController();

    // Fetch scan results from backend API
    fetch(`/api/scan-month?year=${year}&month=${month+1}&folder=${encodeURIComponent(config.saveFolder)}`, {
      signal: abortController.signal
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: Failed to scan monthly invoices`);
        }
        return response.json();
      })
      .then(data => {
        // data.weeks: [{ label, invNum, found, hours }]
        const results = data.weeks || [];
        const newHours = results.map(r => r.hours || 0);
        setWeekHours(newHours);
        setScanPopup(results);

        // Check if monthly report already exists to set alreadySaved flag
        if (data.monthlyExists) {
          setAlreadySaved(true);
        }
      })
      .catch(error => {
        // Ignore abort errors - component unmounted or month changed before fetch completed
        if (error.name === 'AbortError') return;
        console.error('Monthly scan failed:', error);
        // Show error notification to user
        setNotification({
          error: error.message || 'Failed to scan weekly invoices. You can still manually enter hours.'
        });
        // Set empty results on error - user can still manually enter hours
        // Use currentWeeks captured at effect start to avoid stale closure
        setScanPopup(currentWeeks.map(w => ({ label: w.label, invNum: w.invNum, found: false, hours: 0 })));
      });

    return () => abortController.abort();
  },[year,month,config.saveFolder]);

  const weeksWithData = useMemo(()=>weeks.map((w,i)=>({...w,hours:weekHours[i]||0})),[weeks,weekHours]);
  const totalHours = weeksWithData.reduce((s,w)=>s+w.hours,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const setWeekHour = (i,v) => setWeekHours(h=>{ const n=[...h]; n[i]=v; return n; });

  const doSend = async () => {
    setNotification(null);
    setShowConfirm(false);

    try {
      // Prepare payload for monthly submit endpoint
      const payload = {
        weekData: weeksWithData.map(w => ({ label: w.label, hours: w.hours })),
        year: year,
        month: month + 1, // Backend expects 1-indexed month
        accountantEmail: config.accountantEmail
      };

      const response = await fetch('/api/submit/monthly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}: Failed to submit monthly report`);
      }

      const data = await response.json();

      // Update UI with actual response data
      setNotification({
        sent: data.sent || [config.accountantEmail],
        saved: data.saved || savedPath
      });
      setAlreadySaved(true);

    } catch (error) {
      console.error('Monthly submit failed:', error);
      setNotification({
        error: error.message || 'Failed to submit monthly report. Please try again.'
      });
    }
  };

  const handleSubmit = () => { if(alreadySaved){setShowConfirm(true);return;} doSend(); };
  const prevMonth = () => { setNotification(null); if(month===0){setYear(y=>y-1);setMonth(11);}else setMonth(m=>m-1); };
  const nextMonth = () => { setNotification(null); if(month===11){setYear(y=>y+1);setMonth(0);}else setMonth(m=>m+1); };

  const LETTER_W=680, LETTER_H=Math.round(LETTER_W*(11/8.5));

  return (
    <Shell config={config} title="Monthly Report" subtitle={monthLabel} onBack={onBack}>
      {showConfirm && <ConfirmModal savedPath={savedPath} onConfirm={doSend} onCancel={()=>setShowConfirm(false)}/>}
      {scanPopup   && <ScanPopup results={scanPopup} onClose={()=>setScanPopup(null)}/>}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        {/* PDF */}
        <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
          <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"7px 16px",display:"flex",alignItems:"center",gap:8,flexShrink:0}}>
            <button onClick={prevMonth} style={{fontSize:13,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"3px 10px",cursor:"pointer"}}>‹</button>
            <span style={{fontSize:13,color:chrome.brightText,minWidth:140,textAlign:"center"}}>{monthLabel}</span>
            <button onClick={nextMonth} style={{fontSize:13,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"3px 10px",cursor:"pointer"}}>›</button>
            <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:5}}>
              <button className="bsm" onClick={()=>setZoom(z=>Math.max(0.4,+(z-0.05).toFixed(2)))} style={{width:24,height:24,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:15,display:"flex",alignItems:"center",justifyContent:"center"}}>−</button>
              <span style={{fontSize:11,color:chrome.mutedText,width:36,textAlign:"center"}}>{Math.round(zoom*100)}%</span>
              <button className="bsm" onClick={()=>setZoom(z=>Math.min(1.4,+(z+0.05).toFixed(2)))} style={{width:24,height:24,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:15,display:"flex",alignItems:"center",justifyContent:"center"}}>+</button>
            </div>
          </div>
          <div style={{flex:1,overflowY:"auto",overflowX:"auto",display:"flex",justifyContent:"center",alignItems:"flex-start",padding:"24px 20px",background:chrome.previewBg}}>
            <div style={{width:LETTER_W*zoom,minHeight:LETTER_H*zoom,flexShrink:0,boxShadow:"0 4px 32px rgba(0,0,0,0.25)",background:"white",overflow:"hidden"}}>
              <div style={{transform:`scale(${zoom})`,transformOrigin:"top left",width:LETTER_W}}>
                <MonthlyReportPDF config={config} weekData={weeksWithData} monthLabel={monthLabel}/>
              </div>
            </div>
          </div>
        </div>
        {/* Editor */}
        <div style={{width:288,background:"#fdf8f4",borderLeft:"1px solid #e8ddd4",display:"flex",flexDirection:"column",overflow:"hidden",flexShrink:0}}>
          <div style={{flex:1,display:"flex",flexDirection:"column",padding:"13px 16px 0",overflow:"hidden"}}>
            <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Hours Per Week</div>
            <div style={{flex:"1 1 0",overflowY:"auto"}}>
              {weeksWithData.map((w,i)=>(
                <HourRow key={i} label={`Week ${i+1}`} sublabel={w.label} value={w.hours} onChange={v=>setWeekHour(i,v)} accent={acc}/>
              ))}
            </div>
            <div style={{background:"white",borderRadius:8,padding:"8px 12px",margin:"8px 0 6px",display:"flex",justifyContent:"space-between",border:`1px solid ${acc}22`,flexShrink:0}}>
              <div><div style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Hours</div>
                <div style={{fontFamily:"'Playfair Display',serif",fontSize:19,color:"#2c1810",lineHeight:1.1}}>{totalHours}</div></div>
              <div style={{textAlign:"right"}}><div style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Total</div>
                <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,color:acc,fontWeight:700,lineHeight:1.1}}>${totalPay}</div></div>
            </div>
            <div style={{flexShrink:0}}>
              {notification ? (
                <NotifCard notification={notification} onDismiss={()=>setNotification(null)}/>
              ) : (
                <div>
                  <div style={{fontSize:10,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:5}}>Send To</div>
                  <div style={{fontSize:11,color:"#b0988a",marginBottom:3}}>Accountant</div>
                  <div style={{fontSize:13,border:"1.5px solid #e8ddd8",borderRadius:6,padding:"7px 9px",color:"#2c1810",background:"white",opacity:0.8}}>{config.accountantEmail}</div>
                  <div style={{fontSize:11,color:"#c0a898",marginTop:5,fontStyle:"italic"}}>Monthly reports go to your accountant only.</div>
                </div>
              )}
            </div>
            <div style={{flex:"0 0 8px"}}/>
          </div>
          <div style={{padding:"10px 16px 14px",borderTop:"1px solid #eee0d8",flexShrink:0,background:"#fdf8f4"}}>
            <button onClick={handleSubmit} style={{width:"100%",fontSize:14,fontWeight:700,padding:"12px 0",borderRadius:9,border:"none",background:`linear-gradient(135deg,${acc},${acc}bb)`,color:"white",cursor:"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`}}>
              Generate &amp; Send Report 📊
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── ROOT ──────────────────────────────────────────────────────────────────
export default function App() {
  const [config, setConfig] = useState(defaultConfig);
  const [page,   setPage]   = useState("menu");
  const [scrollToFolder, setScrollToFolder] = useState(false);
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState(null);

  // Fetch config from API on app mount
  useEffect(() => {
    const abortController = new AbortController();
    fetch('/api/config', { signal: abortController.signal })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: Failed to load configuration`);
        }
        return response.json();
      })
      .then(data => {
        setConfig({ ...defaultConfig, ...data });
        setLoading(false);
      })
      .catch(error => {
        // Ignore abort errors - component unmounted before fetch completed
        if (error.name === 'AbortError') return;
        console.error('Config fetch failed, using defaults:', error);
        setConfigError(error.message);
        setLoading(false);
        // Keep defaultConfig as fallback
      });
    return () => abortController.abort();
  }, []);

  const handleNav = (dest) => {
    if (dest==="profile-folder") { setScrollToFolder(true); setPage("profile"); }
    else { setScrollToFolder(false); setPage(dest); }
  };

  // Show loading state while fetching config
  if (loading) {
    return (
      <div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#f9f3ee",flexDirection:"column",gap:16}}>
        <div style={{fontSize:32}}>⏳</div>
        <div style={{fontFamily:"'Playfair Display',serif",fontSize:18,color:"#2c1810"}}>Loading your profile...</div>
      </div>
    );
  }

  // Show error banner if config fetch failed (but continue with defaults)
  const ErrorBanner = configError ? (
    <div style={{position:"fixed",top:0,left:0,right:0,background:"#fef3e8",borderBottom:"2px solid #e8b060",padding:"10px 20px",zIndex:1000,display:"flex",alignItems:"center",gap:10}}>
      <span style={{fontSize:16}}>⚠️</span>
      <div style={{flex:1}}>
        <div style={{fontSize:12,fontWeight:700,color:"#8a5010"}}>Could not load saved profile</div>
        <div style={{fontSize:11,color:"#a87020"}}>Using default settings. You can save your profile to persist changes.</div>
      </div>
      <button onClick={()=>setConfigError(null)} style={{fontSize:11,color:"#8a5010",background:"none",border:"none",cursor:"pointer"}}>✕</button>
    </div>
  ) : null;

  if (page==="weekly")  return <>{ErrorBanner}<WeeklyPage  config={config} onBack={()=>setPage("menu")}/></>;
  if (page==="monthly") return <>{ErrorBanner}<MonthlyPage config={config} onBack={()=>setPage("menu")}/></>;
  if (page==="profile") return <>{ErrorBanner}<ProfilePage config={config} onSave={setConfig} onBack={()=>setPage("menu")} scrollToFolder={scrollToFolder}/></>;
  return <>{ErrorBanner}<LandingPage config={config} onNav={handleNav}/></>;
}
