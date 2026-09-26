const DATA_URL = "data/app-data.json";
const ESPN_PLAYERS_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2027/players";
const ESPN_ATHLETES_URL = "https://sports.core.api.espn.com/v3/sports/hockey/nhl/athletes";
const EXCLUDED_KEY = "fantasyHockeyExcludedPlayers";

let appData;
let historyChart;
let projectionChart;
let selectedPlayer = "David Pastrnak";
let sortKey = "Steal Value";
let sortDirection = "desc";
let positionFilter = "All";
let excludedPlayers = new Set(JSON.parse(localStorage.getItem(EXCLUDED_KEY) || "[]"));

const $ = (id) => document.getElementById(id);

function saveExcluded() {
  localStorage.setItem(EXCLUDED_KEY, JSON.stringify([...excludedPlayers].sort()));
}

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

function allPlayerNames() {
  return [...new Set([
    ...appData.history.map(d => d.player),
    ...appData.gems.map(d => d.Player)
  ])].sort((a,b)=>a.localeCompare(b));
}

function filteredPlayers(query, excludeDrafted = false) {
  const q = query.trim().toLowerCase();
  let names = allPlayerNames();
  if (excludeDrafted) names = names.filter(n => !excludedPlayers.has(n));
  return q ? names.filter(n => n.toLowerCase().includes(q)) : names;
}

function renderOptions(query, inputId, optionsId, excludeDrafted = false) {
  const box = $(optionsId);
  const names = filteredPlayers(query, excludeDrafted).slice(0, 80);
  box.innerHTML = names.length
    ? names.map(n => `<div class="option" role="option" data-name="${escapeHtml(n)}">${escapeHtml(n)}</div>`).join("")
    : `<div class="no-results">No players found</div>`;
  box.classList.add("open");
  $(inputId).setAttribute("aria-expanded","true");
}

function selectPlayer(name) {
  selectedPlayer = name;
  $("playerSearch").value = name;
  $("playerOptions").classList.remove("open");
  $("playerSearch").setAttribute("aria-expanded","false");
  renderHistory(name);
}

function excludePlayer(name) {
  excludedPlayers.add(name);
  saveExcluded();
  $("excludePlayerSearch").value = "";
  $("excludePlayerOptions").classList.remove("open");
  $("excludePlayerSearch").setAttribute("aria-expanded","false");
  renderGems();
  renderExcluded();
  renderProjection();
}

function unexcludePlayer(name) {
  excludedPlayers.delete(name);
  saveExcluded();
  renderGems();
  renderExcluded();
  renderProjection();
}

