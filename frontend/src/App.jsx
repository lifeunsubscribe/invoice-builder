import { useState, useMemo, useEffect, useRef } from "react";

// ── CONSTANTS ─────────────────────────────────────────────────────────────
const DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
const PALETTES = [
  { label:"Rose",       value:"#c47a86" },
  { label:"Sage",       value:"#82ab86" },
  { label:"Dusty Blue", value:"#7498bc" },
  { label:"Terracotta", value:"#cf7d5c" },
  { label:"Lavender",   value:"#9a86c0" },
  { label:"Marigold",   value:"#d4a438" },
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
  // A week belongs to whichever month contains its Monday.
  // Find the first Monday in this month.
  const firstDay = new Date(year, month, 1);
  const lastDay  = new Date(year, month+1, 0);
  const daysUntilMon = (8 - firstDay.getDay()) % 7; // 0 if already Monday
  const firstMonday = new Date(year, month, 1 + daysUntilMon);
  const weeks = [];
  let cur = new Date(firstMonday);
  while (cur.getMonth() === month && cur.getFullYear() === year) {
    const monday = new Date(cur);
    const sunday = new Date(cur); sunday.setDate(cur.getDate()+6);
    const fmt = (d,sy) => d.toLocaleDateString("en-US",{month:"short",day:"numeric",...(sy?{year:"numeric"}:{})});
    const invNum = `INV-${monday.getFullYear()}${pad(monday.getMonth()+1)}${pad(monday.getDate())}`;
    weeks.push({ monday, sunday, label:`${fmt(monday)} – ${fmt(sunday,true)}`, invNum });
    cur.setDate(cur.getDate()+7);
  }
  return weeks;
}

const SIGNATURE_FONTS = ["Dancing Script","Great Vibes","Sacramento","Pacifico","Satisfy"];

const ALL_VITALS = [
  {key:"temperature", label:"Temp",   unit:"°F",   step:"0.1"},
  {key:"bpSystolic",  label:"BP Sys", unit:"mmHg", step:"1"},
  {key:"bpDiastolic", label:"BP Dia", unit:"mmHg", step:"1"},
  {key:"weight",      label:"Weight", unit:"lbs",  step:"0.1"},
  {key:"pulse",       label:"Pulse",  unit:"BPM",  step:"1"},
  {key:"o2sat",       label:"O₂ Sat", unit:"%",    step:"1"},
  {key:"respRate",    label:"Resp",   unit:"/min", step:"1"},
  {key:"bloodSugar",  label:"Glucose",unit:"mg/dL",step:"1"},
  {key:"painLevel",   label:"Pain",   unit:"/10",  step:"1"},
];
const DEFAULT_ENABLED_VITALS = ["temperature","bpSystolic","bpDiastolic","weight","pulse","o2sat"];

const OCCUPATIONS = [
  {id:"",                label:"General Service Provider"},
  {id:"home-health-aide",label:"Home Health Aide"},
  {id:"personal-care",   label:"Personal Care Assistant"},
  {id:"tutor",           label:"Tutor / Instructor"},
  {id:"therapist",       label:"Therapist"},
  {id:"other",           label:"Other"},
];

// Occupation-specific labels. Falls back to default ("") for anything not overridden.
const OCC_LABELS = {
  "": {
    recipientName: "Recipient Name",
    recipientAddress: "Address of Service",
    objective: "Service Objective",
    objectivePlaceholder: "e.g., goals, key deliverables, recurring tasks",
    vitalsHeader: "Metrics",
    medsHeader: "Supplies / Materials",
    recipientCardTitle: "Service Recipient",
    recipientCardDesc: "The person or entity you provide service to.",
  },
  "home-health-aide": {
    recipientName: "Patient Name",
    recipientAddress: "Patient Address",
    objective: "Care Objective",
    objectivePlaceholder: "e.g., memory care, weight gain, meals, reduce high blood pressure",
    vitalsHeader: "Vitals",
    medsHeader: "Medications",
    recipientCardTitle: "Service Recipient",
    recipientCardDesc: "The patient you provide care for. Shows on invoices and logs.",
  },
  "personal-care": {
    recipientName: "Client Name",
    recipientAddress: "Client Address",
    objective: "Care Objective",
    objectivePlaceholder: "e.g., daily living assistance, mobility support, companionship",
    vitalsHeader: "Vitals",
    medsHeader: "Medications",
    recipientCardTitle: "Service Recipient",
    recipientCardDesc: "The client you provide care for.",
  },
};

function getOccLabels(config) {
  const occ = config.occupation || "";
  return OCC_LABELS[occ] || OCC_LABELS[""];
}

const defaultConfig = {
  name:           "Jane Doe",
  address:        "123 Main Street, Denver, CO 80201",
  personalEmail:  "jane@email.com",
  rate:           18.0,
  clientName:     "Sunrise Home Health Agency",
  clientEmail:    "billing@clientagency.com",
  accountantEmail:"accountant@cpa.com",
  patientName:    "",
  patientAddress: "",
  accent:         "#c47a86",
  invoiceNote:    "Thank you for the privilege of caring for your clients.",
  saveFolder:     deriveSaveFolder("Jane Doe"),
  clients:        [],
  activeClientId: "",
  signatureFont:  "",
  enabledVitals:  DEFAULT_ENABLED_VITALS,
  occupation:     "",
};

function getActiveClient(config) {
  const clients = config.clients || [];
  const active = clients.find(c => c.id === config.activeClientId);
  return active || clients[0] || { id:"", name:"", address:"", objective:"", defaultShift:{start:"09:00",end:"17:00"}, meds:[] };
}

function makeClientId() { return "client-" + Date.now(); }
function makeMedId() { return "med-" + Date.now() + "-" + Math.random().toString(36).slice(2,6); }

// ── CHROME ────────────────────────────────────────────────────────────────
const chrome = {
  titleBar:"#2e2218", toolbar:"#241a12", previewBg:"#ccc8c4",
  border:"#4a3828", mutedText:"#a08878", brightText:"#e8d8cc",
};

