const DATA_URL = "data/app-data.json";

let appData;
let historyChart;
let projectionChart;
let selectedPlayer = "David Pastrnak";
let sortKey = "Steal Value";
let sortDirection = "desc";

const $ = (id) => document.getElementById(id);

function playerRows(name) {
  return appData.history.filter(d => d.player === name);
}

function renderHistory(name) {
  const rows = playerRows(name);
  const years = appData.years;
  const values = years.map(y => {
    const row = rows.find(r => r.year === y);
    return row ? row.ppg : 0;
  });
  const gps = years.map(y => {
    const row = rows.find(r => r.year === y);
    return row ? row.gp : 0;
  });
  const current = rows.find(r => r.year === years.at(-1));
  $("selectedName").textContent = name;
  $("selectedMeta").textContent = current ? `${current.gp} GP in 2026` : "";
  $("latestPpg").textContent = current && current.ppg ? current.ppg.toFixed(2) : "—";

  if (historyChart) historyChart.destroy();
  historyChart = new Chart($("historyChart"), {
    type: "line",
    data: {
      labels: years.map(String),
      datasets: [{
        data: values,
        borderColor: "#4867f5",
        backgroundColor: "rgba(72,103,245,.10)",
        borderWidth: 2.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: "#fff",
        pointBorderWidth: 2,
        pointBorderColor: "#4867f5",
        tension: .28,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          callbacks: {
            label: (ctx) => `${ctx.parsed.y.toFixed(2)} PPG · ${gps[ctx.dataIndex]} GP`
          }
        }
      },
      scales: {
        x: { grid: { display:false }, border:{display:false}, ticks:{color:"#7a8493"} },
        y: {
          beginAtZero:false,
          grid:{color:"#edf0f4"},
          border:{display:false},
          ticks:{color:"#7a8493", callback:(v)=>Number(v).toFixed(1)}
        }
      }
    }
  });
}

function filteredPlayers(query) {
  const q = query.trim().toLowerCase();
  const names = [...new Set(appData.history.map(d => d.player))].sort((a,b)=>a.localeCompare(b));
  return q ? names.filter(n => n.toLowerCase().includes(q)) : names;
}

function renderOptions(query) {
  const box = $("playerOptions");
  const names = filteredPlayers(query).slice(0, 80);
  box.innerHTML = names.length
    ? names.map(n => `<div class="option" role="option" data-name="${escapeHtml(n)}">${escapeHtml(n)}</div>`).join("")
    : `<div class="no-results">No players found</div>`;
  box.classList.add("open");
  $("playerSearch").setAttribute("aria-expanded","true");
}

function selectPlayer(name) {
  selectedPlayer = name;
  $("playerSearch").value = name;
  $("playerOptions").classList.remove("open");
  $("playerSearch").setAttribute("aria-expanded","false");
  renderHistory(name);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function compare(a,b,key) {
  let av=a[key], bv=b[key];
  if (key === "Player") return String(av).localeCompare(String(bv));
  av=Number(av); bv=Number(bv);
  return av-bv;
}

function renderGems() {
  const rows=[...appData.gems].sort((a,b)=>{
    const c=compare(a,b,sortKey);
    return c === 0 ? String(a.Player).localeCompare(String(b.Player)) : (sortDirection==="asc"?c:-c);
  });
  $("gemsBody").innerHTML=rows.map(r=>{
    const sv=Number(r["Steal Value"]);
    const cls=sv>0?"steal-positive":sv<0?"steal-negative":"";
    return `<tr>
      <td>${r["PPG Ranking"]}</td>
      <td>${r["ESPN Ranking"]}</td>
      <td class="player-col">${escapeHtml(r.Player)}</td>
      <td>${Number(r.PPG).toFixed(2)}</td>
      <td>${Number(r["EWMA PPG"]).toFixed(2)}</td>
      <td class="${cls}">${sv > 0 ? "+" : ""}${sv}</td>
    </tr>`;
  }).join("");

  document.querySelectorAll("th.sortable").forEach(th=>{
    const span=th.querySelector("span");
    const key=th.dataset.key;
    th.classList.toggle("active",key===sortKey);
    span.textContent=key===sortKey?(sortDirection==="asc"?"↑":"↓"):"";
  });
}

function renderProjection() {
  const rows=[...appData.gems].sort((a,b)=>a["ESPN Ranking"]-b["ESPN Ranking"]);
  if(projectionChart) projectionChart.destroy();
  projectionChart=new Chart($("projectionChart"),{
    type:"line",
    data:{
      labels:rows.map(r=>r["ESPN Ranking"]),
      datasets:[{
        label:"PPG",
        data:rows.map(r=>r.PPG),
        borderColor:"#4867f5",
        borderWidth:2,
        pointRadius:0,
        tension:.15
      },{
        label:"EWMA PPG",
        data:rows.map(r=>r["EWMA PPG"]),
        borderColor:"#1f9b72",
        borderWidth:2,
        pointRadius:0,
        tension:.15
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:"index",intersect:false},
      plugins:{
        legend:{position:"top",align:"end",labels:{boxWidth:10,usePointStyle:true}},
        tooltip:{displayColors:false,callbacks:{title:(items)=>`ESPN Rank ${items[0].label}`}}
      },
      scales:{
        x:{title:{display:true,text:"ESPN Ranking",color:"#7a8493"},grid:{display:false},border:{display:false},ticks:{color:"#7a8493",maxTicksLimit:16}},
        y:{title:{display:true,text:"PPG",color:"#7a8493"},grid:{color:"#edf0f4"},border:{display:false},ticks:{color:"#7a8493"}}
      }
    }
  });
}

function initPicker() {
  const input=$("playerSearch"), box=$("playerOptions");
  input.addEventListener("focus",()=>renderOptions(input.value));
  input.addEventListener("input",()=>renderOptions(input.value));
  box.addEventListener("mousedown",(e)=>{
    const option=e.target.closest(".option");
    if(option) selectPlayer(option.dataset.name);
  });
  $("clearPlayer").addEventListener("click",()=>{ input.value=""; input.focus(); renderOptions(""); });
  document.addEventListener("click",(e)=>{
    if(!e.target.closest("#combobox")) {
      box.classList.remove("open");
      input.setAttribute("aria-expanded","false");
    }
  });
}

function initSorting() {
  document.querySelectorAll("th.sortable").forEach(th=>{
    th.addEventListener("click",()=>{
      const key=th.dataset.key;
      if(key===sortKey) sortDirection=sortDirection==="asc"?"desc":"asc";
      else { sortKey=key; sortDirection="asc"; }
      renderGems();
    });
  });
}

async function init() {
  try {
    const res=await fetch(DATA_URL);
    appData=await res.json();
    initPicker();
    initSorting();
    $("tableCount").textContent = `${appData.gems.length} skaters`;
    renderHistory(selectedPlayer);
    renderGems();
    renderProjection();
  } catch(err) {
    console.error(err);
    document.querySelector(".shell").innerHTML=`<div class="card" style="padding:30px"><h2>Could not load draft data</h2><p>Please serve this folder from a web server rather than opening index.html directly.</p></div>`;
  }
}
init();