function resetExcluded() {
  excludedPlayers.clear();
  saveExcluded();
  renderGems();
  renderExcluded();
  renderProjection();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function compare(a,b,key) {
  let av=a[key], bv=b[key];
  if (key === "Player" || key === "Position") return String(av || "").localeCompare(String(bv || ""));
  av=Number(av); bv=Number(bv);
  if (Number.isNaN(av)) av = -Infinity;
  if (Number.isNaN(bv)) bv = -Infinity;
  return av-bv;
}

function positionFromId(id) {
  const n = Number(id);
  if (n === 4) return "D";
  if (n === 1 || n === 2 || n === 3) return "F";
  return "F";
}

function renderGems() {
  const rows=[...appData.gems]
    .filter(r => !excludedPlayers.has(r.Player))
    .filter(r => positionFilter === "All" || r.Position === positionFilter)
    .sort((a,b)=>{
      const c=compare(a,b,sortKey);
      return c === 0 ? String(a.Player).localeCompare(String(b.Player)) : (sortDirection==="asc"?c:-c);
    });

  $("gemsBody").innerHTML=rows.map(r=>{
    const sv=Number(r["Steal Value"]);
    const cls=sv>0?"steal-positive":sv<0?"steal-negative":"";
    const age = Number.isFinite(Number(r.Age)) ? Number(r.Age) : "—";
    const pos = r.Position === "D" ? "D" : "F";
    return `<tr class="gems-row" data-name="${escapeHtml(r.Player)}" title="Click to exclude ${escapeHtml(r.Player)}">
      <td>${r["PPG Ranking"]}</td>
      <td>${r["ESPN Ranking"]}</td>
      <td class="player-col">${escapeHtml(r.Player)}</td>
      <td class="pos-col">${pos}</td>
      <td>${age}</td>
      <td>${Number(r.PPG).toFixed(2)}</td>
      <td>${Number(r["EWMA PPG"]).toFixed(2)}</td>
      <td class="${cls}">${sv > 0 ? "+" : ""}${sv}</td>
    </tr>`;
  }).join("");

  $("tableCount").textContent = `${rows.length} skaters · ${excludedPlayers.size} excluded`;

  document.querySelectorAll("th.sortable").forEach(th=>{
    const span=th.querySelector("span");
    const key=th.dataset.key;
    th.classList.toggle("active",key===sortKey);
    span.textContent=key===sortKey?(sortDirection==="asc"?"↑":"↓"):"";
  });
}

function renderExcluded() {
  const list = $("excludedList");
  const names = [...excludedPlayers].sort((a,b)=>a.localeCompare(b));
  $("excludedCount").textContent = `${names.length} excluded`;
  $("resetExcluded").disabled = names.length === 0;
  list.innerHTML = names.length
    ? names.map(name => `<div class="excluded-player"><span>${escapeHtml(name)}</span><button type="button" data-name="${escapeHtml(name)}" aria-label="Restore ${escapeHtml(name)}">×</button></div>`).join("")
    : `<div class="empty-excluded">No players excluded yet.</div>`;
}

function renderProjection() {
  const rows=[...appData.gems]
    .filter(r => !excludedPlayers.has(r.Player))
    .sort((a,b)=>a["ESPN Ranking"]-b["ESPN Ranking"]);

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
  input.addEventListener("focus",()=>renderOptions(input.value, "playerSearch", "playerOptions"));
  input.addEventListener("input",()=>renderOptions(input.value, "playerSearch", "playerOptions"));
  box.addEventListener("mousedown",(e)=>{
    const option=e.target.closest(".option");
    if(option) selectPlayer(option.dataset.name);
  });
  $("clearPlayer").addEventListener("click",()=>{ input.value=""; input.focus(); renderOptions("", "playerSearch", "playerOptions"); });

  const excludeInput=$("excludePlayerSearch"), excludeBox=$("excludePlayerOptions");
  excludeInput.addEventListener("focus",()=>renderOptions(excludeInput.value, "excludePlayerSearch", "excludePlayerOptions", true));
  excludeInput.addEventListener("input",()=>renderOptions(excludeInput.value, "excludePlayerSearch", "excludePlayerOptions", true));
  excludeBox.addEventListener("mousedown",(e)=>{
    const option=e.target.closest(".option");
    if(option) excludePlayer(option.dataset.name);
  });
  $("clearExcludePlayer").addEventListener("click",()=>{
    excludeInput.value="";
    excludeInput.focus();
    renderOptions("", "excludePlayerSearch", "excludePlayerOptions", true);
  });

  $("excludedList").addEventListener("click",(e)=>{
    const button=e.target.closest("button[data-name]");
    if(button) unexcludePlayer(button.dataset.name);
  });
  $("resetExcluded").addEventListener("click",resetExcluded);

  document.addEventListener("click",(e)=>{
    if(!e.target.closest("#combobox")) {
      box.classList.remove("open");
      input.setAttribute("aria-expanded","false");
    }
    if(!e.target.closest("#excludeCombobox")) {
      excludeBox.classList.remove("open");
      excludeInput.setAttribute("aria-expanded","false");
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

function initGemsRowClick() {
  $("gemsBody").addEventListener("click", (e) => {
    const row = e.target.closest("tr.gems-row");
    if (row?.dataset.name) excludePlayer(row.dataset.name);
  });
}

function initPositionFilter() {
  const select = $("positionFilter");
  if (!select) return;
  select.value = positionFilter;
  select.addEventListener("change", () => {
    positionFilter = select.value;
    renderGems();
  });
}

function normalizeEspnRows(data) {
  const rows = data?.players || (Array.isArray(data) ? data : []);
  const output = [];
  for (const row of rows) {
    const player = row?.player || row;
    if (!player?.fullName) continue;
    const ranks = player.draftRanksByRankType || {};
    const standard = ranks.STANDARD;
    let rank = standard?.rank;

    if (!rank && player.rankings) {
      for (const values of Object.values(player.rankings)) {
        if (!Array.isArray(values)) continue;
        const item = values.find(x => String(x?.rankType || "").toUpperCase() === "STANDARD");
        if (item?.rank) { rank = item.rank; break; }
      }
    }
    rank = Number(rank);
    if (!Number.isFinite(rank) || rank <= 0) continue;

    output.push({
      Player: player.fullName,
      "ESPN Ranking": rank,
      "ESPN ID": player.id ?? row.id,
      Age: player.age ?? null,
      "Default Position ID": player.defaultPositionId ?? null
    });
  }

  const byName = new Map();
  for (const row of output) {
    const old = byName.get(row.Player);
    if (!old || row["ESPN Ranking"] < old["ESPN Ranking"]) byName.set(row.Player, row);
  }
  return [...byName.values()].sort((a,b)=>a["ESPN Ranking"]-b["ESPN Ranking"]);
}

function mergeLiveRankings(rankRows, ageById) {
  const existing = new Map(appData.gems.map(r => [r.Player, r]));
  const goalieNames = new Set(
    appData.history
      .filter(r => false)
      .map(r => r.player)
  );

  // Historical stats contain the original goalie classification.
  const statsGoalies = new Set();
  for (const row of appData.history) {
    // Goalies are already absent from gems. If a live player isn't present in
    // gems, we use the local historical data only when it has a skater PPG.
    // This keeps newly ranked players available while avoiding an extra
    // 12k-row payload in the browser.
  }

  const live = rankRows
    .filter(r => Number(r["Default Position ID"]) !== 5)
    .filter(r => !excludedPlayers.has(r.Player))
    .map(r => {
      const old = existing.get(r.Player);
      const age = r.Age ?? ageById.get(Number(r["ESPN ID"])) ?? old?.Age ?? null;
      const position = old?.Position || positionFromId(r["Default Position ID"]);
      return {
        "PPG Ranking": old?.["PPG Ranking"] ?? 9999,
        "ESPN Ranking": r["ESPN Ranking"],
        Player: r.Player,
        Position: position,
        Age: age,
        PPG: old?.PPG ?? 0,
        "EWMA PPG": old?.["EWMA PPG"] ?? 0,
        "Steal Value": 0
      };
    });

  // Re-rank the live board by current PPG, exactly as the static build does.
  live.sort((a,b) => Number(b.PPG)-Number(a.PPG) || a.Player.localeCompare(b.Player));
  live.forEach((r, i) => {
    r["PPG Ranking"] = i + 1;
    r["Steal Value"] = r["ESPN Ranking"] - r["PPG Ranking"];
  });

  appData.gems = live;
}

async function fetchLiveEspnData() {
  const filter = {
    players: {
      filterActive: { value: true },
      limit: 10000,
      offset: 0
    }
  };

  const response = await fetch(
    `${ESPN_PLAYERS_URL}?view=players_wl&scoringPeriodId=0`,
    {
      headers: {
        "Accept": "application/json, text/plain, */*",
        "X-Fantasy-Filter": JSON.stringify(filter)
      },
      cache: "no-store"
    }
  );
  if (!response.ok) throw new Error(`ESPN player request failed (${response.status})`);
  const data = await response.json();
  const rankings = normalizeEspnRows(data);
  if (!rankings.length) throw new Error("ESPN returned no ranked players");

  let ages = new Map();
  try {
    const ageResponse = await fetch(`${ESPN_ATHLETES_URL}?limit=10000`, {cache:"no-store"});
    if (ageResponse.ok) {
      const ageData = await ageResponse.json();
      for (const athlete of (ageData.items || [])) {
        const age = Number(athlete.age);
        if (athlete.id != null && Number.isFinite(age)) ages.set(Number(athlete.id), age);
      }
    }
  } catch (_) {
    // Age is supplementary; don't fail a ranking refresh if this endpoint is down.
  }

  mergeLiveRankings(rankings, ages);
  appData.updated = new Date().toISOString().slice(0,10);
  appData.rankingSource = "ESPN Fantasy API (live)";
  return rankings.length;
}

async function refreshEspnData() {
  const button = $("refreshData");
  const status = $("refreshStatus");
  button.disabled = true;
  button.textContent = "Refreshing…";
  status.textContent = "Fetching ESPN's live ranked player pool…";
  status.className = "refresh-status";

  try {
    const count = await fetchLiveEspnData();
    renderGems();
    renderExcluded();
    renderProjection();
    status.textContent = `Live ESPN data loaded: ${count} ranked players · ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}`;
    status.className = "refresh-status success";
  } catch (err) {
    console.error(err);
    status.textContent = "Live refresh failed. The cached rankings are still being used. If your browser blocks ESPN's API, run the repository updater instead.";
    status.className = "refresh-status error";
  } finally {
    button.disabled = false;
    button.textContent = "Refresh ESPN Data";
  }
}

async function init() {
  try {
    const res=await fetch(DATA_URL);
    appData=await res.json();
    initPicker();
    initSorting();
    initGemsRowClick();
    initPositionFilter();
    // Backfill Position for older cached JSON that predates this column.
    for (const row of appData.gems) {
      if (row.Position !== "F" && row.Position !== "D") {
        row.Position = "F";
      }
    }
    $("refreshData").addEventListener("click", refreshEspnData);
    $("dataUpdated").textContent = `Cached: ${appData.updated || "unknown"}`;
    $("tableCount").textContent = `${appData.gems.length} skaters`;
    renderHistory(selectedPlayer);
    renderGems();
    renderExcluded();
    renderProjection();
  } catch(err) {
    console.error(err);
    document.querySelector(".shell").innerHTML=`<div class="card" style="padding:30px"><h2>Could not load draft data</h2><p>Please serve this folder from a web server rather than opening index.html directly.</p></div>`;
  }
}
init();