// ── CALENDAR PICKER ──────────────────────────────────────────────────────
function CalendarPicker({ accent, onSelect, onClose, highlightedDays, initialYear, initialMonth, selectedDay, mode, anchorRef, refreshKey }) {
  // mode: "day" (default) picks a day, "week" picks a week (Monday), "month" picks a month
  const m = mode || "day";
  const [year, setYear] = useState(initialYear || new Date().getFullYear());
  const [month, setMonth] = useState(initialMonth != null ? initialMonth : new Date().getMonth());
  const [loadedHL, setLoadedHL] = useState([]);
  const panelRef = useRef(null);

  // Close on click outside
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const handler = (e) => { if (panelRef.current && !panelRef.current.contains(e.target)) onCloseRef.current(); };
    const timer = setTimeout(() => document.addEventListener("mousedown", handler), 0);
    return () => { clearTimeout(timer); document.removeEventListener("mousedown", handler); };
  }, []);

  // If highlightedDays is a function, call it when month/year changes
  // Use a ref to avoid re-triggering when the function identity changes (inline arrows)
  const hlRef = useRef(highlightedDays);
  hlRef.current = highlightedDays;
  useEffect(() => {
    if (typeof hlRef.current === "function") {
      let cancelled = false;
      hlRef.current(year, month).then(days => { if (!cancelled) setLoadedHL(days); });
      return () => { cancelled = true; };
    } else if (Array.isArray(hlRef.current)) {
      setLoadedHL(hlRef.current);
    }
  }, [year, month, refreshKey]);

  const prevMonth = () => { if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(mo => mo - 1); };
  const nextMonth = () => { if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(mo => mo + 1); };

  const panelStyle = { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 9999, background: "white", borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,0.18)", padding: 16 };

  // Month picker mode
  if (m === "month") {
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return (
      <div ref={panelRef} style={{...panelStyle, minWidth: 240}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12}}>
          <button onClick={() => setYear(y => y - 1)} style={{background:"none",border:"none",cursor:"pointer",fontSize:16,color:"#9a8070"}}>‹</button>
          <span style={{fontSize:15,fontWeight:700,color:"#2c1810"}}>{year}</span>
          <button onClick={() => setYear(y => y + 1)} style={{background:"none",border:"none",cursor:"pointer",fontSize:16,color:"#9a8070"}}>›</button>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:6}}>
          {months.map((ml, i) => {
            const isHL = loadedHL.includes(i);
            const now = new Date();
            const isCurrent = year === now.getFullYear() && i === now.getMonth();
            return (
              <button key={i} onClick={() => { onSelect(year, i); onClose(); }}
                style={{padding:"8px 4px",borderRadius:8,border:isCurrent ? `2px solid ${accent}` : "1px solid #e8ddd4",background:isHL ? `${accent}18` : "white",color:"#2c1810",cursor:"pointer",fontSize:13,fontWeight:isCurrent ? 700 : 400}}>
                {ml}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // Day/week picker
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startDow = (firstDay.getDay() + 6) % 7; // 0=Mon
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= lastDay.getDate(); d++) cells.push(d);
  const monthName = firstDay.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const today = new Date();
  const isThisMonth = year === today.getFullYear() && month === today.getMonth();

  const getMondayForDay = (day) => {
    const d = new Date(year, month, day);
    const dow = (d.getDay() + 6) % 7;
    const mon = new Date(d); mon.setDate(d.getDate() - dow);
    return mon;
  };

  return (
    <div ref={panelRef} style={{...panelStyle, minWidth: 260}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
        <button onClick={prevMonth} style={{background:"none",border:"none",cursor:"pointer",fontSize:16,color:"#9a8070"}}>‹</button>
        <span style={{fontSize:15,fontWeight:700,color:"#2c1810"}}>{monthName}</span>
        <button onClick={nextMonth} style={{background:"none",border:"none",cursor:"pointer",fontSize:16,color:"#9a8070"}}>›</button>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:2,textAlign:"center"}}>
        {["M","T","W","T","F","S","S"].map((d,i) => (
          <div key={i} style={{fontSize:11,color:"#9a8070",padding:"4px 0",fontWeight:600}}>{d}</div>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={i}/>;
          const isSelected = selectedDay && year === selectedDay.year && month === selectedDay.month && day === selectedDay.day;
          const isToday = isThisMonth && day === today.getDate();
          const isHL = loadedHL.includes(day);
          const border = isSelected ? `2px solid ${accent}` : (isToday ? `2px dashed ${accent}` : "none");
          const accent2 = isSelected || isToday;
          const handleClick = () => {
            if (m === "week") {
              const mon = getMondayForDay(day);
              onSelect(mon);
            } else {
              onSelect(year, month, day);
            }
            onClose();
          };
          return (
            <button key={i} onClick={handleClick}
              style={{width:32,height:32,borderRadius:"50%",border,background:isHL ? `${accent}25` : "transparent",color:accent2 ? accent : "#2c1810",cursor:"pointer",fontSize:13,fontWeight:accent2 ? 700 : 400,display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto"}}>
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── SHARED: HOUR INPUT ROW ────────────────────────────────────────────────
function HourRow({ label, sublabel, value, onChange, accent }) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState(String(value));
  const commit = () => {
    const n = parseFloat(raw);
    const rounded = isNaN(n) ? value : Math.round(Math.max(0, Math.min(168, n)) * 2) / 2;
    onChange(rounded);
    setEditing(false);
  };
  const display = value % 1 === 0 ? String(value) : value.toFixed(1);
  return (
    <div className="day-row" style={{display:"flex",alignItems:"center",padding:"6px 3px",borderBottom:"1px solid #f0e6e0",transition:"background 0.1s",borderRadius:4}}>
      <div style={{flex:1,minWidth:0}}>
        <div style={{fontSize:15,color:"#4a3028",fontWeight:value>0?700:500}}>{label}</div>
        {sublabel && <div style={{fontSize:12,color:"#b0988a",marginTop:1}}>{sublabel}</div>}
      </div>
      <div style={{display:"flex",alignItems:"center",gap:6,flexShrink:0,marginLeft:8}}>
        <button onClick={()=>onChange(Math.max(0,value-0.5))}
          style={{width:23,height:23,borderRadius:"50%",border:`1.5px solid ${accent}`,background:"white",color:accent,fontSize:16,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>−</button>
        {editing ? (
          <input value={raw} onChange={e=>setRaw(e.target.value)}
            onBlur={commit} onKeyDown={e=>{if(e.key==="Enter")commit();if(e.key==="Escape")setEditing(false);}}
            style={{width:36,textAlign:"center",fontFamily:"'Playfair Display',serif",fontSize:17,border:`1.5px solid ${accent}`,borderRadius:5,padding:"1px 2px",color:"#2c1810",outline:"none"}} autoFocus/>
        ) : (
          <span onClick={()=>{setRaw(String(value));setEditing(true);}} title="Click to type"
            style={{fontFamily:"'Playfair Display',serif",fontSize:18,color:value>0?"#2c1810":"#ccc",width:36,textAlign:"center",cursor:"text",borderBottom:`1px dashed ${value>0?"#c8b0a8":"#ddd"}`}}>
            {display}
          </span>
        )}
        <button onClick={()=>onChange(Math.min(168,value+0.5))}
          style={{width:23,height:23,borderRadius:"50%",border:`1.5px solid ${accent}`,background:accent,color:"white",fontSize:16,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>+</button>
        {!sublabel && <span style={{fontSize:12,color:"#c0a898",width:18}}>hr</span>}
      </div>
    </div>
  );
}

// ── CONFIRM MODAL ─────────────────────────────────────────────────────────
function ConfirmModal({ savedPath, onConfirm, onCancel, accent }) {
  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.5)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:300,padding:16}}>
      <div style={{background:"white",borderRadius:16,maxWidth:360,width:"100%",overflow:"hidden",boxShadow:"0 8px 48px rgba(0,0,0,0.25)"}}>
        <div style={{background:chrome.titleBar,padding:"16px 22px"}}>
          <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:"#e0c090",marginBottom:4}}>⚠ Already Sent</div>
          <div style={{fontSize:14,color:chrome.mutedText}}>This document appears to have been sent already.</div>
        </div>
        <div style={{padding:"18px 22px"}}>
          <div style={{fontSize:14,color:"#4a3028",lineHeight:1.6,marginBottom:16}}>
            A file was already saved at:<br/>
            <span style={{fontFamily:"monospace",fontSize:12,color:"#7a5030",background:"#fdf0e8",padding:"3px 7px",borderRadius:4,display:"inline-block",marginTop:4}}>{savedPath}</span>
            <br/><br/>Send again and overwrite it?
          </div>
          <div style={{display:"flex",gap:9}}>
            <button onClick={onCancel} style={{flex:1,fontSize:14,fontWeight:700,padding:"10px 0",borderRadius:9,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:"pointer"}}>Cancel</button>
            <button onClick={onConfirm} style={{flex:1,fontSize:14,fontWeight:700,padding:"10px 0",borderRadius:9,border:"none",background:accent,color:"white",cursor:"pointer"}}>Send Anyway</button>
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
        <div style={{background:chrome.titleBar,padding:"22px 28px"}}>
          <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:"#a8c8d8",marginBottom:6}}>📁 Weekly Invoice Scan</div>
          <div style={{fontSize:14,color:chrome.mutedText}}>
            Found {foundCount} of {results.length} weekly invoices in your folder.
            {foundCount>0 && <><br/>Hours pre-filled from found files.</>}
          </div>
        </div>
        <div style={{padding:"20px 28px",maxHeight:340,overflowY:"auto"}}>
          {results.map((r,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 0",borderBottom:i<results.length-1?"1px solid #f0ece8":"none"}}>
              <span style={{fontSize:16,flexShrink:0}}>{r.found?"✅":"❌"}</span>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontSize:13,fontWeight:600,color:"#2c1810"}}>Week {i+1} — {r.label}</div>
                <div style={{fontSize:11,fontFamily:"monospace",color:"#9a7060",marginTop:2,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.invNum}.pdf</div>
              </div>
              <span style={{fontSize:12,fontWeight:700,color:r.found?"#4a7a50":"#c07050",flexShrink:0}}>{r.found?"found":"not found"}</span>
            </div>
          ))}
        </div>
        <div style={{padding:"16px 28px 20px",borderTop:"1px solid #f0ece8"}}>
          {foundCount < results.length && (
            <div style={{fontSize:12,color:"#9a8070",fontStyle:"italic",marginBottom:12}}>
              Missing weeks defaulted to 0 hrs — adjust manually if needed.
            </div>
          )}
          <button onClick={onClose} style={{width:"100%",fontSize:14,fontWeight:700,padding:"11px 0",borderRadius:9,border:"none",background:chrome.titleBar,color:"white",cursor:"pointer"}}>Got it</button>
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
        <th key={h} style={{padding:`11px ${h==="Amount"?"38px":"0"} 11px ${h==="Day"?"38px":"0"}`,textAlign:h==="Day"?"left":"right",fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:accentColor,fontWeight:700,borderBottom:"1.5px solid #e0e8e0"}}>{h}</th>
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
        <div style={{fontSize:13,color:ML_ACC,letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7,fontFamily:"sans-serif"}}><span style={{fontSize:15}}>🌸</span> Contractor Invoice</div>
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
        {config.patientName && <div style={{marginRight:52}}><div style={{fontSize:10,fontFamily:"sans-serif",letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC,marginBottom:7}}>Service Recipient</div>
          <div style={{fontSize:15,fontWeight:700,color:"#2c1810",fontFamily:"sans-serif"}}>{config.patientName}</div>
          {config.patientAddress && <div style={{fontSize:13,fontFamily:"sans-serif",color:"#6a4a40",marginTop:3}}>{config.patientAddress}</div>}</div>}
        <div><div style={{fontSize:10,fontFamily:"sans-serif",letterSpacing:1.5,textTransform:"uppercase",color:ML_ACC,marginBottom:7}}>Week Of</div>
          <div style={{fontSize:14,color:"#2c1810",fontFamily:"sans-serif"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="white" rowOdd="#fdf8f4" accentColor={ML_ACC} textColor="#2c1810" dayDates={week.dayDates}/></div>
      <div style={{margin:"0 38px",borderTop:`2px solid ${ML_ACC}44`,marginTop:16,paddingTop:20,paddingBottom:14,display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
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
        <div style={{fontSize:13,color:CH_ACC,letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7}}><span style={{fontSize:15}}>🤍</span> Contractor Invoice</div>
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
        {config.patientName && <div style={{marginRight:52}}><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC,marginBottom:7}}>Service Recipient</div>
          <div style={{fontSize:15,fontWeight:700,color:"#1a2a3a"}}>{config.patientName}</div>
          {config.patientAddress && <div style={{fontSize:13,color:"#4a6a60",marginTop:3}}>{config.patientAddress}</div>}</div>}
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:CH_ACC,marginBottom:7}}>Service Period</div>
          <div style={{fontSize:14,color:"#1a2a3a"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="white" rowOdd="#f4f9f8" accentColor={CH_ACC} textColor="#1a2a3a" dayDates={week.dayDates}/></div>
      <div style={{margin:"32px 38px 18px",display:"flex",justifyContent:"flex-end"}}>
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
        <div style={{fontSize:13,color:"#a8d8a0",letterSpacing:2.5,textTransform:"uppercase",marginBottom:10,display:"flex",alignItems:"center",gap:7}}><span style={{fontSize:15}}>🌿</span> Contractor Invoice</div>
        <div style={{fontSize:27,fontWeight:500,color:"#e8f5e4",letterSpacing:0.5}}>{config.name}</div>
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
        {config.patientName && <div style={{marginRight:52}}><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:GD_ACC,marginBottom:7}}>Service Recipient</div>
          <div style={{fontSize:15,fontWeight:700,color:"#2d4a2d"}}>{config.patientName}</div>
          {config.patientAddress && <div style={{fontSize:13,color:"#6a8a60",marginTop:3}}>{config.patientAddress}</div>}</div>}
        <div><div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:GD_ACC,marginBottom:7}}>Service Week</div>
          <div style={{fontSize:14,color:"#2d4a2d"}}>{week.start} – {week.end}</div></div>
      </div>
      <div style={{paddingTop:6}}><InvoiceTable hours={hours} config={config} rowEven="#fffef8" rowOdd="#f4f8f0" accentColor={GD_ACC} textColor="#2d4a2d" dayDates={week.dayDates}/></div>
      <div style={{margin:"0 38px",borderTop:"2px dashed #b8d8b0",marginTop:16,paddingTop:20,paddingBottom:14,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
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
function MonthlyReportPDF({ config, weekData, monthLabel, signatureFont }) {
  const totalHours = weekData.reduce((s,w)=>s+w.hours,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const worked     = weekData.filter(w=>w.hours>0);
  return (
    <div style={{fontFamily:"sans-serif",background:"white",width:"100%",minHeight:880,display:"flex",flexDirection:"column"}}>
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
          <div style={{fontSize:16,fontWeight:700,color:"#1a2a3a"}}>${config.rate.toFixed(2)}<span style={{fontSize:11,fontWeight:500,color:"#5a8090"}}>/hr</span></div></div>
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
              <td style={{padding:"12px 38px 12px 0",textAlign:"right",color:w.hours>0?"#1a2a3a":"#aaa",fontWeight:w.hours>0?600:500}}>
                {w.hours>0?`$${(w.hours*config.rate).toFixed(2)}`:"—"}
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div style={{margin:"28px 38px 18px",display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
        <div style={{fontSize:13,color:"#7a9aaa"}}>{worked.length} week{worked.length!==1?"s":""} worked · ${config.rate.toFixed(2)}/hr</div>
        <div style={{background:"#2c3e50",borderRadius:10,padding:"16px 28px",textAlign:"right"}}>
          <div style={{fontSize:11,letterSpacing:1.5,textTransform:"uppercase",color:"#a8c8d8",marginBottom:6}}>{totalHours} total hours · Amount Due</div>
          <div style={{fontSize:30,fontWeight:700,color:"white"}}>${totalPay}</div>
        </div>
      </div>
      <div style={{margin:"0 38px",borderTop:"1px dashed #c8dce8"}}/>
      <div style={{flex:1}}/>
      <div style={{margin:"0 38px 20px",paddingTop:16,display:"flex",gap:48}}>
        <div style={{flex:1}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:6}}>Provider Signature</div>
          {signatureFont
            ? <div style={{fontFamily:`'${signatureFont}', cursive`,fontSize:28,color:"#1a2a3a",paddingBottom:2,height:38,display:"flex",alignItems:"flex-end"}}>{config.name}</div>
            : <div style={{height:38}}/>}
          <div style={{borderBottom:"1px solid #1a2a3a",height:1,width:"80%"}}/>
          <div style={{fontSize:11,color:"#7a9aaa",marginTop:5}}>{config.name}</div>
        </div>
        <div style={{flex:1}}>
          <div style={{fontSize:10,letterSpacing:1.5,textTransform:"uppercase",color:"#5a90a8",marginBottom:6}}>Date</div>
          {signatureFont
            ? <div style={{fontFamily:`'${signatureFont}', cursive`,fontSize:22,color:"#1a2a3a",paddingBottom:2,height:38,display:"flex",alignItems:"flex-end"}}>{new Date().toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric"})}</div>
            : <div style={{height:38}}/>}
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
function Shell({ config, title, subtitle, onBack, emailConfigured, onOpenEmailSetup, children }) {
  return (
    <div style={{height:"100vh",display:"flex",flexDirection:"column",background:chrome.titleBar,overflow:"hidden"}}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Dancing+Script:wght@400;700&family=Great+Vibes&family=Sacramento&family=Pacifico&family=Satisfy&display=swap');*{box-sizing:border-box}.day-row:hover{background:#fbeee8!important}.tmpl-btn,.bsm{transition:all 0.15s}.tmpl-btn:hover,.bsm:hover{opacity:0.85}::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:#d0c0b8;border-radius:3px}@keyframes pulse-glow{0%,100%{box-shadow:0 0 0 0 ${tint(config.accent,0.4)}}50%{box-shadow:0 0 0 6px ${tint(config.accent,0)}}}`}</style>
      <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"10px 20px",display:"flex",alignItems:"center",gap:14,flexShrink:0}}>
        <button onClick={onBack||undefined} style={{fontSize:15,color:chrome.mutedText,background:"none",border:`1px solid ${onBack?chrome.border:"transparent"}`,borderRadius:6,padding:"5px 12px",cursor:onBack?"pointer":"default",visibility:onBack?"visible":"hidden"}}>← Back</button>
        <span style={{fontSize:14,letterSpacing:3,textTransform:"uppercase",color:config.accent,display:"flex",alignItems:"center",gap:6}}><span>♥</span> {title}</span>
        {subtitle && <><div style={{width:1,height:14,background:chrome.border}}/><span style={{fontSize:16,color:chrome.brightText}}>{subtitle}</span></>}
        <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:8}}>
        {onOpenEmailSetup && emailConfigured === false && (
          <button onClick={onOpenEmailSetup}
            style={{fontSize:14,fontWeight:700,color:"#fff",background:config.accent,border:"none",borderRadius:20,padding:"6px 15px",cursor:"pointer",display:"flex",alignItems:"center",gap:5,animation:"pulse-glow 2s ease-in-out infinite"}}>
            <span style={{fontSize:16}}>✉</span> Set Up Email
          </button>
        )}
        {onOpenEmailSetup && emailConfigured === true && (
          <button onClick={onOpenEmailSetup}
            style={{fontSize:13,color:"#c0b0a4",background:"none",border:`1px solid ${chrome.border}`,borderRadius:20,padding:"5px 12px",cursor:"pointer",display:"flex",alignItems:"center",gap:4,opacity:0.85,transition:"opacity 0.15s"}}
            onMouseEnter={e=>e.currentTarget.style.opacity="1"}
            onMouseLeave={e=>e.currentTarget.style.opacity="0.7"}>
            <span style={{fontSize:14}}>✉</span> Email Settings
          </button>
        )}
        </div>
      </div>
      {children}
    </div>
  );
}

// ── NOTIFICATION CARD ─────────────────────────────────────────────────────
function NotifCard({ notification, onDismiss, onOpenEmailSetup, accent }) {
  // Handle partial success: PDF saved but email failed
  if (notification.saved && notification.emailError) {
    const isCredentialError = notification.emailError.includes('.env') || notification.emailError.includes('not found');
    return (
      <div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
          <div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#c9972a"}}>Partial Success</div>
          <button onClick={onDismiss} aria-label="Dismiss notification" style={{fontSize:12,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
        </div>
        <div style={{background:"#fefaf2",border:"1px solid #ead8a8",borderRadius:8,padding:"11px 13px"}}>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:16,color:"#6a5010",marginBottom:7}}>⚠ Saved but Email Failed</div>
          <div style={{fontSize:13,color:"#4a7a50",marginBottom:8,paddingBottom:8,borderBottom:"1px solid #e8e0c8",display:"flex",alignItems:"center",gap:5}}>
            <span>💾</span> <span style={{wordBreak:"break-word",overflowWrap:"break-word"}}>{notification.saved}</span>
          </div>
          <div style={{fontSize:13,color:"#8a6020",lineHeight:1.5,wordBreak:"break-word",overflowWrap:"break-word"}}>
            {isCredentialError
              ? <><strong>Email is not set up.</strong> Your invoice was saved locally. Set up your Gmail and app password to send invoices by email.</>
              : <><strong>Email error:</strong> {notification.emailError}</>
            }
          </div>
          {isCredentialError && onOpenEmailSetup && (
            <button onClick={onOpenEmailSetup}
              style={{marginTop:10,fontSize:13,fontWeight:700,color:"#fff",background:accent,border:"none",borderRadius:8,padding:"8px 16px",cursor:"pointer",width:"100%"}}>
              Set Up Email Now
            </button>
          )}
        </div>
      </div>
    );
  }

  // Handle full error notifications
  if (notification.error) {
    return (
      <div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
          <div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#c4714f"}}>Error</div>
          <button onClick={onDismiss} aria-label="Dismiss notification" style={{fontSize:12,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
        </div>
        <div style={{background:"#fff5f2",border:"1px solid #f0c8b8",borderRadius:8,padding:"11px 13px"}}>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:16,color:"#4a2010",marginBottom:4}}>⚠ Failed</div>
          <div style={{fontSize:13,color:"#7a4030",lineHeight:1.5,wordBreak:"break-word",overflowWrap:"break-word"}}>{notification.error}</div>
        </div>
      </div>
    );
  }

  // Handle full success notifications
  const hasSent = notification.sent && notification.sent.length > 0;
  return (
    <div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
        <div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#6a9a70"}}>{hasSent ? "Sent" : "Saved"}</div>
        <button onClick={onDismiss} aria-label="Dismiss notification" style={{fontSize:12,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
      </div>
      <div style={{background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:8,padding:"11px 13px"}}>
        <div style={{fontFamily:"'Playfair Display',serif",fontSize:16,color:"#2d4a2d",marginBottom:7}}>{hasSent ? "✓ Sent!" : "✓ Saved!"}</div>
        {hasSent && notification.sent.map(e=><div key={e} style={{fontSize:13,color:"#4a7a50",marginBottom:3,wordBreak:"break-word",overflowWrap:"break-word"}}>✉ {e}</div>)}
        {!hasSent && <div style={{fontSize:13,color:"#9a8070",marginBottom:3}}>No emails sent</div>}
        <div style={{fontSize:13,color:"#4a7a50",marginTop:4,paddingTop:6,borderTop:"1px solid #c8e8c8",display:"flex",alignItems:"center",gap:5}}>
          <span>💾</span> <span style={{wordBreak:"break-word",overflowWrap:"break-word"}}>{notification.saved}</span>
        </div>
      </div>
    </div>
  );
}

// ── LANDING ───────────────────────────────────────────────────────────────
function LandingPage({ config, onNav, emailConfigured, onOpenEmailSetup }) {
  const acc  = config.accent;
  const week = getWeekRange(0);
  const now  = new Date();
  const todayFormatted = now.toLocaleDateString("en-US",{weekday:"long",month:"long",day:"numeric"});
  const monthName = now.toLocaleDateString("en-US",{month:"long",year:"numeric"});
  const cards = [
    { id:"log",     emoji:"📓", label:"Daily Service Log", desc:todayFormatted,                         primary:true  },
    { id:"weekly",  emoji:"📄", label:"Weekly Invoice",    desc:`Week of ${week.start}`,               primary:false },
    { id:"monthly", emoji:"📊", label:"Monthly Report",    desc:monthName,                              primary:false },
    { id:"profile", emoji:"👤", label:"Edit Profile",      desc:"Invoice & Custom Settings",     primary:false },
  ];
  return (
    <Shell config={config} title="Contractor Invoice" subtitle={config.name} emailConfigured={emailConfigured} onOpenEmailSetup={onOpenEmailSetup}>
      <style>{`
        .landing-cards{display:flex;flex-direction:column;align-items:center;gap:14px;width:100%;max-width:520px}
        @media(min-width:700px){.landing-cards{display:grid;grid-template-columns:1fr 1fr;max-width:760px;gap:16px}}
      `}</style>
      <div style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:14,padding:"32px 24px",background:"linear-gradient(160deg,#f9f3ee,#f2ebe4)"}}>
        <div style={{textAlign:"center",marginBottom:8}}>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:29,color:"#2c1810",fontWeight:700,marginBottom:4}}>
            Good {now.getHours()<12?"Morning":now.getHours()<18?"Afternoon":"Evening"}{config.name.trim() ? `, ${config.name.split(" ")[0]}` : ""} 👋
          </div>
          <div style={{fontFamily:"sans-serif",fontSize:15,color:"#9a8070"}}>What would you like to do today?</div>
        </div>
        <div className="landing-cards">
          {cards.map(c=>(
            <button key={c.id} onClick={()=>onNav(c.id)} style={{width:"100%",padding:"22px 32px",borderRadius:16,cursor:"pointer",border:c.primary?`2px solid ${acc}`:"2px solid #e8ddd4",background:c.primary?`linear-gradient(135deg,${acc},${tint(acc,0.85)})`:"white",color:c.primary?"white":"#2c1810",textAlign:"left",display:"flex",alignItems:"center",gap:18,boxShadow:c.primary?`0 6px 24px ${tint(acc,0.3)}`:"0 2px 12px rgba(0,0,0,0.06)",transition:"transform 0.1s,box-shadow 0.1s"}}
              onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-2px)";e.currentTarget.style.boxShadow=c.primary?`0 10px 28px ${tint(acc,0.35)}`:"0 6px 20px rgba(0,0,0,0.1)";}}
              onMouseLeave={e=>{e.currentTarget.style.transform="translateY(0)";e.currentTarget.style.boxShadow=c.primary?`0 6px 24px ${tint(acc,0.3)}`:"0 2px 12px rgba(0,0,0,0.06)";}}>
              <span style={{fontSize:35}}>{c.emoji}</span>
              <div>
                <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,fontWeight:700,marginBottom:3}}>{c.label}</div>
                <div style={{fontFamily:"sans-serif",fontSize:15,opacity:0.75}}>{c.desc}</div>
              </div>
              <span style={{marginLeft:"auto",fontSize:21,opacity:0.5}}>→</span>
            </button>
          ))}
        </div>
        {/* Clickable "Saving to" — navigates to profile folder section */}
        <button onClick={()=>onNav("profile-folder")}
          style={{fontSize:13,color:"#9a8070",background:"none",border:"1px dashed #d0c0b0",borderRadius:8,padding:"7px 15px",cursor:"pointer",marginTop:4,transition:"all 0.15s"}}
          onMouseEnter={e=>{e.currentTarget.style.borderColor=acc;e.currentTarget.style.color=acc;}}
          onMouseLeave={e=>{e.currentTarget.style.borderColor="#d0c0b0";e.currentTarget.style.color="#9a8070";}}>
          📁 Saving to <span style={{fontFamily:"monospace"}}>{config.saveFolder}</span> — click to change
        </button>
      </div>
    </Shell>
  );
}

// ── PROFILE PAGE ──────────────────────────────────────────────────────────
function ProfilePage({ config, onSave, onBack, scrollToFolder, emailConfigured, onOpenEmailSetup }) {
  const [draft, setDraft] = useState(()=>{
    // Ensure clients array exists in draft
    const d = {...config};
    if (!d.clients) d.clients = [];
    if (!d.activeClientId) d.activeClientId = "";
    if (!d.signatureFont) d.signatureFont = "";
    return d;
  });
  const [folderOverridden, setFolderOverridden] = useState(config.saveFolder && config.name ? config.saveFolder !== deriveSaveFolder(config.name) : false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const folderRef = useRef(null);
  const saveInProgressRef = useRef(false);
  const acc = draft.accent;

  // Active client helper for this draft
  const activeClient = getActiveClient(draft);
  const hasClient = activeClient.id !== "";

  const updateField = (key, value) => {
    setDraft(d => {
      const next = {...d,[key]:value};
      if (key==="name" && !folderOverridden) next.saveFolder = deriveSaveFolder(value);
      return next;
    });
  };

  const updateClient = (field, value) => {
    setDraft(d => {
      const clients = (d.clients||[]).map(c =>
        c.id === d.activeClientId ? {...c, [field]: value} : c
      );
      return {...d, clients};
    });
  };

  const updateClientShift = (field, value) => {
    setDraft(d => {
      const clients = (d.clients||[]).map(c =>
        c.id === d.activeClientId ? {...c, defaultShift: {...(c.defaultShift||{}), [field]: value}} : c
      );
      return {...d, clients};
    });
  };

  const addClient = () => {
    const id = makeClientId();
    setDraft(d => ({
      ...d,
      clients: [...(d.clients||[]), {id, name:"", address:"", objective:"", defaultShift:{start:"09:00",end:"17:00"}, meds:[]}],
      activeClientId: id
    }));
  };

  const removeClient = (id) => {
    setDraft(d => {
      const clients = (d.clients||[]).filter(c => c.id !== id);
      const activeClientId = d.activeClientId === id ? (clients[0]?.id || "") : d.activeClientId;
      return {...d, clients, activeClientId};
    });
  };

  // Medication CRUD
  const addMed = () => {
    setDraft(d => {
      const newMed = {id: makeMedId(), name:"", dosage:"", frequency:"", route:"Oral"};
      const clients = (d.clients||[]).map(c =>
        c.id === d.activeClientId ? {...c, meds: [...(c.meds||[]), newMed]} : c
      );
      return {...d, clients};
    });
  };

  const updateMed = (medId, field, value) => {
    setDraft(d => {
      const clients = (d.clients||[]).map(c =>
        c.id === d.activeClientId
          ? {...c, meds: (c.meds||[]).map(m => m.id === medId ? {...m, [field]: value} : m)}
          : c
      );
      return {...d, clients};
    });
  };

  const removeMed = (medId) => {
    setDraft(d => {
      const clients = (d.clients||[]).map(c =>
        c.id === d.activeClientId
          ? {...c, meds: (c.meds||[]).filter(m => m.id !== medId)}
          : c
      );
      return {...d, clients};
    });
  };

  // Scroll to folder section if requested
  useEffect(()=>{
    if (scrollToFolder && folderRef.current) {
      setTimeout(()=>folderRef.current.scrollIntoView({ behavior:"smooth", block:"center" }), 120);
    }
  },[scrollToFolder]);

  // Save profile changes to persistent storage via API
  const handleSave = async () => {
    if (saveInProgressRef.current) return;
    saveInProgressRef.current = true;
    setSaving(true);
    setSaveError(null);
    try {
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft)
      });
      if (!response.ok) {
        throw new Error(`Unable to save your profile settings. Please try again or contact support if the issue continues.`);
      }
      onSave({ ...draft, rate: Number(draft.rate) || 0 });
      onBack();
    } catch (error) {
      console.error('Save failed:', error);
      setSaveError(error.message);
    } finally {
      setSaving(false);
      saveInProgressRef.current = false;
    }
  };

  const inputStyle = {width:"100%",fontSize:15,border:"1.5px solid #e8ddd8",borderRadius:8,padding:"9px 12px",color:"#2c1810",outline:"none",background:"#fdfaf8"};
  const labelStyle = {fontSize:11,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",display:"block",marginBottom:4};

  return (
    <Shell config={draft} title="Edit Profile" onBack={onBack} emailConfigured={emailConfigured} onOpenEmailSetup={onOpenEmailSetup}>
      <div style={{flex:1,overflowY:"auto",background:"#f9f3ee",padding:"28px 16px 32px"}}>
        <div style={{width:"100%",maxWidth:480,margin:"0 auto"}}>

          {/* Invoice Details card */}
          <div style={{background:"white",borderRadius:16,overflow:"hidden",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:16}}>
            <div style={{background:chrome.titleBar,padding:"16px 24px"}}>
              <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:acc,marginBottom:4}}>Invoice Details</div>
              <div style={{fontSize:14,color:chrome.mutedText}}>This info appears on every invoice and report.</div>
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
                <div key={key} style={{marginBottom:18}}>
                  <label style={labelStyle}>{label}</label>
                  <input type={type||"text"} value={draft[key]} onChange={e=>updateField(key,e.target.value)} style={inputStyle}/>
                </div>
              ))}

              {/* Save folder */}
              <div ref={folderRef} style={{marginBottom:13,scrollMarginTop:24}}>
                <label style={labelStyle}>Save Folder</label>
                <input value={draft.saveFolder}
                  onChange={e=>{setFolderOverridden(true);setDraft(d=>({...d,saveFolder:e.target.value}));}}
                  style={{...inputStyle,fontSize:14,fontFamily:"monospace",color:"#5a4030"}}/>
                {folderOverridden && (
                  <button onClick={()=>{setFolderOverridden(false);setDraft(d=>({...d,saveFolder:deriveSaveFolder(d.name)}));}}
                    style={{fontSize:12,color:acc,background:"none",border:"none",cursor:"pointer",marginTop:4,padding:0}}>↺ Reset to auto-derived</button>
                )}
                <div style={{background:"#f8f4f0",borderRadius:8,padding:"10px 12px",fontSize:12,color:"#9a8070",marginTop:8}}>
                  📄 Weekly → <span style={{fontFamily:"monospace"}}>{draft.saveFolder}/weekly/</span><br/>
                  📊 Monthly → <span style={{fontFamily:"monospace"}}>{draft.saveFolder}/monthly/</span><br/>
                  📋 Logs → <span style={{fontFamily:"monospace"}}>{draft.saveFolder}/logs/</span>
                </div>
              </div>
            </div>
          </div>

          {/* Service Recipient card */}
          <div style={{background:"white",borderRadius:16,overflow:"hidden",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:16}}>
            <div style={{background:chrome.titleBar,padding:"16px 24px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
              <div>
                <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:acc,marginBottom:4}}>Service Recipient</div>
                <div style={{fontSize:14,color:chrome.mutedText}}>The person you provide service to. Shows on invoices and logs.</div>
              </div>
              {!hasClient && (
                <button onClick={addClient} style={{fontSize:12,fontWeight:700,padding:"6px 14px",borderRadius:8,border:"none",background:acc,color:"white",cursor:"pointer"}}>+ Add</button>
              )}
            </div>
            {hasClient && (
              <div style={{padding:"20px 24px"}}>
                {/* Client selector (only if multiple) */}
                {(draft.clients||[]).length > 1 && (
                  <div style={{marginBottom:18}}>
                    <label style={labelStyle}>Active Recipient</label>
                    <select value={draft.activeClientId} onChange={e=>setDraft(d=>({...d,activeClientId:e.target.value}))}
                      style={{...inputStyle,cursor:"pointer"}}>
                      {(draft.clients||[]).map(c=><option key={c.id} value={c.id}>{c.name||"(unnamed)"}</option>)}
                    </select>
                  </div>
                )}

                <div style={{marginBottom:18}}>
                  <label style={labelStyle}>Service Recipient</label>
                  <input value={activeClient.name} onChange={e=>updateClient("name",e.target.value)} style={inputStyle}/>
                </div>
                <div style={{marginBottom:18}}>
                  <label style={labelStyle}>Service Address</label>
                  <input value={activeClient.address} onChange={e=>updateClient("address",e.target.value)} style={inputStyle}/>
                </div>
                <div style={{marginBottom:18}}>
                  <label style={labelStyle}>Care Objective</label>
                  <textarea value={activeClient.objective||""} onChange={e=>updateClient("objective",e.target.value)}
                    rows={2} style={{...inputStyle,resize:"vertical",minHeight:48,lineHeight:"1.4"}}
                    placeholder="e.g., memory care, weight gain, meals, reduce high blood pressure"/>
                </div>

                {/* Default shift times */}
                <div style={{marginBottom:18}}>
                  <label style={labelStyle}>Default Shift</label>
                  <div style={{display:"flex",gap:8,alignItems:"center"}}>
                    <input type="time" value={activeClient.defaultShift?.start||"09:00"} onChange={e=>updateClientShift("start",e.target.value)}
                      style={{...inputStyle,width:"auto",flex:1}}/>
                    <span style={{color:"#b0988a",fontSize:13}}>to</span>
                    <input type="time" value={activeClient.defaultShift?.end||"17:00"} onChange={e=>updateClientShift("end",e.target.value)}
                      style={{...inputStyle,width:"auto",flex:1}}/>
                  </div>
                </div>

                {/* Medications */}
                <div style={{marginBottom:8}}>
                  <label style={labelStyle}>Medications</label>
                  {(activeClient.meds||[]).length === 0 && (
                    <div style={{fontSize:13,color:"#c0b0a0",fontStyle:"italic",marginBottom:8}}>No medications configured yet.</div>
                  )}
                  {(activeClient.meds||[]).map((med,i) => (
                    <div key={med.id} style={{background:"#fdfaf8",border:"1.5px solid #e8ddd8",borderRadius:10,padding:"12px 14px",marginBottom:8}}>
                      <div style={{display:"flex",gap:8,marginBottom:6}}>
                        <div style={{flex:2}}>
                          <label style={{...labelStyle,fontSize:10}}>Medication</label>
                          <input value={med.name} onChange={e=>updateMed(med.id,"name",e.target.value)}
                            placeholder="Name" style={{...inputStyle,fontSize:13,padding:"6px 10px"}}/>
                        </div>
                        <div style={{flex:1}}>
                          <label style={{...labelStyle,fontSize:10}}>Dosage</label>
                          <input value={med.dosage} onChange={e=>updateMed(med.id,"dosage",e.target.value)}
                            placeholder="e.g., 5mg" style={{...inputStyle,fontSize:13,padding:"6px 10px"}}/>
                        </div>
                      </div>
                      <div style={{display:"flex",gap:8,alignItems:"flex-end"}}>
                        <div style={{flex:1}}>
                          <label style={{...labelStyle,fontSize:10}}>Frequency</label>
                          <input value={med.frequency} onChange={e=>updateMed(med.id,"frequency",e.target.value)}
                            placeholder="e.g., 2x daily" style={{...inputStyle,fontSize:13,padding:"6px 10px"}}/>
                        </div>
                        <div style={{flex:1}}>
                          <label style={{...labelStyle,fontSize:10}}>Route</label>
                          <select value={med.route||"Oral"} onChange={e=>updateMed(med.id,"route",e.target.value)}
                            style={{...inputStyle,fontSize:13,padding:"6px 10px",cursor:"pointer"}}>
                            {["Oral","Topical","Injection","Inhaled","Sublingual","Other"].map(r=><option key={r}>{r}</option>)}
                          </select>
                        </div>
                        <button onClick={()=>removeMed(med.id)} title="Remove medication"
                          style={{fontSize:16,color:"#d08080",background:"none",border:"none",cursor:"pointer",padding:"6px",marginBottom:1,flexShrink:0}}>✕</button>
                      </div>
                    </div>
                  ))}
                  <button onClick={addMed} style={{fontSize:13,fontWeight:600,color:acc,background:"none",border:`1.5px dashed ${acc}50`,borderRadius:8,padding:"8px 14px",cursor:"pointer",width:"100%",marginTop:4}}>
                    + Add Medication
                  </button>
                </div>

                {/* Multi-recipient management */}
                <div style={{borderTop:"1px solid #f0e8e0",paddingTop:12,marginTop:16,display:"flex",gap:8}}>
                  <button onClick={addClient} style={{fontSize:12,color:acc,background:"none",border:`1.5px solid ${acc}40`,borderRadius:6,padding:"5px 12px",cursor:"pointer"}}>+ Add Recipient</button>
                  {(draft.clients||[]).length > 1 && (
                    <button onClick={()=>removeClient(activeClient.id)} style={{fontSize:12,color:"#c07070",background:"none",border:"1.5px solid #e0c0c0",borderRadius:6,padding:"5px 12px",cursor:"pointer"}}>Remove This Recipient</button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Signature Font picker */}
          <div style={{background:"white",borderRadius:16,overflow:"hidden",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:16}}>
            <div style={{background:chrome.titleBar,padding:"16px 24px"}}>
              <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:acc,marginBottom:4}}>Signature</div>
              <div style={{fontSize:14,color:chrome.mutedText}}>Used on monthly reports and weekly service logs.</div>
            </div>
            <div style={{padding:"20px 24px"}}>
              <div style={{display:"flex",flexDirection:"column",gap:4}}>
                {SIGNATURE_FONTS.map(f=>(
                  <button key={f} onClick={()=>setDraft(d=>({...d,signatureFont:f}))}
                    style={{textAlign:"left",padding:"7px 12px",borderRadius:7,border:draft.signatureFont===f?`2px solid ${acc}`:`1.5px solid ${acc}30`,background:draft.signatureFont===f?"#fff5f0":"white",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                    <span style={{fontFamily:`'${f}', cursive`,fontSize:20,color:"#2c1810",lineHeight:"28px"}}>{draft.name||"Your Name"}</span>
                    <span style={{fontSize:11,color:"#b0988a"}}>{f}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Color picker */}
          <div style={{background:"white",borderRadius:16,padding:"20px 24px",boxShadow:"0 2px 20px rgba(0,0,0,0.07)",marginBottom:20}}>
            <div style={{fontSize:11,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",marginBottom:12}}>Color Palette</div>
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
              <div style={{fontSize:12,fontWeight:700,color:"#8a5010",marginBottom:3}}>Save Failed</div>
              <div style={{fontSize:12,color:"#a87020"}}>{saveError}</div>
            </div>
          )}

          {/* Buttons */}
          <div style={{display:"flex",gap:10}}>
            <button onClick={onBack} disabled={saving} style={{flex:1,fontSize:14,fontWeight:700,padding:"12px 0",borderRadius:10,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:saving?"not-allowed":"pointer",opacity:saving?0.5:1}}>Cancel</button>
            <button onClick={handleSave} disabled={saving} style={{flex:2,fontSize:14,fontWeight:700,padding:"12px 0",borderRadius:10,border:"none",background:acc,color:"white",cursor:saving?"wait":"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`,opacity:saving?0.7:1}}>
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── SHARED UTILITY: HANDLE SUBMIT RESPONSE ───────────────────────────────
/**
 * Processes API response from weekly/monthly submit endpoints and updates UI state.
 * Handles both partial success (PDF saved but email failed) and full success cases.
 *
 * @param {Object} data - Response data from submit endpoint
 * @param {string} savedPath - Expected path where PDF should be saved (fallback)
 * @param {string[]} emails - Expected email recipients (fallback)
 * @param {Function} setNotification - State setter for notification display
 * @param {Function} setAlreadySaved - State setter for saved status flag
 * @param {Function} setSavedDate - State setter for saved date display
 */
function handleSubmitResponse(data, savedPath, emails, setNotification, setAlreadySaved, setSavedDate) {
  // Validate API response shape to prevent undefined value issues
  if (!data || typeof data !== 'object') {
    setNotification({
      error: 'Unable to process server response. Please try again or contact support if the issue persists.'
    });
    return;
  }

  const dateStr = new Date().toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});

  // Check for partial success: PDF saved but email failed
  if (data.saved && data.emailError) {
    setNotification({
      saved: data.saved,
      emailError: data.emailError
    });
    setAlreadySaved(true);
    setSavedDate(dateStr);
  } else if (data.saved || (data.sent && data.sent.length)) {
    // Full success - require at least one success indicator
    setNotification({
      sent: data.sent && data.sent.length ? data.sent : null,
      saved: data.saved || savedPath
    });
    setAlreadySaved(true);
    setSavedDate(dateStr);
  } else {
    // Response doesn't match expected success patterns
    setNotification({
      error: 'The submission did not complete successfully. Please verify your configuration and try again.'
    });
  }
}

// ── WEEKLY PAGE ───────────────────────────────────────────────────────────
function WeeklyPage({ config, onBack, emailConfigured, onOpenEmailSetup, emailSetupCount }) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [showCalendar, setShowCalendar] = useState(false);
  const calBtnRef = useRef(null);
  const week  = useMemo(()=>getWeekRange(weekOffset),[weekOffset]);
  const acc   = config.accent;
  const savedPath = weeklyPath(config.saveFolder, week.invNum);

  const [hours, setHours] = useState({Monday:8,Tuesday:8,Wednesday:8,Thursday:8,Friday:8,Saturday:0,Sunday:0});
  const [hoursSource, setHoursSource] = useState({}); // {Monday: "log"|"saved"|"default"}
  const [clientEmail,     setClientEmail]     = useState(config.clientEmail);
  const [accountantEmail, setAccountantEmail] = useState(config.accountantEmail);
  const [zoom,            setZoom]            = useState(()=>{const s=localStorage.getItem("invoiceZoom");return s?parseFloat(s):0.9;});
  const [activeTemplate,  setActiveTemplate]  = useState(()=>localStorage.getItem("invoiceTemplate")||"morning-light");
  const [notification,    setNotification]    = useState(null);
  const [alreadySaved,    setAlreadySaved]    = useState(false);
  const [savedDate,       setSavedDate]       = useState(null);
  const [showConfirm,     setShowConfirm]     = useState(false);
  const [submitting,      setSubmitting]      = useState(false);
  const [submitStep,      setSubmitStep]      = useState(1); // 1=invoice, 2=log review
  const [savedInvoicePath, setSavedInvoicePath] = useState(null);
  const [logPdfUrl,       setLogPdfUrl]       = useState(null);
  const submitInProgressRef = useRef(false);
  const hoursChangedRef = useRef(false);

  // Reset state when week changes, re-default hours, and check saved/log data
  useEffect(()=>{
    setHours({Monday:8,Tuesday:8,Wednesday:8,Thursday:8,Friday:8,Saturday:0,Sunday:0});
    setHoursSource({}); hoursChangedRef.current = false;
    setNotification(null); setAlreadySaved(false); setSavedDate(null);
    setSubmitStep(1); setSavedInvoicePath(null);
    if (logPdfUrl) { URL.revokeObjectURL(logPdfUrl); setLogPdfUrl(null); }

    const mon = week.monday;
    const mondayStr = `${mon.getFullYear()}-${pad(mon.getMonth()+1)}-${pad(mon.getDate())}`;

    // Check if this week's invoice already exists on disk
    fetch(`/api/scan?folder=${encodeURIComponent(config.saveFolder)}&invNum=${week.invNum}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.found) {
          setAlreadySaved(true);
          setSavedDate(data.date || null);
          if (data.dailyHours) {
            setHours(prev => ({...prev, ...data.dailyHours}));
            const src = {}; DAYS.forEach(d => { src[d] = "saved"; }); setHoursSource(src);
          }
          if (data.template) setActiveTemplate(data.template);
        } else {
          // No saved invoice — auto-populate from daily log shift times
          fetch(`/api/log-week?monday=${mondayStr}`)
            .then(r => r.ok ? r.json() : null)
            .then(logData => {
              if (!logData) return;
              const newHours = {}; const src = {};
              DAYS.forEach(d => {
                if (logData.hasLog[d] && logData.hours[d] > 0) { newHours[d] = logData.hours[d]; src[d] = "log"; }
                else if (logData.hasLog[d]) { newHours[d] = 0; src[d] = "log"; }
                else { newHours[d] = 0; src[d] = "default"; }
              });
              setHours(newHours);
              setHoursSource(src);
            })
            .catch(() => {});
        }
      })
      .catch(() => {});
  },[weekOffset]);

  // Clear stale "email failed" notification after email setup completes
  useEffect(()=>{
    if (emailSetupCount > 0 && notification?.emailError) setNotification(null);
  },[emailSetupCount]);

  const totalHours = Object.values(hours).reduce((a,b)=>a+b,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const setHour    = (day,v) => { hoursChangedRef.current = true; setHours(h=>({...h,[day]:v})); };

  // Step 1: Save invoice only (no email), then transition to log review
  const doSaveInvoice = async () => {
    if (submitInProgressRef.current) return;
    submitInProgressRef.current = true;
    setSubmitting(true);
    setNotification(null);
    setShowConfirm(false);

    try {
      const payload = {
        hours,
        clientEmail,
        accountantEmail,
        week: { start: week.start, end: week.end, invNum: week.invNum },
        template: activeTemplate,
        saveOnly: true
      };

      const response = await fetch('/api/submit/weekly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Unable to save invoice.');
      }

      const data = await response.json();
      setSavedInvoicePath(data.saved);
      setAlreadySaved(true);

      // Generate log PDF preview
      const logResp = await fetch('/api/submit/preview-weekly-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invNum: week.invNum })
      });

      if (logResp.ok) {
        const blob = await logResp.blob();
        const url = URL.createObjectURL(blob);
        setLogPdfUrl(url);
      }

      setSubmitStep(2);
    } catch (error) {
      console.error('Save invoice failed:', error);
      setNotification({ error: error.message || 'Unable to save invoice.' });
    } finally {
      setSubmitting(false);
      submitInProgressRef.current = false;
    }
  };

  // Preview logs only (skip saving invoice)
  const doPreviewLogsOnly = async () => {
    if (submitInProgressRef.current) return;
    submitInProgressRef.current = true;
    setSubmitting(true);
    setNotification(null);
    try {
      const logResp = await fetch('/api/submit/preview-weekly-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invNum: week.invNum })
      });
      if (logResp.ok) {
        const blob = await logResp.blob();
        setLogPdfUrl(URL.createObjectURL(blob));
      }
      setSavedInvoicePath(null); // mark as not saved
      setSubmitStep(2);
    } catch (error) {
      console.error('Log preview failed:', error);
      setNotification({ error: error.message || 'Unable to preview logs.' });
    } finally {
      setSubmitting(false);
      submitInProgressRef.current = false;
    }
  };

  // Step 2a: Send both invoice + logs
  const doSendWithLogs = async () => {
    if (submitInProgressRef.current) return;
    submitInProgressRef.current = true;
    setSubmitting(true);
    setNotification(null);

    try {
      const payload = {
        invNum: week.invNum,
        clientEmail,
        accountantEmail,
        hours
      };

      const response = await fetch('/api/submit/weekly-with-logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Unable to send.');
      }

      const data = await response.json();
      handleSubmitResponse(data, savedPath, [clientEmail, accountantEmail], setNotification, setAlreadySaved, setSavedDate);
    } catch (error) {
      console.error('Send with logs failed:', error);
      setNotification({ error: error.message || 'Unable to send.' });
    } finally {
      setSubmitting(false);
      submitInProgressRef.current = false;
    }
  };

  // Step 2b: Send invoice only (skip logs)
  const doSendInvoiceOnly = async () => {
    if (submitInProgressRef.current) return;
    submitInProgressRef.current = true;
    setSubmitting(true);
    setNotification(null);

    try {
      const payload = {
        hours,
        clientEmail,
        accountantEmail,
        week: { start: week.start, end: week.end, invNum: week.invNum },
        template: activeTemplate
      };

      const response = await fetch('/api/submit/weekly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Unable to submit.');
      }

      const data = await response.json();
      handleSubmitResponse(data, savedPath, [clientEmail, accountantEmail], setNotification, setAlreadySaved, setSavedDate);
    } catch (error) {
      console.error('Send invoice only failed:', error);
      setNotification({ error: error.message || 'Unable to send.' });
    } finally {
      setSubmitting(false);
      submitInProgressRef.current = false;
    }
  };

  const handleSubmit = async () => {
    if (submitInProgressRef.current) return;

    // If already saved and user hasn't changed hours, skip overwrite confirm — go straight to step 2
    if (alreadySaved && !hoursChangedRef.current) {
      await doSaveInvoice();
      return;
    }

    // Pre-flight check: does this invoice already exist?
    try {
      const scanResponse = await fetch(`/api/scan?folder=${encodeURIComponent(config.saveFolder)}&invNum=${week.invNum}`);
      if (scanResponse.ok) {
        const scanData = await scanResponse.json();
        if (scanData.found) {
          setAlreadySaved(true);
          setShowConfirm(true);
          return;
        }
      }
      await doSaveInvoice();
    } catch (error) {
      console.error('Pre-flight scan failed:', error);
      await doSaveInvoice();
    }
  };

  const PreviewComponent = activeTemplate==="morning-light"?TemplateMorningLight:activeTemplate==="caring-hands"?TemplateCaringHands:TemplateGarden;
  const LETTER_W=680, LETTER_H=Math.round(LETTER_W*(11/8.5));

  const isCurrent = weekOffset === 0;
  const weekLabel = isCurrent ? `${week.start} – ${week.end}` : weekOffset < 0 ? `${week.start} – ${week.end} (past)` : `${week.start} – ${week.end} (future)`;

  return (
    <Shell config={config} title="Weekly Invoice" subtitle={weekLabel} onBack={onBack} emailConfigured={emailConfigured} onOpenEmailSetup={onOpenEmailSetup}>
      {showConfirm && <ConfirmModal savedPath={savedPath} onConfirm={doSaveInvoice} onCancel={()=>setShowConfirm(false)} accent={acc}/>}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        {/* PDF */}
        <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
          {/* Toolbar: templates left | zoom center | week nav right */}
          <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"7px 20px",display:"flex",alignItems:"center",gap:6,flexShrink:0}}>
            <span style={{fontSize:12,letterSpacing:2,textTransform:"uppercase",color:chrome.mutedText,marginRight:2}}>Template</span>
            {TEMPLATES.map(t=>(
              <button key={t.id} className="tmpl-btn" onClick={()=>{setActiveTemplate(t.id);localStorage.setItem("invoiceTemplate",t.id);}} style={{fontFamily:"sans-serif",fontSize:14,padding:"5px 12px",borderRadius:20,border:`1px solid ${activeTemplate===t.id?acc:chrome.border}`,background:activeTemplate===t.id?acc:"transparent",color:activeTemplate===t.id?"white":chrome.mutedText,cursor:"pointer"}}>{t.label}</button>
            ))}
            <div style={{flex:1}}/>
            {/* Week nav + Zoom — right */}
            <div style={{display:"flex",alignItems:"center",gap:12}}>
              <div style={{display:"flex",alignItems:"center",gap:7}}>
                <button ref={calBtnRef} className="bsm" onClick={() => setShowCalendar(!showCalendar)}
                  style={{fontSize:15,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:"pointer"}}>📅</button>
                {showCalendar && <CalendarPicker accent={acc} initialYear={week.monday.getFullYear()} initialMonth={week.monday.getMonth()} mode="week" anchorRef={calBtnRef}
                  highlightedDays={async (y, m) => {
                    try {
                      const r = await fetch(`/api/scan-month?year=${y}&month=${m+1}&folder=${encodeURIComponent(config.saveFolder)}`);
                      const data = await r.json();
                      return (data.weeks||[]).filter(w => w.found).map(w => { const d = new Date(y, m, 1); const parts = w.invNum.replace("INV-",""); return parseInt(parts.slice(6,8)); });
                    } catch { return []; }
                  }}
                  onSelect={(monday) => {
                    const today = new Date(); today.setHours(0,0,0,0);
                    const todayDay = today.getDay();
                    const todayMonday = new Date(today); todayMonday.setDate(today.getDate() - ((todayDay+6)%7));
                    const diff = Math.round((monday - todayMonday) / (7*86400000));
                    setWeekOffset(diff);
                  }}
                  onClose={() => setShowCalendar(false)} />}
                <button className="bsm" onClick={()=>setWeekOffset(o=>o-1)} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,width:30,height:30,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}>‹</button>
                <span style={{fontSize:15,color:isCurrent?acc:chrome.mutedText,fontWeight:isCurrent?700:500,minWidth:60,textAlign:"center"}}>
                  {isCurrent?"This week":weekOffset<0?`${Math.abs(weekOffset)}w ago`:`+${weekOffset}w`}
                </span>
                <button className="bsm" onClick={()=>setWeekOffset(o=>o+1)} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,width:30,height:30,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}>›</button>
              </div>
              <div style={{width:1,height:18,background:chrome.border}}/>
              <div style={{display:"flex",alignItems:"center",gap:5}}>
                <button className="bsm" onClick={()=>setZoom(z=>{const v=Math.max(0.4,+(z-0.05).toFixed(2));localStorage.setItem("invoiceZoom",v);return v;})} style={{width:28,height:28,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:18,display:"flex",alignItems:"center",justifyContent:"center"}}>−</button>
                <span style={{fontSize:14,color:chrome.mutedText,width:40,textAlign:"center"}}>{Math.round(zoom*100)}%</span>
                <button className="bsm" onClick={()=>setZoom(z=>{const v=Math.min(1.4,+(z+0.05).toFixed(2));localStorage.setItem("invoiceZoom",v);return v;})} style={{width:28,height:28,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:18,display:"flex",alignItems:"center",justifyContent:"center"}}>+</button>
              </div>
            </div>
          </div>
          <div style={{flex:1,overflowY:"auto",overflowX:"auto",display:"flex",justifyContent:"center",alignItems:"flex-start",padding:"24px 20px",background:chrome.previewBg}}>
            {submitStep === 2 && logPdfUrl ? (
              <iframe src={logPdfUrl} title="Weekly Service Log Preview"
                style={{width:LETTER_W*zoom,height:"100%",minHeight:LETTER_H*zoom,border:"none",boxShadow:"0 4px 32px rgba(0,0,0,0.25)",background:"white"}}/>
            ) : (
              <div style={{width:LETTER_W*zoom,minHeight:LETTER_H*zoom,flexShrink:0,boxShadow:"0 4px 32px rgba(0,0,0,0.25)",background:"white",overflow:"hidden"}}>
                <div style={{transform:`scale(${zoom})`,transformOrigin:"top left",width:LETTER_W}}>
                  <PreviewComponent config={config} hours={hours} week={week} totalHours={totalHours} totalPay={totalPay}/>
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Editor sidebar */}
        <div style={{width:360,background:"#fdf8f4",borderLeft:`1px solid ${acc}18`,display:"flex",flexDirection:"column",overflow:"hidden",flexShrink:0}}>
          <div style={{flex:1,display:"flex",flexDirection:"column",padding:"20px 16px 0",overflowY:"auto"}}>

            {submitStep === 1 ? (<>
              {/* Step 1: Invoice editor */}
              <div style={{fontSize:12,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Hours This Week</div>
              <div style={{flex:"0 0 auto"}}>
                {DAYS.map(day=>(
                  <HourRow key={day} label={day} value={hours[day]} onChange={v=>setHour(day,v)} accent={acc}
                    sublabel={hoursSource[day]==="log"?"from log":undefined}/>
                ))}
                <div style={{background:"white",borderRadius:8,padding:"8px 12px",margin:"8px 0 0",display:"flex",justifyContent:"space-between",border:`1px solid ${acc}22`}}>
                  <div><div style={{fontSize:12,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Hours</div>
                    <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,color:"#2c1810",lineHeight:1.1}}>{totalHours}</div></div>
                  <div style={{textAlign:"right"}}><div style={{fontSize:12,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Total Due</div>
                    <div style={{fontFamily:"'Playfair Display',serif",fontSize:23,color:acc,fontWeight:700,lineHeight:1.1}}>${totalPay}</div></div>
                </div>
              </div>
              {/* Saved status pill */}
              <div style={{flexShrink:0,marginTop:32,marginBottom:32}}>
                {alreadySaved ? (
                  <div style={{display:"flex",alignItems:"center",gap:5,background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:20,padding:"4px 11px",fontSize:13,color:"#4a7a50",maxWidth:"100%",overflow:"hidden",width:"fit-content"}}>
                    <span>💾</span>
                    <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                      {savedDate ? `Saved · ${week.invNum} · ${savedDate}` : `File exists · ${week.invNum}`}
                    </span>
                  </div>
                ) : (
                  <div style={{display:"flex",alignItems:"center",gap:5,background:"#f5f0eb",border:"1px solid #e0d4cc",borderRadius:20,padding:"4px 11px",fontSize:13,color:"#9a8070",width:"fit-content"}}>
                    <span style={{fontSize:12}}>○</span> Not yet saved for this week
                  </div>
                )}
                <div onClick={()=>fetch('/api/open-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:config.saveFolder})}).catch(()=>{})}
                  style={{display:"flex",alignItems:"center",gap:5,fontSize:13,color:"#b0a090",marginTop:8,paddingLeft:11,cursor:"pointer"}}
                  title="Open folder">
                  <span style={{fontSize:14}}>📁</span> <span style={{fontFamily:"monospace",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",textDecoration:"underline",textDecorationColor:"#d0c0b8"}}>{config.saveFolder}</span>
                </div>
              </div>
            </>) : (<>
              {/* Step 2: Log review + email */}
              <div style={{background:`linear-gradient(135deg, white, ${tint(acc,0.05)})`,borderRadius:12,border:`1.5px solid ${tint(acc, savedInvoicePath ? 0.15 : 0.08)}`,padding:"16px 18px",marginBottom:20}}>
                <div style={{fontSize:14,fontWeight:700,color:"#2c1810",marginBottom:6}}>
                  {savedInvoicePath ? "Invoice Saved" : "Preview Mode"}
                </div>
                <div style={{fontSize:13,color:"#8a7060",lineHeight:1.4}}>
                  {savedInvoicePath
                    ? "Review the weekly service log below. When ready, send both documents to your recipients."
                    : "Previewing aggregated logs. Go back to save the invoice before sending."}
                </div>
              </div>

              {/* Signature warning */}
              {!config.signatureFont && (
                <div style={{background:"#fff8f0",border:"1.5px solid #e8c870",borderRadius:10,padding:"12px 16px",marginBottom:16}}>
                  <div style={{fontSize:13,fontWeight:600,color:"#8a6a20",marginBottom:4}}>Signature Required</div>
                  <div style={{fontSize:12,color:"#9a7a30",lineHeight:1.4}}>
                    Select a signature font in <strong>Edit Profile</strong> to sign your service logs.
                  </div>
                </div>
              )}

              <button onClick={()=>setSubmitStep(1)}
                style={{fontSize:13,color:acc,background:"none",border:"none",cursor:"pointer",padding:0,marginBottom:20,textAlign:"left"}}>
                ← Back to Invoice
              </button>

              <div style={{flexShrink:0,marginBottom:32}}>
                <div style={{fontSize:12,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Send To</div>
                {[{label:"Client",value:clientEmail,set:setClientEmail},{label:"Accountant",value:accountantEmail,set:setAccountantEmail}].map(({label,value,set})=>(
                  <div key={label} style={{marginBottom:7}}>
                    <div style={{fontSize:13,color:"#b0988a",marginBottom:3}}>{label}</div>
                    <input value={value} onChange={e=>set(e.target.value)}
                        style={{width:"100%",fontSize:15,border:`1.5px solid ${acc}30`,borderRadius:6,padding:"7px 10px",color:"#2c1810",outline:"none",background:"white"}}
                        onFocus={e=>{e.target.style.borderColor=acc;e.target.style.boxShadow=`0 0 0 2px ${tint(acc,0.12)}`;}}
                        onBlur={e=>{e.target.style.borderColor=`${acc}30`;e.target.style.boxShadow="none";}}/>
                    </div>
                  ))}
              </div>
            </>)}

            <div style={{flex:1}}/>
          </div>
          <div style={{flexShrink:0,borderTop:`1px solid ${acc}18`,background:"#fdf8f4"}}>
            {notification && <div style={{padding:"10px 16px 0"}}><NotifCard notification={notification} onDismiss={()=>setNotification(null)} onOpenEmailSetup={onOpenEmailSetup} accent={acc}/></div>}
            <div style={{padding:"10px 16px 14px"}}>
              {submitStep === 1 ? (<>
                <button onClick={handleSubmit} disabled={submitting} style={{width:"100%",fontSize:16,fontWeight:700,padding:"12px 0",borderRadius:9,border:"none",background:`linear-gradient(135deg,${acc},${acc}bb)`,color:"white",cursor:submitting?"wait":"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`,opacity:submitting?0.7:1}}>
                  {submitting ? "Saving..." : "Save & Review Logs"}
                </button>
                <button onClick={doPreviewLogsOnly} disabled={submitting}
                  style={{width:"100%",fontSize:13,color:"#9a8070",background:"none",border:"none",cursor:submitting?"wait":"pointer",padding:"8px 0 0",textDecoration:"underline",textDecorationColor:"#d0c0b8"}}>
                  Preview Logs Only
                </button>
              </>) : (
                <div style={{display:"flex",flexDirection:"column",gap:8}}>
                  {(()=>{const cantSend=submitting||!config.signatureFont||!savedInvoicePath;return(<>
                  <button onClick={doSendWithLogs} disabled={cantSend} style={{width:"100%",fontSize:16,fontWeight:700,padding:"12px 0",borderRadius:9,border:"none",background:`linear-gradient(135deg,${acc},${acc}bb)`,color:"white",cursor:cantSend?"not-allowed":"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`,opacity:cantSend?0.5:1}}>
                    {submitting ? "Sending..." : "Send Invoice & Logs"}
                  </button>
                  {!config.signatureFont && (
                    <div style={{fontSize:12,color:"#9a7a30",textAlign:"center",lineHeight:1.3}}>
                      Select a signature font in <strong>Edit Profile</strong> to send logs.
                    </div>
                  )}
                  {!savedInvoicePath && config.signatureFont && (
                    <div style={{fontSize:12,color:"#9a8070",textAlign:"center",lineHeight:1.3}}>
                      Save the invoice first to enable sending.
                    </div>
                  )}
                  </>);})()}
                  <button onClick={doSendInvoiceOnly} disabled={submitting||!savedInvoicePath} style={{width:"100%",fontSize:14,fontWeight:600,padding:"10px 0",borderRadius:9,border:`1.5px solid ${acc}30`,background:"white",color:acc,cursor:(submitting||!savedInvoicePath)?"not-allowed":"pointer",opacity:(submitting||!savedInvoicePath)?0.5:1}}>
                    Send Invoice Only
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── MONTHLY PAGE ──────────────────────────────────────────────────────────
function MonthlyPage({ config, onBack, emailConfigured, onOpenEmailSetup, emailSetupCount }) {
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [showCalendar, setShowCalendar] = useState(false);
  const calBtnRef = useRef(null);
  const [zoom,  setZoom]  = useState(()=>{const s=localStorage.getItem("invoiceZoom");return s?parseFloat(s):0.9;});
  const [notification, setNotification] = useState(null);
  const [alreadySaved, setAlreadySaved] = useState(false);
  const [savedDate,    setSavedDate]    = useState(null);
  const [showConfirm,  setShowConfirm]  = useState(false);
  const [scanPopup,    setScanPopup]    = useState(null); // null | results[]
  const [lastScanResults, setLastScanResults] = useState(null); // persists after popup closes
  const [accountantEmail, setAccountantEmail] = useState(config.accountantEmail);
  const [submitting,   setSubmitting]   = useState(false);
  const signatureFont = config.signatureFont || "Dancing Script";
  const submitInProgressRef = useRef(false);
  const isFirstLoad = useRef(true);
  const acc = config.accent;

  const weeks     = useMemo(()=>getWeeksForMonth(year,month),[year,month]);
  const [weekHours, setWeekHours] = useState(()=>weeks.map(()=>0));
  const monthLabel  = new Date(year,month,1).toLocaleDateString("en-US",{month:"long",year:"numeric"});
  const monthOffset = (year - now.getFullYear()) * 12 + (month - now.getMonth());
  const isCurrentMonth = monthOffset === 0;
  const monthNavLabel = isCurrentMonth ? "This month" : monthOffset === -1 ? "1m ago" : monthOffset < 0 ? `${Math.abs(monthOffset)}m ago` : `+${monthOffset}m`;
  const savedPath   = monthlyPath(config.saveFolder, year, month);

  // Clear stale "email failed" notification after email setup completes
  useEffect(()=>{
    if (emailSetupCount > 0 && notification?.emailError) setNotification(null);
  },[emailSetupCount]);

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
          throw new Error(`Unable to scan for existing weekly invoices. You can still manually enter hours.`);
        }
        return response.json();
      })
      .then(data => {
        // data.weeks: [{ label, invNum, found, hours }]
        const results = data.weeks || [];
        const newHours = results.map(r => r.hours || 0);
        setWeekHours(newHours);
        setLastScanResults(results);
        if (isFirstLoad.current) { setScanPopup(results); isFirstLoad.current = false; }

        // Check if monthly report already exists to set alreadySaved flag
        if (data.monthlyExists) {
          setAlreadySaved(true);
        }
      })
      .catch(error => {
        // Ignore abort errors - component unmounted or month changed before fetch completed
        if (error.name === 'AbortError') return;
        console.error('Monthly scan failed:', error);
        // Non-critical — user can still manually enter hours
        // Set empty results on error - user can still manually enter hours
        // Use currentWeeks captured at effect start to avoid stale closure
        const fallback = currentWeeks.map(w => ({ label: w.label, invNum: w.invNum, found: false, hours: 0 }));
        setLastScanResults(fallback);
        if (isFirstLoad.current) { setScanPopup(fallback); isFirstLoad.current = false; }
      });

    return () => abortController.abort();
  },[year,month,config.saveFolder]);

  const weeksWithData = useMemo(()=>weeks.map((w,i)=>({...w,hours:weekHours[i]||0})),[weeks,weekHours]);
  const totalHours = weeksWithData.reduce((s,w)=>s+w.hours,0);
  const totalPay   = (totalHours*config.rate).toFixed(2);
  const setWeekHour = (i,v) => setWeekHours(h=>{ const n=[...h]; n[i]=v; return n; });

  const doSend = async () => {
    // Prevent race condition from rapid clicks - ref updates synchronously
    if (submitInProgressRef.current) {
      return;
    }

    submitInProgressRef.current = true;
    setSubmitting(true);
    setNotification(null);
    setShowConfirm(false);

    try {
      // Prepare payload for monthly submit endpoint
      const payload = {
        weekData: weeksWithData.map(w => ({ label: w.label, hours: w.hours })),
        year: year,
        month: month + 1, // Backend expects 1-indexed month
        accountantEmail: accountantEmail,
        signatureFont: signatureFont
      };

      const response = await fetch('/api/submit/monthly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Unable to submit your monthly report. Please check your settings and try again.`);
      }

      const data = await response.json();

      // Update UI with actual response data using shared handler
      handleSubmitResponse(
        data,
        savedPath,
        [accountantEmail],
        setNotification,
        setAlreadySaved,
        setSavedDate
      );

    } catch (error) {
      console.error('Monthly submit failed:', error);
      setNotification({
        error: error.message || 'Unable to submit monthly report. Please try again.'
      });
    } finally {
      // Always reset submitting state and ref in all code paths (success, error, or early return)
      setSubmitting(false);
      submitInProgressRef.current = false;
    }
  };

  const handleSubmit = async () => {
    // Prevent multiple submissions
    if (submitInProgressRef.current) {
      return;
    }

    if (alreadySaved) {
      setShowConfirm(true);
      return;
    }
    await doSend();
  };
  const prevMonth = () => { setNotification(null); if(month===0){setYear(y=>y-1);setMonth(11);}else setMonth(m=>m-1); };
  const nextMonth = () => { setNotification(null); if(month===11){setYear(y=>y+1);setMonth(0);}else setMonth(m=>m+1); };

  const LETTER_W=680, LETTER_H=Math.round(LETTER_W*(11/8.5));

  return (
    <Shell config={config} title="Monthly Report" subtitle={isCurrentMonth ? monthLabel : monthOffset < 0 ? `${monthLabel} (past)` : `${monthLabel} (future)`} onBack={onBack} emailConfigured={emailConfigured} onOpenEmailSetup={onOpenEmailSetup}>
      {showConfirm && <ConfirmModal savedPath={savedPath} onConfirm={doSend} onCancel={()=>setShowConfirm(false)} accent={acc}/>}
      {scanPopup   && <ScanPopup results={scanPopup} onClose={()=>setScanPopup(null)}/>}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        {/* PDF */}
        <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
          <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"7px 20px",display:"flex",alignItems:"center",gap:8,flexShrink:0}}>
            {lastScanResults && (
              <button className="bsm" onClick={()=>setScanPopup(lastScanResults)}
                style={{fontSize:13,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 10px",cursor:"pointer",display:"flex",alignItems:"center",gap:5}}>
                📁 Scan
              </button>
            )}
            <div style={{flex:1}}/>
            {/* Month nav + Zoom — right */}
            <div style={{display:"flex",alignItems:"center",gap:12}}>
              <div style={{display:"flex",alignItems:"center",gap:7}}>
                <button ref={calBtnRef} className="bsm" onClick={() => setShowCalendar(!showCalendar)}
                  style={{fontSize:15,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:"pointer"}}>📅</button>
                {showCalendar && <CalendarPicker accent={acc} initialYear={year} initialMonth={month} mode="month" anchorRef={calBtnRef}
                  highlightedDays={async (y) => {
                    // Highlight months that have any weekly invoices
                    const months = [];
                    for (let m = 0; m < 12; m++) {
                      try {
                        const r = await fetch(`/api/scan-month?year=${y}&month=${m+1}&folder=${encodeURIComponent(config.saveFolder)}`);
                        const data = await r.json();
                        if (data.monthlyExists || (data.weeks||[]).some(w => w.found)) months.push(m);
                      } catch {}
                    }
                    return months;
                  }}
                  onSelect={(y, m) => { setYear(y); setMonth(m); setNotification(null); }}
                  onClose={() => setShowCalendar(false)} />}
                <button className="bsm" onClick={prevMonth} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 12px",cursor:"pointer"}}>‹</button>
                <span style={{fontSize:15,color:isCurrentMonth?acc:chrome.mutedText,fontWeight:isCurrentMonth?700:500,minWidth:80,textAlign:"center"}}>{monthNavLabel}</span>
                <button className="bsm" onClick={nextMonth} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 12px",cursor:"pointer"}}>›</button>
              </div>
              <div style={{width:1,height:18,background:chrome.border}}/>
              <div style={{display:"flex",alignItems:"center",gap:5}}>
                <button className="bsm" onClick={()=>setZoom(z=>{const v=Math.max(0.4,+(z-0.05).toFixed(2));localStorage.setItem("invoiceZoom",v);return v;})} style={{width:28,height:28,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:18,display:"flex",alignItems:"center",justifyContent:"center"}}>−</button>
                <span style={{fontSize:14,color:chrome.mutedText,width:40,textAlign:"center"}}>{Math.round(zoom*100)}%</span>
                <button className="bsm" onClick={()=>setZoom(z=>{const v=Math.min(1.4,+(z+0.05).toFixed(2));localStorage.setItem("invoiceZoom",v);return v;})} style={{width:28,height:28,border:`1px solid ${chrome.border}`,background:"transparent",color:chrome.mutedText,borderRadius:5,cursor:"pointer",fontSize:18,display:"flex",alignItems:"center",justifyContent:"center"}}>+</button>
              </div>
            </div>
          </div>
          <div style={{flex:1,overflowY:"auto",overflowX:"auto",display:"flex",justifyContent:"center",alignItems:"flex-start",padding:"24px 20px",background:chrome.previewBg}}>
            <div style={{width:LETTER_W*zoom,minHeight:LETTER_H*zoom,flexShrink:0,boxShadow:"0 4px 32px rgba(0,0,0,0.25)",background:"white",overflow:"hidden"}}>
              <div style={{transform:`scale(${zoom})`,transformOrigin:"top left",width:LETTER_W}}>
                <MonthlyReportPDF config={config} weekData={weeksWithData} monthLabel={monthLabel} signatureFont={signatureFont}/>
              </div>
            </div>
          </div>
        </div>
        {/* Editor */}
        <div style={{width:360,background:"#fdf8f4",borderLeft:`1px solid ${acc}18`,display:"flex",flexDirection:"column",overflow:"hidden",flexShrink:0}}>
          <div style={{flex:1,display:"flex",flexDirection:"column",padding:"20px 16px 0",overflowY:"auto"}}>
            <div style={{fontSize:12,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Hours Per Week</div>
            <div style={{flex:"0 0 auto",overflowY:"auto"}}>
              {weeksWithData.map((w,i)=>(
                <HourRow key={i} label={`Week ${i+1}`} sublabel={w.label} value={w.hours} onChange={v=>setWeekHour(i,v)} accent={acc}/>
              ))}
              <div style={{background:"white",borderRadius:8,padding:"8px 12px",margin:"8px 0 0",display:"flex",justifyContent:"space-between",border:`1px solid ${acc}22`}}>
                <div><div style={{fontSize:12,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Hours</div>
                  <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,color:"#2c1810",lineHeight:1.1}}>{totalHours}</div></div>
                <div style={{textAlign:"right"}}><div style={{fontSize:12,letterSpacing:1,textTransform:"uppercase",color:"#9a8070"}}>Total</div>
                  <div style={{fontFamily:"'Playfair Display',serif",fontSize:23,color:acc,fontWeight:700,lineHeight:1.1}}>${totalPay}</div></div>
              </div>
            </div>
            {/* Saved status pill */}
            <div style={{flexShrink:0,marginTop:32,marginBottom:32}}>
              {alreadySaved ? (
                <div style={{display:"flex",alignItems:"center",gap:5,background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:20,padding:"4px 11px",fontSize:13,color:"#4a7a50",maxWidth:"100%",overflow:"hidden",width:"fit-content"}}>
                  <span>💾</span>
                  <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                    {savedDate ? `Saved · ${monthLabel} · ${savedDate}` : `File exists · ${monthLabel}`}
                  </span>
                </div>
              ) : (
                <div style={{display:"flex",alignItems:"center",gap:5,background:"#f5f0eb",border:"1px solid #e0d4cc",borderRadius:20,padding:"4px 11px",fontSize:13,color:"#9a8070",width:"fit-content"}}>
                  <span style={{fontSize:12}}>○</span> Not yet saved for this month
                </div>
              )}
              <div onClick={()=>fetch('/api/open-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:config.saveFolder})}).catch(()=>{})}
                style={{display:"flex",alignItems:"center",gap:5,fontSize:13,color:"#b0a090",marginTop:8,paddingLeft:11,cursor:"pointer"}}
                title="Open folder">
                <span style={{fontSize:14}}>📁</span> <span style={{fontFamily:"monospace",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",textDecoration:"underline",textDecorationColor:"#d0c0b8"}}>{config.saveFolder}</span>
              </div>
            </div>
            <div style={{flexShrink:0,marginBottom:32}}>
              <div>
                <div style={{fontSize:12,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginBottom:6}}>Send To</div>
                <div style={{marginBottom:7}}>
                  <div style={{fontSize:13,color:"#b0988a",marginBottom:3}}>Accountant</div>
                  <input value={accountantEmail} onChange={e=>setAccountantEmail(e.target.value)}
                    style={{width:"100%",fontSize:15,border:`1.5px solid ${acc}30`,borderRadius:6,padding:"7px 10px",color:"#2c1810",outline:"none",background:"white"}}
                    onFocus={e=>{e.target.style.borderColor=acc;e.target.style.boxShadow=`0 0 0 2px ${tint(acc,0.12)}`;}}
                    onBlur={e=>{e.target.style.borderColor=`${acc}30`;e.target.style.boxShadow="none";}}/>
                </div>
                <div style={{fontSize:13,color:"#c0a898",fontStyle:"italic"}}>Monthly reports go to your accountant only.</div>
              </div>
            </div>
            <div style={{flex:1}}/>
          </div>
          <div style={{flexShrink:0,borderTop:`1px solid ${acc}18`,background:"#fdf8f4"}}>
            {notification && <div style={{padding:"10px 16px 0"}}><NotifCard notification={notification} onDismiss={()=>setNotification(null)} onOpenEmailSetup={onOpenEmailSetup} accent={acc}/></div>}
            <div style={{padding:"10px 16px 14px"}}>
              <button onClick={handleSubmit} disabled={submitting} style={{width:"100%",fontSize:16,fontWeight:700,padding:"12px 0",borderRadius:9,border:"none",background:`linear-gradient(135deg,${acc},${acc}bb)`,color:"white",cursor:submitting?"wait":"pointer",boxShadow:`0 3px 14px ${tint(acc,0.35)}`,opacity:submitting?0.7:1}}>
                {submitting ? "Sending Report..." : "Generate & Send Report 📊"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

// ── ROOT ──────────────────────────────────────────────────────────────────
// ── EMAIL SETUP MODAL ──────────────────────────────────────────────────
function EmailSetupModal({ onDone, onSkip, isEditing }) {
  const [gmailAddress, setGmailAddress] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [alreadyVerified, setAlreadyVerified] = useState(false);
  const [wantsToChange, setWantsToChange] = useState(false);

  // Load existing email address and verification status on mount
  useEffect(() => {
    fetch('/api/email-status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          if (data.gmailAddress) setGmailAddress(data.gmailAddress);
          if (data.configured) setAlreadyVerified(true);
        }
        setLoadingExisting(false);
      })
      .catch(() => setLoadingExisting(false));
  }, []);

  const handleSave = async () => {
    // If already verified and user hasn't changed anything, just close
    if (alreadyVerified && !wantsToChange) {
      setSuccess("Email is already verified and ready to send.");
      setTimeout(() => onDone(), 1000);
      return;
    }
    if (!gmailAddress.trim()) { setError("Please enter your Gmail address."); return; }
    if (!appPassword.trim()) { setError("Please enter your app password."); return; }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch('/api/email-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gmailAddress: gmailAddress.trim(), gmailAppPassword: appPassword.trim() })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Failed to save email settings.");
      setSuccess("Connected successfully! Your email is ready to send invoices.");
      setTimeout(() => onDone(), 1200);
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  };

  const inputStyle = {
    width:"100%",fontSize:15,padding:"10px 12px",borderRadius:8,
    border:"1.5px solid #d8ccc4",fontFamily:"monospace",color:"#2c1810",
    background:"white",outline:"none",boxSizing:"border-box"
  };
  const labelStyle = {fontSize:12,fontWeight:700,color:"#6a4a40",letterSpacing:0.5,marginBottom:5,display:"block"};

  // Whether to show the full form (new setup, or user chose to change existing)
  const showForm = !alreadyVerified || wantsToChange;

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(44,24,16,0.55)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:500,padding:16}}>
      <div style={{background:"white",borderRadius:18,maxWidth:440,width:"100%",overflow:"hidden",boxShadow:"0 12px 60px rgba(0,0,0,0.3)"}}>
        {/* Header */}
        <div style={{background:chrome.titleBar,padding:"20px 24px"}}>
          <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:"#e0c090",marginBottom:6}}>
            {isEditing ? "Email Settings" : "Email Setup"}
          </div>
          <div style={{fontFamily:"'Playfair Display',serif",fontSize:21,color:"#f0e0d0",fontWeight:700}}>
            {isEditing ? "Email Settings" : "Set Up Email Sending"}
          </div>
          <div style={{fontSize:14,color:chrome.mutedText,marginTop:6,lineHeight:1.5}}>
            {alreadyVerified && !wantsToChange
              ? "Your email is connected and ready to send invoices."
              : isEditing
                ? "Update your Gmail address or app password below."
                : "To send invoices by email, you need a Gmail address and an app password."}
          </div>
        </div>

        {/* Body */}
        <div style={{padding:"20px 24px"}}>
          {loadingExisting ? (
            <div style={{textAlign:"center",padding:"20px 0",color:"#9a8070",fontSize:14}}>Loading...</div>
          ) : (<>
            {/* Verified status badge */}
            {alreadyVerified && !wantsToChange && (
              <div style={{marginBottom:18}}>
                <div style={{background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:10,padding:"14px 16px",display:"flex",alignItems:"center",gap:10}}>
                  <span style={{fontSize:23}}>✓</span>
                  <div>
                    <div style={{fontSize:15,fontWeight:700,color:"#2d6a2d",marginBottom:2}}>Email Verified</div>
                    <div style={{fontSize:14,color:"#4a7a50",fontFamily:"monospace"}}>{gmailAddress}</div>
                  </div>
                </div>
                <button onClick={()=>setWantsToChange(true)}
                  style={{marginTop:10,fontSize:13,color:"#9a8070",background:"none",border:"1px dashed #d0c0b0",borderRadius:8,padding:"6px 14px",cursor:"pointer",width:"100%",transition:"all 0.15s"}}
                  onMouseEnter={e=>{e.currentTarget.style.borderColor="#8a6a5a";e.currentTarget.style.color="#6a4a40";}}
                  onMouseLeave={e=>{e.currentTarget.style.borderColor="#d0c0b0";e.currentTarget.style.color="#9a8070";}}>
                  Change email or app password
                </button>
              </div>
            )}

            {showForm && (<>
              {/* Gmail address */}
              <div style={{marginBottom:16}}>
                <label style={labelStyle}>Gmail Address</label>
                <input
                  type="email" placeholder="yourname@gmail.com" value={gmailAddress}
                  onChange={e=>setGmailAddress(e.target.value)}
                  style={inputStyle}
                />
              </div>

              {/* App password */}
              <div style={{marginBottom:18}}>
                <label style={labelStyle}>Gmail App Password</label>
                <div style={{position:"relative"}}>
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="xxxx xxxx xxxx xxxx" value={appPassword}
                    onChange={e=>setAppPassword(e.target.value)}
                    style={{...inputStyle,paddingRight:40}}
                  />
                  <button onClick={()=>setShowPassword(v=>!v)}
                    style={{position:"absolute",right:8,top:"50%",transform:"translateY(-50%)",background:"none",border:"none",cursor:"pointer",fontSize:15,color:"#9a8070"}}>
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {/* Instructions */}
              <div style={{background:"#f9f3ee",border:"1px solid #e8ddd4",borderRadius:10,padding:"14px 16px",marginBottom:18}}>
                <div style={{fontSize:13,fontWeight:700,color:"#4a3028",marginBottom:8}}>How to get a Gmail App Password:</div>
                <ol style={{margin:0,paddingLeft:18,fontSize:13,color:"#6a4a40",lineHeight:1.8}}>
                  <li>Go to <strong>myaccount.google.com</strong></li>
                  <li>Click <strong>Security</strong> on the left sidebar</li>
                  <li>Under "How you sign in to Google", make sure <strong>2-Step Verification</strong> is turned on</li>
                  <li>Go back to Security, then click <strong>2-Step Verification</strong></li>
                  <li>Scroll to the bottom and click <strong>App passwords</strong></li>
                  <li>Enter a name (e.g. "Invoice Builder") and click <strong>Create</strong></li>
                  <li>Copy the 16-character password and paste it above</li>
                </ol>
              </div>
            </>)}

            {/* Success */}
            {success && (
              <div style={{fontSize:13,color:"#2d6a2d",background:"#f0f8f2",border:"1px solid #b0d8b8",borderRadius:8,padding:"10px 12px",marginBottom:14,display:"flex",alignItems:"center",gap:8}}>
                <span style={{fontSize:17}}>✓</span> {success}
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{fontSize:13,color:"#c4504f",background:"#fff5f2",border:"1px solid #f0c8b8",borderRadius:8,padding:"8px 12px",marginBottom:14,lineHeight:1.5}}>
                {error}
              </div>
            )}

            {/* Buttons */}
            <div style={{display:"flex",gap:10}}>
              {alreadyVerified && !wantsToChange ? (
                <button onClick={onSkip}
                  style={{flex:1,fontSize:14,fontWeight:700,padding:"11px 0",borderRadius:10,border:"none",background:chrome.titleBar,color:"white",cursor:"pointer"}}>
                  Close
                </button>
              ) : (<>
                <button onClick={onSkip} disabled={saving}
                  style={{flex:1,fontSize:14,fontWeight:700,padding:"11px 0",borderRadius:10,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:"pointer"}}>
                  {isEditing ? "Cancel" : "Skip for Now"}
                </button>
                <button onClick={handleSave} disabled={saving || !!success}
                  style={{flex:2,fontSize:14,fontWeight:700,padding:"11px 0",borderRadius:10,border:"none",background:chrome.titleBar,color:"white",cursor:saving?"wait":"pointer",opacity:(saving||!!success)?0.7:1}}>
                  {saving ? "Verifying..." : success ? "Done!" : "Verify & Save"}
                </button>
              </>)}
            </div>
          </>)}
        </div>
      </div>
    </div>
  );
}

// ── AUTO-RESIZE TEXTAREA ──────────────────────────────────────────────────
function makeTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase();
}

function AutoTextarea({ value, onChange, placeholder, style, timestamped, ...props }) {
  const ref = useRef(null);
  const pendingStampRef = useRef(false);
  useEffect(() => {
    if (ref.current) { ref.current.style.height = "auto"; ref.current.style.height = ref.current.scrollHeight + "px"; }
  }, [value]);

  const handleKeyDown = (e) => {
    if (!timestamped) return;
    if (e.key === "Enter") {
      e.preventDefault();
      const ta = ref.current;
      const pos = ta.selectionStart;
      const before = value.slice(0, pos);
      const after = value.slice(ta.selectionEnd);
      const stamp = `${makeTimestamp()} — `;
      const inserted = `\n\n${stamp}`;
      const newVal = before + inserted + after;
      onChange({ target: { value: newVal } });
      const newPos = pos + inserted.length;
      setTimeout(() => { ta.selectionStart = ta.selectionEnd = newPos; }, 0);
    } else if (!value.trim() && e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
      // First keystroke into empty section — prepend timestamp
      e.preventDefault();
      const stamp = `${makeTimestamp()} — ${e.key}`;
      onChange({ target: { value: stamp } });
      setTimeout(() => { if (ref.current) { ref.current.selectionStart = ref.current.selectionEnd = stamp.length; } }, 0);
    }
  };

  return <textarea ref={ref} value={value} onChange={onChange} placeholder={placeholder}
    onKeyDown={handleKeyDown} {...props}
    style={{...style, overflow:"hidden", resize:"none"}} />;
}

// ── DAILY SERVICE LOG ─────────────────────────────────────────────────────
const EMPTY_VITALS = Object.fromEntries(ALL_VITALS.map(v => [v.key, null]));

function DailyLogPage({ config, onBack }) {
  const acc = config.accent;
  const activeClient = getActiveClient(config);
  const [dayOffset, setDayOffset] = useState(0);
  const [sections, setSections] = useState([]);
  const [sectionNames, setSectionNames] = useState(null);
  const [saveStatus, setSaveStatus] = useState("idle");
  const [saveCount, setSaveCount] = useState(0);
  const [editingNewIdx, setEditingNewIdx] = useState(null);
  const [showCalendar, setShowCalendar] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const calBtnRef = useRef(null);
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);

  // Structured fields
  const [vitals, setVitals] = useState({...EMPTY_VITALS});
  const [shift, setShift] = useState({start: activeClient.defaultShift?.start || "", end: activeClient.defaultShift?.end || ""});
  const [medChecklist, setMedChecklist] = useState([]);
  const [showAddMed, setShowAddMed] = useState(false);
  const [newMed, setNewMed] = useState({name:"",dosage:"",route:"Oral"});
  const [showVitalsModal, setShowVitalsModal] = useState(false);
  const [hoverVital, setHoverVital] = useState(null);

  // Enabled vitals from config
  const [localEnabledVitals, setLocalEnabledVitals] = useState(null);
  const enabledVitals = localEnabledVitals || config.enabledVitals || DEFAULT_ENABLED_VITALS;
  const activeVitals = enabledVitals.map(key => ALL_VITALS.find(v => v.key === key)).filter(Boolean);
  const [vitalDragIdx, setVitalDragIdx] = useState(null);
  const [vitalDragOverIdx, setVitalDragOverIdx] = useState(null);

  const saveEnabledVitals = (updated) => {
    setLocalEnabledVitals(updated);
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({...config, enabledVitals: updated})
    }).catch(() => {});
  };

  const removeVitalFromConfig = (key) => {
    saveEnabledVitals(enabledVitals.filter(k => k !== key));
  };

  // Undo/redo
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  const pushUndo = (snapshot) => { setUndoStack(prev => [...prev.slice(-50), snapshot]); setRedoStack([]); };

  const timerRef = useRef(null);
  const abortRef = useRef(null);
  const dirtyRef = useRef(false);
  const dirtyDateRef = useRef(null); // tracks which date the pending save is for
  const clearedDatesRef = useRef(new Set()); // dates cleared this session, to prevent stale GET overwrites
  const sectionsRef = useRef(sections);
  const sectionNamesRef = useRef(sectionNames);
  const vitalsRef = useRef(vitals);
  const shiftRef = useRef(shift);
  const medChecklistRef = useRef(medChecklist);
  const locallyRemovedRef = useRef(new Set());
  sectionsRef.current = sections;
  vitalsRef.current = vitals;
  shiftRef.current = shift;
  medChecklistRef.current = medChecklist;
  sectionNamesRef.current = sectionNames;

  // Compute date
  const dateInfo = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + dayOffset);
    const dateStr = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    const abs = Math.abs(dayOffset);
    const navLabel = dayOffset === 0 ? "Today"
      : dayOffset === -1 ? "Yesterday"
      : dayOffset === 1 ? "Tomorrow"
      : dayOffset < 0 ? `${abs} days ago`
      : `In ${abs} days`;
    const fullDate = d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    return { dateStr, navLabel, fullDate, year: d.getFullYear(), month: d.getMonth(), day: d.getDate() };
  }, [dayOffset]);

  // Flush pending save
  const flush = (overrideSections) => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    if (!dirtyRef.current) return Promise.resolve();
    dirtyRef.current = false;
    const secs = overrideSections || sectionsRef.current;
    const ds = dirtyDateRef.current || dateInfo.dateStr;
    dirtyDateRef.current = null;
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    const payload = {
      date: ds,
      sections: secs,
      vitals: vitalsRef.current,
      shift: shiftRef.current,
      meds: medChecklistRef.current,
      clientId: activeClient.id || "",
    };
    return fetch("/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: abortRef.current.signal,
    }).then(r => { if (r.ok) { setSaveStatus("saved"); setSaveCount(c => c + 1); } else setSaveStatus("error"); })
      .catch(e => { if (e.name !== "AbortError") setSaveStatus("error"); });
  };

  const scheduleSave = () => {
    dirtyRef.current = true;
    dirtyDateRef.current = dateInfo.dateStr;
    setSaveStatus("idle");
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setSaveStatus("saving");
      flush();
    }, 1500);
  };

  // Load section names (once)
  useEffect(() => {
    fetch("/api/log-sections").then(r => r.json()).then(data => {
      setSectionNames(data.sections || []);
    }).catch(() => setSectionNames([]));
  }, []);

  // Track which date we last loaded so we know when it's a date change vs a sectionNames change
  const loadedDateRef = useRef(null);

  // Load log when date changes
  useEffect(() => {
    setSaveStatus("idle");
    setUndoStack([]); setRedoStack([]);
    locallyRemovedRef.current = new Set();
  }, [dateInfo.dateStr]);

  // Merge sections with sectionNames whenever either changes
  useEffect(() => {
    const isDateChange = loadedDateRef.current !== dateInfo.dateStr;
    const wasCleared = clearedDatesRef.current.has(dateInfo.dateStr);

    // If this date was just cleared and the POST hasn't confirmed yet,
    // use the in-memory cleared state instead of fetching stale data
    if (wasCleared) {
      if (sectionNames) {
        const removed = locallyRemovedRef.current;
        setSections(sectionNames.filter(name => !removed.has(name)).map(name => ({ name, content: "" })));
      }
      setVitals({...EMPTY_VITALS});
      setShift({start: activeClient.defaultShift?.start || "", end: activeClient.defaultShift?.end || ""});
      setMedChecklist((activeClient.meds || []).map(m => ({...m, configuredId: m.id, times: []})));
      loadedDateRef.current = dateInfo.dateStr;
      dirtyRef.current = false;
      return;
    }

    const ac = new AbortController();
    fetch(`/api/log?date=${dateInfo.dateStr}`, { signal: ac.signal })
      .then(r => r.json())
      .then(data => {
        const loaded = data.sections || [];
        if (sectionNames) {
          const byName = {};
          loaded.forEach(s => { byName[s.name] = s.content; });
          // Only preserve in-progress edits when sectionNames changed (not date)
          if (!isDateChange) {
            sectionsRef.current.forEach(s => { if (s.content) byName[s.name] = s.content; });
          }
          const removed = locallyRemovedRef.current;
          const merged = sectionNames.filter(name => !removed.has(name)).map(name => ({ name, content: byName[name] || "" }));
          loaded.forEach(s => { if (!sectionNames.includes(s.name) && !removed.has(s.name)) merged.push(s); });
          setSections(merged);
        } else {
          setSections(loaded);
        }

        // Load structured fields (only on date change)
        if (isDateChange) {
          setVitals(data.vitals || {...EMPTY_VITALS});
          setShift(data.shift?.start ? data.shift : {start: activeClient.defaultShift?.start || "", end: activeClient.defaultShift?.end || ""});
          // Seed med checklist from saved data, or from client config if no saved meds
          if (data.meds && data.meds.length > 0) {
            setMedChecklist(data.meds);
          } else {
            setMedChecklist((activeClient.meds || []).map(m => ({...m, configuredId: m.id, times: []})));
          }
        }

        loadedDateRef.current = dateInfo.dateStr;
        dirtyRef.current = false;
      })
      .catch(e => { if (e.name !== "AbortError") console.error("Failed to load log:", e); });
    return () => ac.abort();
  }, [dateInfo.dateStr, sectionNames]);

  useEffect(() => () => { flush(); }, []);

  const handleBack = () => { flush(); onBack(); };
  const prevDay = () => { flush(); setDayOffset(o => o - 1); };
  const nextDay = () => { flush(); setDayOffset(o => o + 1); };
  const goToday = () => { if (dayOffset !== 0) { flush(); setDayOffset(0); } };
  const jumpToDate = (y, m, d) => {
    flush();
    const target = new Date(y, m, d);
    const today = new Date(); today.setHours(0,0,0,0);
    const diff = Math.round((target - today) / 86400000);
    setDayOffset(diff);
  };

  const isToday = dayOffset === 0;

  // Auto-capitalize helper
  const autoCapitalize = (str) => str.replace(/(?:^|\s)\S/g, c => c.toUpperCase());

  // Section content change with undo
  const updateContent = (realIdx, content) => {
    pushUndo({ type: "content", sections: sections.map(s => ({...s})) });
    setSections(prev => prev.map((s, i) => i === realIdx ? { ...s, content } : s));
    scheduleSave();
  };

  // Add section
  const addSection = () => {
    let name = "Notes"; let n = 2;
    while (sectionNames.includes(name)) { name = `Notes ${n}`; n++; }
    const updated = [...sectionNames, name];
    pushUndo({ type: "structure", sections: sections.map(s => ({...s})), names: [...sectionNames] });
    setSectionNames(updated);
    setSections(prev => [...prev, { name, content: "" }]);
    setEditingNewIdx(updated.length - 1);
  };

  // Finalize section name
  const finalizeSectionName = (idx, newName) => {
    const trimmed = autoCapitalize(newName.trim() || "Notes");
    let final = trimmed; let n = 2;
    while (sectionNames.some((name, i) => i !== idx && name === final)) { final = `${trimmed} ${n}`; n++; }
    const oldName = sectionNames[idx];
    const updatedNames = sectionNames.map((name, i) => i === idx ? final : name);
    setSectionNames(updatedNames);
    setSections(prev => prev.map(s => s.name === oldName ? { ...s, name: final } : s));
    setEditingNewIdx(null);
    fetch("/api/log-sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sections: updatedNames }) }).catch(() => {});
    scheduleSave();
  };

  const liveRenameSection = (idx, newName) => {
    const oldName = sectionNames[idx];
    const updatedNames = sectionNames.map((name, i) => i === idx ? newName : name);
    setSectionNames(updatedNames);
    setSections(prev => prev.map(s => s.name === oldName ? { ...s, name: newName } : s));
  };

  // Remove section from current day's log only (trash icon on card)
  const removeSectionFromLog = (name) => {
    pushUndo({ type: "content", sections: sections.map(s => ({...s})), locallyRemoved: new Set(locallyRemovedRef.current) });
    locallyRemovedRef.current.add(name);
    setSections(prev => prev.filter(s => s.name !== name));
    scheduleSave();
  };

  // Remove section from config — affects all future logs (pill "x" button)
  const removeSectionFromConfig = (name) => {
    pushUndo({ type: "structure", sections: sections.map(s => ({...s})), names: [...sectionNames] });
    const updated = sectionNames.filter(n => n !== name);
    setSectionNames(updated);
    // Don't remove from current sections array — just from config
    // The display filter will hide it, but it stays in the saved file
    fetch("/api/log-sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sections: updated }) }).catch(() => {});
  };

  // Undo
  const undo = () => {
    if (undoStack.length === 0) return;
    const snapshot = undoStack[undoStack.length - 1];
    setRedoStack(prev => [...prev, { type: snapshot.type, sections: sections.map(s => ({...s})), names: sectionNames ? [...sectionNames] : null, locallyRemoved: new Set(locallyRemovedRef.current) }]);
    setUndoStack(prev => prev.slice(0, -1));
    setSections(snapshot.sections);
    if (snapshot.locallyRemoved) locallyRemovedRef.current = snapshot.locallyRemoved;
    if (snapshot.names) {
      setSectionNames(snapshot.names);
      fetch("/api/log-sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sections: snapshot.names }) }).catch(() => {});
    }
    scheduleSave();
  };

  // Redo
  const redo = () => {
    if (redoStack.length === 0) return;
    const snapshot = redoStack[redoStack.length - 1];
    setUndoStack(prev => [...prev, { type: snapshot.type, sections: sections.map(s => ({...s})), names: sectionNames ? [...sectionNames] : null, locallyRemoved: new Set(locallyRemovedRef.current) }]);
    setRedoStack(prev => prev.slice(0, -1));
    setSections(snapshot.sections);
    if (snapshot.locallyRemoved) locallyRemovedRef.current = snapshot.locallyRemoved;
    if (snapshot.names) {
      setSectionNames(snapshot.names);
      fetch("/api/log-sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sections: snapshot.names }) }).catch(() => {});
    }
    scheduleSave();
  };

  // Clear all content for the current day
  const clearDay = () => {
    pushUndo({ type: "content", sections: sections.map(s => ({...s})) });
    const clearedSections = sections.map(s => ({ ...s, content: "" }));
    const clearedVitals = {...EMPTY_VITALS};
    const clearedShift = {start: activeClient.defaultShift?.start || "", end: activeClient.defaultShift?.end || ""};
    const clearedMeds = (activeClient.meds || []).map(m => ({...m, configuredId: m.id, times: []}));
    setSections(clearedSections);
    setVitals(clearedVitals);
    setShift(clearedShift);
    setMedChecklist(clearedMeds);
    // Update refs immediately so any pending flush uses cleared data
    sectionsRef.current = clearedSections;
    vitalsRef.current = clearedVitals;
    shiftRef.current = clearedShift;
    medChecklistRef.current = clearedMeds;
    setShowClearConfirm(false);
    // Save immediately — don't debounce, so calendar and navigation see it right away
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    dirtyRef.current = false;
    clearedDatesRef.current.add(dateInfo.dateStr);
    setSaveStatus("saving");
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    fetch("/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: dateInfo.dateStr, sections: clearedSections, vitals: clearedVitals, shift: clearedShift, meds: clearedMeds, clientId: activeClient.id || "" }),
      signal: abortRef.current.signal,
    }).then(r => { if (r.ok) { setSaveStatus("saved"); setSaveCount(c => c + 1); clearedDatesRef.current.delete(dateInfo.dateStr); } else setSaveStatus("error"); })
      .catch(e => { if (e.name !== "AbortError") setSaveStatus("error"); });
  };

  // Vitals/shift/med change helpers
  const updateVital = (key, raw) => {
    const val = raw === "" ? null : Number(raw);
    setVitals(v => ({...v, [key]: isNaN(val) ? v[key] : val}));
    scheduleSave();
  };
  const updateShift = (key, val) => {
    setShift(s => ({...s, [key]: val}));
    scheduleSave();
  };
  const shiftHours = useMemo(() => {
    if (!shift.start || !shift.end) return null;
    const [sh,sm] = shift.start.split(":").map(Number);
    const [eh,em] = shift.end.split(":").map(Number);
    const diff = (eh*60+em) - (sh*60+sm);
    return diff > 0 ? (diff/60).toFixed(1) : null;
  }, [shift]);

  const toggleMed = (idx) => {
    setMedChecklist(prev => prev.map((m,i) => {
      if (i !== idx) return m;
      if (m.times && m.times.length > 0) return {...m, times: m.times.slice(0,-1)};
      const now = new Date().toLocaleTimeString("en-US", {hour:"numeric", minute:"2-digit"}).toLowerCase();
      return {...m, times: [...(m.times||[]), now]};
    }));
    scheduleSave();
  };
  const addOneOffMed = () => {
    if (!newMed.name.trim()) return;
    setMedChecklist(prev => [...prev, {...newMed, configuredId: null, times: []}]);
    setNewMed({name:"",dosage:"",route:"Oral"});
    setShowAddMed(false);
    scheduleSave();
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
      if ((e.metaKey || e.ctrlKey) && (e.key === "y" || (e.key === "z" && e.shiftKey))) { e.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  // Drag reorder
  const handleDragStart = (idx) => { setDragIdx(idx); };
  const handleDragOver = (e, idx) => { e.preventDefault(); setDragOverIdx(idx); };
  const handleDrop = (idx) => {
    if (dragIdx == null || dragIdx === idx) { setDragIdx(null); setDragOverIdx(null); return; }
    pushUndo({ type: "structure", sections: sections.map(s => ({...s})), names: [...sectionNames] });
    const newNames = [...sectionNames];
    const [moved] = newNames.splice(dragIdx, 1);
    newNames.splice(idx, 0, moved);
    const newSections = [...sections];
    const [movedSec] = newSections.splice(dragIdx, 1);
    newSections.splice(idx, 0, movedSec);
    setSectionNames(newNames);
    setSections(newSections);
    setDragIdx(null); setDragOverIdx(null);
    fetch("/api/log-sections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sections: newNames }) }).catch(() => {});
    scheduleSave();
  };

  // Calendar: fetch highlighted days
  const fetchLogDates = async (y, m) => {
    try {
      const r = await fetch(`/api/log-dates?year=${y}&month=${m + 1}`);
      const data = await r.json();
      return data.dates || [];
    } catch { return []; }
  };

  // Filter displayed sections
  // Show sections that are in config OR have content for this day
  const displaySections = sectionNames
    ? sections.filter(s => sectionNames.includes(s.name) || s.content.trim())
    : sections;

  return (
    <Shell config={config} title="Daily Service Log" subtitle={dateInfo.fullDate} onBack={handleBack} emailConfigured={null} onOpenEmailSetup={()=>{}}>
      {showClearConfirm && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.5)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:300,padding:16}}>
          <div style={{background:"white",borderRadius:16,maxWidth:360,width:"100%",overflow:"hidden",boxShadow:"0 8px 48px rgba(0,0,0,0.25)"}}>
            <div style={{background:chrome.titleBar,padding:"16px 22px"}}>
              <div style={{fontSize:11,letterSpacing:3,textTransform:"uppercase",color:"#e0c090",marginBottom:4}}>🗑 Clear Day</div>
              <div style={{fontSize:14,color:chrome.mutedText}}>This will erase all notes for {dateInfo.fullDate}.</div>
            </div>
            <div style={{padding:"18px 22px"}}>
              <div style={{fontSize:14,color:"#4a3028",lineHeight:1.6,marginBottom:16}}>All entries for this day will be cleared. This can be undone.</div>
              <div style={{display:"flex",gap:9}}>
                <button onClick={() => setShowClearConfirm(false)} style={{flex:1,fontSize:14,fontWeight:700,padding:"10px 0",borderRadius:9,border:"1.5px solid #e8ddd8",background:"white",color:"#9a8070",cursor:"pointer"}}>Cancel</button>
                <button onClick={clearDay} style={{flex:1,fontSize:14,fontWeight:700,padding:"10px 0",borderRadius:9,border:"none",background:"#c47070",color:"white",cursor:"pointer"}}>Clear This Day</button>
              </div>
            </div>
          </div>
        </div>
      )}
      <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
        {/* Toolbar */}
        <div style={{background:chrome.toolbar,borderBottom:`1px solid ${chrome.border}`,padding:"7px 20px",display:"flex",alignItems:"center",gap:8,flexShrink:0}}>
          {/* Calendar button */}
          <button ref={calBtnRef} className="bsm" onClick={() => setShowCalendar(!showCalendar)}
            style={{fontSize:15,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:"pointer"}}>📅</button>
          {showCalendar && <CalendarPicker accent={acc} initialYear={dateInfo.year} initialMonth={dateInfo.month}
            selectedDay={{year:dateInfo.year,month:dateInfo.month,day:dateInfo.day}}
            anchorRef={calBtnRef} highlightedDays={fetchLogDates} refreshKey={saveCount} onSelect={jumpToDate} onClose={() => setShowCalendar(false)} />}
          <div style={{display:"flex",alignItems:"center",gap:7}}>
            <button className="bsm" onClick={prevDay} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 12px",cursor:"pointer"}}>‹</button>
            <button className="bsm" onClick={goToday} style={{fontSize:14,color:isToday?acc:chrome.mutedText,fontWeight:isToday?700:500,textAlign:"center",background:"none",border:"none",cursor:"pointer",padding:0,minWidth:80}}>{dateInfo.navLabel}</button>
            <button className="bsm" onClick={nextDay} style={{fontSize:17,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 12px",cursor:"pointer"}}>›</button>
          </div>
          <div style={{flex:1}}/>
          {/* Undo/Redo */}
          <button className="bsm" onClick={undo} disabled={undoStack.length===0} title="Undo (Ctrl+Z)"
            style={{fontSize:15,color:undoStack.length?chrome.mutedText:chrome.border,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:undoStack.length?"pointer":"default"}}>↩</button>
          <button className="bsm" onClick={redo} disabled={redoStack.length===0} title="Redo (Ctrl+Shift+Z)"
            style={{fontSize:15,color:redoStack.length?chrome.mutedText:chrome.border,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:redoStack.length?"pointer":"default"}}>↪</button>
          <button className="bsm" onClick={() => setShowClearConfirm(true)} title="Clear this day's entries"
            style={{fontSize:14,color:chrome.mutedText,background:"none",border:`1px solid ${chrome.border}`,borderRadius:5,padding:"4px 8px",cursor:"pointer",marginLeft:4}}>🗑</button>
          <div style={{width:1,height:18,background:chrome.border}}/>
          <div style={{fontSize:12,color:saveStatus==="saving"?acc:saveStatus==="saved"?"#82ab86":saveStatus==="error"?"#c47070":chrome.mutedText,fontWeight:500,minWidth:60,textAlign:"right"}}>
            {saveStatus==="saving"?"Saving...":saveStatus==="saved"?"Saved":saveStatus==="error"?"Save failed":""}
          </div>
        </div>

        {/* Section pills bar */}
        <div style={{background:"#fdf8f4",borderBottom:"1px solid #e8ddd4",padding:"10px 20px",display:"flex",alignItems:"center",gap:8,flexWrap:"wrap",flexShrink:0}}>
          <span style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",marginRight:4}}>Sections</span>
          {(sectionNames||[]).map((name, idx) => (
            <span key={idx} draggable={editingNewIdx !== idx} onDragStart={() => handleDragStart(idx)} onDragOver={e => handleDragOver(e, idx)} onDrop={() => handleDrop(idx)} onDragEnd={() => { setDragIdx(null); setDragOverIdx(null); }}
              style={{display:"inline-flex",alignItems:"center",gap:4,background:editingNewIdx===idx?"transparent":dragOverIdx===idx?`${acc}15`:"white",border:editingNewIdx===idx?`1px dashed ${acc}`:dragOverIdx===idx?`1px dashed ${acc}`:"1px solid #e8ddd4",borderRadius:12,padding:"4px 10px",fontSize:13,color:"#2c1810",cursor:editingNewIdx===idx?"text":"grab",opacity:dragIdx===idx?0.5:1,transition:"all 0.15s"}}>
              {editingNewIdx === idx ? (
                <input autoFocus value={name}
                  onChange={e => liveRenameSection(idx, e.target.value)}
                  onFocus={e => e.target.select()}
                  onBlur={() => finalizeSectionName(idx, name)}
                  onKeyDown={e => { if (e.key === "Enter") e.target.blur(); }}
                  style={{fontSize:13,border:"none",outline:"none",background:"transparent",width:Math.max(40, name.length * 8 + 10),padding:0,fontFamily:"inherit",color:name.match(/^Notes\s*\d*$/i)?"#b8a898":"#2c1810"}}
                  placeholder="Notes" />
              ) : (<>
                {name}
                <button onClick={e => { e.stopPropagation(); removeSectionFromConfig(name); }}
                  style={{background:"none",border:"none",cursor:"pointer",color:"#c0a898",fontSize:13,padding:0,lineHeight:1}}
                  title="Remove from all future logs">×</button>
              </>)}
            </span>
          ))}
          <button onClick={addSection}
            style={{fontSize:13,color:acc,background:"none",border:`1px dashed ${acc}`,borderRadius:12,padding:"4px 14px",cursor:"pointer",display:"flex",alignItems:"center",gap:4}}>
            + add section
          </button>
        </div>

        {/* Section content area */}
        <div style={{flex:1,overflowY:"auto",padding:"20px 24px",background:"linear-gradient(160deg,#f9f3ee,#f2ebe4)",display:"flex",flexDirection:"column",gap:16}}>

          {/* Patient info card */}
          {activeClient.name && (
            <div style={{background:`linear-gradient(135deg, white, ${tint(acc,0.04)})`,borderRadius:14,border:`1.5px solid ${tint(acc,0.2)}`,padding:"16px 20px",display:"flex",alignItems:"flex-start",gap:14}}>
              <div style={{width:40,height:40,borderRadius:"50%",background:tint(acc,0.12),display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,fontWeight:700,color:acc,flexShrink:0,marginTop:2}}>
                {activeClient.name.charAt(0).toUpperCase()}
              </div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontSize:18,fontWeight:700,color:"#2c1810",fontFamily:"'Playfair Display',serif"}}>{activeClient.name}</div>
                {activeClient.address && (
                  <div style={{fontSize:12,color:"#b0988a",marginTop:2}}>{activeClient.address}</div>
                )}
                {activeClient.objective && (
                  <div style={{fontSize:13,color:"#6a5a4a",lineHeight:1.4,marginTop:6,padding:"8px 12px",background:tint(acc,0.05),borderRadius:8,borderLeft:`3px solid ${tint(acc,0.3)}`}}>
                    <span style={{fontSize:10,letterSpacing:1,textTransform:"uppercase",color:"#9a8070",fontWeight:600,display:"block",marginBottom:3}}>Objective</span>
                    {activeClient.objective}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Shift times */}
          <div style={{background:"white",borderRadius:14,border:"1px solid #e8ddd4",padding:"14px 20px",display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
            <span style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",fontWeight:600}}>Shift</span>
            <input type="time" value={shift.start} onChange={e=>updateShift("start",e.target.value)}
              style={{fontSize:15,border:"1.5px solid #e8ddd8",borderRadius:8,padding:"6px 10px",color:"#2c1810",outline:"none",background:"#fdfaf8"}}/>
            <span style={{color:"#b0988a",fontSize:13}}>to</span>
            <input type="time" value={shift.end} onChange={e=>updateShift("end",e.target.value)}
              style={{fontSize:15,border:"1.5px solid #e8ddd8",borderRadius:8,padding:"6px 10px",color:"#2c1810",outline:"none",background:"#fdfaf8"}}/>
            {shiftHours && <span style={{fontSize:14,color:acc,fontWeight:600,marginLeft:4}}>{shiftHours} hrs</span>}
          </div>

          {/* Vitals card */}
          {activeVitals.length>0&&<div style={{background:"white",borderRadius:14,border:"1px solid #e8ddd4",padding:"14px 20px"}}>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12}}>
              <div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",fontWeight:600}}>Vitals</div>
              <button onClick={()=>setShowVitalsModal(true)} title="Edit vitals metrics" style={{fontSize:11,color:acc,background:"none",border:`1px solid ${acc}40`,borderRadius:6,padding:"2px 8px",cursor:"pointer"}}>Edit</button>
            </div>
            <div style={{display:"grid",gridTemplateColumns:`repeat(auto-fit, minmax(${activeVitals.length<=4?130:105}px, 1fr))`,gap:12}}>
              {activeVitals.map(({key,label,unit,step})=>(<div key={key} style={{textAlign:"center",position:"relative"}} onMouseEnter={()=>setHoverVital(key)} onMouseLeave={()=>setHoverVital(null)}>
                {hoverVital===key&&<button onClick={()=>removeVitalFromConfig(key)} title={`Remove ${label}`} style={{position:"absolute",top:-6,right:-4,width:18,height:18,borderRadius:"50%",border:"none",background:"#e8ddd4",color:"#8a7060",fontSize:12,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",zIndex:1,lineHeight:1}}>×</button>}
                <input type="number" step={step||"1"} value={vitals[key]===null?"":vitals[key]} onChange={e=>updateVital(key,e.target.value)} placeholder="—"
                  style={{width:"100%",fontSize:26,fontWeight:700,textAlign:"center",border:"1.5px solid #e8ddd8",borderRadius:10,padding:"10px 4px",color:"#2c1810",outline:"none",background:"#fdfaf8",boxSizing:"border-box"}}/>
                <div style={{fontSize:11,color:"#9a8070",marginTop:4,fontWeight:500}}>{label} <span style={{color:"#b0a090"}}>{unit}</span></div>
              </div>))}
            </div>
          </div>}
          {showVitalsModal&&<div style={{position:"fixed",inset:0,background:"rgba(44,24,16,0.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:500,padding:16}} onClick={e=>{if(e.target===e.currentTarget)setShowVitalsModal(false);}}>
            <div style={{background:"white",borderRadius:16,width:380,maxWidth:"90vw",overflow:"hidden",boxShadow:"0 12px 60px rgba(0,0,0,0.25)"}}>
              <div style={{background:chrome.titleBar,padding:"16px 20px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                <div><div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:acc}}>Configure</div><div style={{fontSize:16,fontWeight:700,color:"#f0e0d0"}}>Vitals Metrics</div></div>
                <button onClick={()=>setShowVitalsModal(false)} style={{color:"#a08878",background:"none",border:"none",fontSize:18,cursor:"pointer"}}>✕</button></div>
              <div style={{padding:"16px 20px",maxHeight:400,overflowY:"auto"}}>
                {/* Enabled vitals — draggable to reorder */}
                {enabledVitals.map((key,idx)=>{const v=ALL_VITALS.find(x=>x.key===key);if(!v)return null;return(
                  <div key={key} draggable onDragStart={()=>setVitalDragIdx(idx)} onDragOver={e=>{e.preventDefault();setVitalDragOverIdx(idx);}}
                    onDrop={()=>{if(vitalDragIdx!=null&&vitalDragIdx!==idx){const arr=[...enabledVitals];const[moved]=arr.splice(vitalDragIdx,1);arr.splice(idx,0,moved);saveEnabledVitals(arr);}setVitalDragIdx(null);setVitalDragOverIdx(null);}}
                    onDragEnd={()=>{setVitalDragIdx(null);setVitalDragOverIdx(null);}}
                    style={{display:"flex",alignItems:"center",gap:10,padding:"10px 0",borderBottom:vitalDragOverIdx===idx?`2px solid ${acc}`:"1px solid #f0e8e0",opacity:vitalDragIdx===idx?0.4:1,cursor:"grab"}}>
                    <span style={{color:"#c0b8b0",fontSize:14,userSelect:"none",flexShrink:0}}>⠿</span>
                    <input type="checkbox" checked onChange={()=>saveEnabledVitals(enabledVitals.filter(k=>k!==key))} style={{width:18,height:18,accentColor:acc,cursor:"pointer",flexShrink:0}}/>
                    <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600,color:"#2c1810"}}>{v.label}</div><div style={{fontSize:12,color:"#b0988a"}}>{v.unit}</div></div>
                  </div>);})}
                {/* Disabled vitals — can be added */}
                {ALL_VITALS.filter(v=>!enabledVitals.includes(v.key)).map(v=>(
                  <label key={v.key} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 0",borderBottom:"1px solid #f0e8e0",cursor:"pointer",opacity:0.6}}>
                    <span style={{width:14,flexShrink:0}}/>
                    <input type="checkbox" checked={false} onChange={()=>saveEnabledVitals([...enabledVitals,v.key])} style={{width:18,height:18,accentColor:acc,cursor:"pointer",flexShrink:0}}/>
                    <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600,color:"#2c1810"}}>{v.label}</div><div style={{fontSize:12,color:"#b0988a"}}>{v.unit}</div></div>
                  </label>))}
              </div>
              <div style={{padding:"12px 20px",borderTop:"1px solid #f0e8e0"}}><button onClick={()=>setShowVitalsModal(false)} style={{width:"100%",fontSize:14,fontWeight:700,padding:"10px 0",borderRadius:9,border:"none",background:acc,color:"white",cursor:"pointer"}}>Done</button></div>
            </div></div>}

          {/* Medications checklist */}
          {(medChecklist.length > 0 || (activeClient.meds||[]).length > 0) && (
            <div style={{background:"white",borderRadius:14,border:"1px solid #e8ddd4",padding:"14px 20px"}}>
              <div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",color:"#9a8070",fontWeight:600,marginBottom:10}}>Medications</div>
              {medChecklist.map((med, idx) => {
                const isChecked = med.times && med.times.length > 0;
                return (
                  <div key={med.configuredId || `oneoff-${idx}`}
                    style={{display:"flex",alignItems:"center",gap:10,padding:"8px 0",borderBottom:idx < medChecklist.length-1 ? "1px solid #f0e8e0" : "none"}}>
                    <button onClick={()=>toggleMed(idx)}
                      style={{width:24,height:24,borderRadius:6,border:`2px solid ${isChecked?acc:"#d0c0b8"}`,background:isChecked?acc:"white",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,transition:"all 0.15s"}}>
                      {isChecked && <span style={{color:"white",fontSize:14,fontWeight:700}}>✓</span>}
                    </button>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{fontSize:14,fontWeight:600,color:"#2c1810"}}>{med.name}</div>
                      <div style={{fontSize:12,color:"#b0988a"}}>
                        {[med.dosage, med.frequency, med.route].filter(Boolean).join(" · ")}
                        {!med.configuredId && <span style={{color:acc,marginLeft:6,fontStyle:"italic"}}>one-time</span>}
                      </div>
                    </div>
                    {isChecked && (
                      <div style={{fontSize:12,color:acc,fontWeight:500,flexShrink:0}}>
                        {med.times.join(", ")}
                      </div>
                    )}
                  </div>
                );
              })}
              {/* Add one-off med */}
              {showAddMed ? (
                <div style={{marginTop:10,display:"flex",gap:6,alignItems:"flex-end",flexWrap:"wrap"}}>
                  <input value={newMed.name} onChange={e=>setNewMed(m=>({...m,name:e.target.value}))} placeholder="Med name"
                    style={{flex:2,fontSize:13,border:"1.5px solid #e8ddd8",borderRadius:6,padding:"6px 8px",outline:"none",minWidth:80}}/>
                  <input value={newMed.dosage} onChange={e=>setNewMed(m=>({...m,dosage:e.target.value}))} placeholder="Dosage"
                    style={{flex:1,fontSize:13,border:"1.5px solid #e8ddd8",borderRadius:6,padding:"6px 8px",outline:"none",minWidth:60}}/>
                  <button onClick={addOneOffMed} style={{fontSize:12,fontWeight:600,color:"white",background:acc,border:"none",borderRadius:6,padding:"7px 12px",cursor:"pointer"}}>Add</button>
                  <button onClick={()=>setShowAddMed(false)} style={{fontSize:12,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>Cancel</button>
                </div>
              ) : (
                <button onClick={()=>setShowAddMed(true)}
                  style={{marginTop:8,fontSize:12,color:acc,background:"none",border:"none",cursor:"pointer",padding:0}}>
                  + Add one-time medication
                </button>
              )}
            </div>
          )}

          {/* Text sections */}
          {displaySections.length === 0 && sectionNames !== null && medChecklist.length === 0 && !activeClient.name && (
            <div style={{textAlign:"center",padding:40,color:"#9a8070",fontSize:15,fontFamily:"sans-serif"}}>
              Click <strong style={{color:acc}}>+ add section</strong> above to start documenting.
            </div>
          )}
          {displaySections.map((s) => {
            const realIdx = sections.findIndex(sec => sec.name === s.name);
            const nameIdx = sectionNames.indexOf(s.name);
            const isEditing = editingNewIdx === nameIdx;
            return (
              <div key={s.name}
                draggable={!isEditing} onDragStart={() => handleDragStart(nameIdx)} onDragOver={e => handleDragOver(e, nameIdx)} onDrop={() => handleDrop(nameIdx)} onDragEnd={() => { setDragIdx(null); setDragOverIdx(null); }}
                style={{background:"white",borderRadius:14,border:dragOverIdx===nameIdx?`2px dashed ${acc}`:"1px solid #e8ddd4",boxShadow:"0 2px 10px rgba(0,0,0,0.04)",overflow:"hidden",opacity:dragIdx===nameIdx?0.5:1,transition:"border 0.15s"}}>
                <div style={{padding:"14px 20px 8px",borderBottom:"1px solid #f0e8e0",display:"flex",alignItems:"center",gap:8}}>
                  {isEditing ? (
                    <input value={s.name}
                      onChange={e => liveRenameSection(nameIdx, e.target.value)}
                      onFocus={e => e.target.select()}
                      onBlur={() => finalizeSectionName(nameIdx, s.name)}
                      onKeyDown={e => { if (e.key === "Enter") e.target.blur(); }}
                      placeholder="Notes"
                      style={{fontFamily:"'Playfair Display',serif",fontSize:18,fontWeight:700,color:s.name.match(/^Notes\s*\d*$/i)?"#b8a898":"#2c1810",border:"none",outline:"none",background:"transparent",flex:1,padding:0}} />
                  ) : (
                    <div style={{fontFamily:"'Playfair Display',serif",fontSize:18,fontWeight:700,color:"#2c1810",flex:1}}>{s.name}</div>
                  )}
                  {/* Delete button */}
                  <button onClick={() => removeSectionFromLog(s.name)} title={`Remove ${s.name} from this day`}
                    style={{background:"none",border:"none",cursor:"pointer",color:"#c0a898",fontSize:16,padding:"2px 4px",borderRadius:4,flexShrink:0,transition:"color 0.15s"}}
                    onMouseEnter={e => e.currentTarget.style.color="#c47070"}
                    onMouseLeave={e => e.currentTarget.style.color="#c0a898"}>🗑</button>
                  {/* Drag handle */}
                  <span style={{cursor:"grab",color:"#c0b8b0",fontSize:14,userSelect:"none",flexShrink:0}} title="Drag to reorder">⠿</span>
                </div>
                <AutoTextarea
                  timestamped
                  value={s.content}
                  onChange={e => updateContent(realIdx, e.target.value)}
                  placeholder={`Enter ${(s.name || "notes").toLowerCase()} here...`}
                  style={{
                    width:"100%",border:"none",outline:"none",
                    padding:"12px 20px 16px",fontSize:15,fontFamily:"sans-serif",
                    color:"#2c1810",background:"transparent",minHeight:80,
                    lineHeight:1.6,boxSizing:"border-box",
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </Shell>
  );
}

// ── REPORT A PROBLEM ─────────────────────────────────────────────────────
function ReportModal({ onClose }) {
  const [description, setDescription] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null); // {success} or {error, report}

  const handleSubmit = async () => {
    if (!description.trim()) return;
    setSending(true);
    try {
      const resp = await fetch('/api/report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({description: description.trim()})
      });
      const data = await resp.json();
      if (data.success) {
        setResult({success: true});
      } else if (data.report) {
        // Email failed — offer clipboard fallback
        setResult({error: data.error, report: data.report});
      } else {
        setResult({error: data.error || 'Failed to send report'});
      }
    } catch (e) {
      setResult({error: 'Could not reach server'});
    } finally {
      setSending(false);
    }
  };

  const handleCopy = () => {
    if (result?.report) {
      navigator.clipboard.writeText(result.report).then(() => {
        setResult(prev => ({...prev, copied: true}));
      });
    }
  };

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.5)",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center",fontFamily:"sans-serif"}}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{background:"#faf6f2",borderRadius:12,padding:28,width:420,maxWidth:"90vw",maxHeight:"80vh",overflow:"auto",boxShadow:"0 8px 32px rgba(0,0,0,0.2)"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
          <div style={{fontSize:16,fontWeight:700,color:"#2c1810"}}>Report a Problem</div>
          <button onClick={onClose} style={{fontSize:14,color:"#9a8070",background:"none",border:"none",cursor:"pointer"}}>✕</button>
        </div>

        {!result ? (
          <>
            <div style={{fontSize:13,color:"#7a6a5a",lineHeight:1.6,marginBottom:14}}>
              Share any issues, ideas, or suggestions — we'd love to hear from you. Diagnostic logs and system info will be included automatically.
            </div>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder={"How can we improve the app?\n\nExamples:\n• The app froze when I clicked Submit\n• A button isn't working the way I expected\n• It would be helpful if I could..."}
              maxLength={5000}
              style={{width:"100%",minHeight:140,padding:12,borderRadius:8,border:"1px solid #d8c8b8",background:"#fff",fontSize:13,color:"#2c1810",resize:"vertical",fontFamily:"inherit",lineHeight:1.5,boxSizing:"border-box"}}
            />
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginTop:12}}>
              <span style={{fontSize:11,color:"#b0a090"}}>{description.length}/5000</span>
              <button
                onClick={handleSubmit}
                disabled={!description.trim() || sending}
                style={{fontSize:13,fontWeight:700,color:"#fff",background:!description.trim()||sending?"#c0b0a0":"#7a6050",border:"none",borderRadius:8,padding:"8px 20px",cursor:!description.trim()||sending?"default":"pointer",opacity:!description.trim()?0.6:1}}>
                {sending ? "Sending..." : "Send Report"}
              </button>
            </div>
          </>
        ) : result.success ? (
          <div style={{textAlign:"center",padding:"20px 0"}}>
            <div style={{fontSize:28,marginBottom:10}}>✓</div>
            <div style={{fontSize:14,color:"#4a7a50",fontWeight:600,marginBottom:6}}>Report sent</div>
            <div style={{fontSize:13,color:"#7a6a5a"}}>Thank you — this helps us improve the app.</div>
            <button onClick={onClose}
              style={{marginTop:16,fontSize:13,color:"#7a6050",background:"none",border:`1px solid #d8c8b8`,borderRadius:8,padding:"6px 16px",cursor:"pointer"}}>
              Close
            </button>
          </div>
        ) : (
          <div>
            <div style={{fontSize:13,color:"#8a5020",marginBottom:10}}>
              Could not send automatically{result.error ? `: ${result.error}` : ''}
            </div>
            {result.report && (
              <>
                <div style={{fontSize:13,color:"#7a6a5a",marginBottom:8}}>
                  Copy the report below and email it to us manually:
                </div>
                <textarea
                  readOnly
                  value={result.report}
                  style={{width:"100%",minHeight:100,padding:10,borderRadius:8,border:"1px solid #d8c8b8",background:"#f5f0eb",fontSize:11,color:"#5a4a3a",fontFamily:"monospace",resize:"vertical",boxSizing:"border-box"}}
                />
                <button onClick={handleCopy}
                  style={{marginTop:8,fontSize:13,fontWeight:600,color:"#fff",background:result.copied?"#6a9a70":"#7a6050",border:"none",borderRadius:8,padding:"8px 16px",cursor:"pointer",width:"100%"}}>
                  {result.copied ? "Copied!" : "Copy to Clipboard"}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ReportButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      title="Report a problem or share feedback"
      style={{position:"fixed",bottom:12,left:12,zIndex:9000,fontSize:12,color:"#a09080",background:"rgba(46,34,24,0.75)",border:"1px solid rgba(74,56,40,0.5)",borderRadius:20,padding:"5px 12px",cursor:"pointer",display:"flex",alignItems:"center",gap:5,backdropFilter:"blur(4px)",transition:"opacity 0.15s",opacity:0.6}}
      onMouseEnter={e=>e.currentTarget.style.opacity="1"}
      onMouseLeave={e=>e.currentTarget.style.opacity="0.6"}>
      <span style={{fontSize:13}}>💬</span> Feedback
    </button>
  );
}

export default function App() {
  const [config, setConfig] = useState(defaultConfig);
  const [page,   setPage]   = useState("menu");
  const [scrollToFolder, setScrollToFolder] = useState(false);
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState(null);
  const [serverDead, setServerDead] = useState(false);
  const [showEmailSetup, setShowEmailSetup] = useState(false);
  const [emailConfigured, setEmailConfigured] = useState(null); // null=unknown, true/false
  const [emailSetupCount, setEmailSetupCount] = useState(0); // increments on successful setup
  const [updateInfo, setUpdateInfo] = useState(null); // {downloadUrl, latestVersion}
  const [updating, setUpdating] = useState(false);
  const [updateComplete, setUpdateComplete] = useState(false);
  const [showReport, setShowReport] = useState(false);

  // Show "Update complete" toast if redirected after update
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('updated')) {
      setUpdateComplete(true);
      window.history.replaceState({}, '', '/');
      setTimeout(() => setUpdateComplete(false), 5000);
    }
  }, []);

  // Heartbeat: ping the server every 3s so it knows we're alive.
  // On close: beacon tells server to shut down after 5s.
  // On reload: page remounts, immediate ping cancels the shutdown.
  // On tab focus: immediate ping keeps server alive after background throttling.
  // If server stops responding, show a "server disconnected" overlay.
  useEffect(() => {
    let failures = 0;
    const ping = () => fetch("/api/heartbeat", { method: "POST" })
      .then(() => { failures = 0; setServerDead(false); })
      .catch(() => { failures++; if (failures >= 3) setServerDead(true); });
    ping();
    const interval = setInterval(ping, 3000);
    const onVisible = () => { if (!document.hidden) ping(); };
    const onUnload = () => navigator.sendBeacon("/api/shutdown");
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("beforeunload", onUnload);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("beforeunload", onUnload);
    };
  }, []);

  // Check for updates on mount
  useEffect(() => {
    fetch('/api/check-update').then(r=>r.json()).then(data => {
      if (data.updateAvailable) setUpdateInfo(data);
    }).catch(()=>{});
  }, []);

  // Fetch config and email status on app mount
  useEffect(() => {
    const abortController = new AbortController();

    // Fetch both config and email status in parallel
    Promise.all([
      fetch('/api/config', { signal: abortController.signal }).then(r => r.ok ? r.json() : Promise.reject(new Error('Config fetch failed'))),
      fetch('/api/email-status', { signal: abortController.signal }).then(r => r.ok ? r.json() : null).catch(() => null)
    ])
      .then(([configData, emailStatus]) => {
        if (configData.rate != null) configData.rate = Number(configData.rate) || 0;
        setConfig({ ...defaultConfig, ...configData });
        const configured = emailStatus ? emailStatus.configured : null;
        setEmailConfigured(configured);
        setLoading(false);
      })
      .catch(error => {
        if (error.name === 'AbortError') return;
        console.error('Config fetch failed, using defaults:', error);
        setConfigError(error.message);
        setLoading(false);
      });
    return () => abortController.abort();
  }, []);

  const handleNav = (dest) => {
    if (dest==="profile-folder") { setScrollToFolder(true); setPage("profile"); }
    else { setScrollToFolder(false); setPage(dest); }
  };

  const handleEmailSetupDone = () => {
    setShowEmailSetup(false);
    setEmailConfigured(true);
    setEmailSetupCount(c => c + 1);
  };

  const handleEmailSetupSkip = () => {
    setShowEmailSetup(false);
    // emailConfigured stays false — pill button remains visible
  };

  const openEmailSetup = () => setShowEmailSetup(true);

  // Shared props for email setup state
  const emailProps = { emailConfigured, onOpenEmailSetup: openEmailSetup, emailSetupCount };

  // Show loading state while fetching config
  if (loading) {
    return (
      <div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#f9f3ee",flexDirection:"column",gap:16}}>
        <div style={{fontSize:33}}>⏳</div>
        <div style={{fontFamily:"'Playfair Display',serif",fontSize:19,color:"#2c1810"}}>Loading your profile...</div>
      </div>
    );
  }

  // Show error banner if config fetch failed (but continue with defaults)
  const ErrorBanner = configError ? (
    <div style={{position:"fixed",top:0,left:0,right:0,background:"#fef3e8",borderBottom:"2px solid #e8b060",padding:"10px 20px",zIndex:1000,display:"flex",alignItems:"center",gap:10}}>
      <span style={{fontSize:17}}>⚠️</span>
      <div style={{flex:1}}>
        <div style={{fontSize:13,fontWeight:700,color:"#8a5010"}}>Welcome! Fill in your profile to get started.</div>
        <div style={{fontSize:12,color:"#a87020"}}>Head to Edit Profile to add your info.</div>
      </div>
      <button onClick={()=>setConfigError(null)} aria-label="Dismiss error" style={{fontSize:12,color:"#8a5010",background:"none",border:"none",cursor:"pointer"}}>✕</button>
    </div>
  ) : null;

  const doSelfUpdate = async () => {
    setUpdating(true);
    try {
      const resp = await fetch('/api/self-update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({downloadUrl: updateInfo.downloadUrl})
      });
      if (!resp.ok) {
        const err = await resp.json().catch(()=>({}));
        alert(err.error || 'Update failed');
        setUpdating(false);
      }
    } catch {
      // Server exited (expected) — poll until the new server is up, then reload
      const poll = () => {
        fetch('/api/heartbeat', {method: 'POST'})
          .then(() => { window.location.href = '/?updated=1'; })
          .catch(() => setTimeout(poll, 2000));
      };
      setTimeout(poll, 8000);
    }
  };
  const UpdateBanner = updateComplete ? (
    <div style={{position:"fixed",bottom:0,left:0,right:0,background:"#eef9ee",borderTop:"2px solid #6ac86a",padding:"10px 20px",zIndex:1000,display:"flex",alignItems:"center",gap:10}}>
      <span style={{fontSize:17}}>✅</span>
      <div style={{flex:1,fontSize:13,color:"#1a4a2a"}}>Update complete.</div>
    </div>
  ) : updateInfo ? (
    <div style={{position:"fixed",bottom:0,left:0,right:0,background:"#eef6ff",borderTop:"2px solid #6aa8d8",padding:"10px 20px",zIndex:1000,display:"flex",alignItems:"center",gap:10}}>
      <span style={{fontSize:17}}>🔄</span>
      <div style={{flex:1,fontSize:13,color:"#1a4a6a"}}>{updating ? "Installing update — this page will reload automatically." : "A new version of Invoice Builder is available."}</div>
      {!updating && <button onClick={doSelfUpdate}
        style={{fontSize:13,fontWeight:700,color:"#fff",background:"#4a90c8",border:"none",borderRadius:6,padding:"6px 14px",cursor:"pointer"}}>Install Update</button>}
      {updating && <span style={{fontSize:13,color:"#4a80a8"}}>Please wait...</span>}
      {!updating && <button onClick={()=>setUpdateInfo(null)} style={{fontSize:12,color:"#4a80a8",background:"none",border:"none",cursor:"pointer"}}>✕</button>}
    </div>
  ) : null;

  const emailModal = showEmailSetup ? <EmailSetupModal onDone={handleEmailSetupDone} onSkip={handleEmailSetupSkip} isEditing={emailConfigured === true}/> : null;

  if (serverDead) return (
    <div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#f5f0eb",fontFamily:"sans-serif"}}>
      <div style={{textAlign:"center",padding:40}}>
        <div style={{fontSize:40,marginBottom:16}}>😴</div>
        <div style={{fontSize:18,fontWeight:600,color:"#2c1810",marginBottom:8}}>Invoice Builder has stopped</div>
        <div style={{fontSize:14,color:"#9a8070",marginBottom:24}}>The app was closed due to inactivity. Reopen it from your desktop.</div>
      </div>
    </div>
  );

  const reportUI = <><ReportButton onClick={()=>setShowReport(true)}/>{showReport && <ReportModal onClose={()=>setShowReport(false)}/>}</>;

  if (page==="log")     return <>{ErrorBanner}{UpdateBanner}{emailModal}{reportUI}<DailyLogPage config={config} onBack={()=>setPage("menu")}/></>;
  if (page==="weekly")  return <>{ErrorBanner}{UpdateBanner}{emailModal}{reportUI}<WeeklyPage  config={config} onBack={()=>setPage("menu")} {...emailProps}/></>;
  if (page==="monthly") return <>{ErrorBanner}{UpdateBanner}{emailModal}{reportUI}<MonthlyPage config={config} onBack={()=>setPage("menu")} {...emailProps}/></>;
  if (page==="profile") return <>{ErrorBanner}{UpdateBanner}{emailModal}{reportUI}<ProfilePage config={config} onSave={setConfig} onBack={()=>setPage("menu")} scrollToFolder={scrollToFolder} {...emailProps}/></>;
  return <>{ErrorBanner}{UpdateBanner}{emailModal}{reportUI}<LandingPage config={config} onNav={handleNav} {...emailProps}/></>;
}
