const API = "/api";
let soilChart, fertilityChart;
const $ = id => document.getElementById(id);

document.addEventListener("DOMContentLoaded", async () => {
  bindAuth();
  bindUI();
  await checkAuth();
});

function bindAuth() {
  document.querySelectorAll(".tab").forEach(btn => btn.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    btn.classList.add("active");
    $("loginForm").classList.toggle("hidden", btn.dataset.auth !== "login");
    $("signupForm").classList.toggle("hidden", btn.dataset.auth !== "signup");
    $("authMsg").textContent = "";
  });
  $("loginForm").onsubmit = e => authSubmit(e, "/auth/login", {
    email: $("loginEmail").value, password: $("loginPassword").value
  });
  $("signupForm").onsubmit = e => authSubmit(e, "/auth/signup", {
    name: $("signupName").value, email: $("signupEmail").value, password: $("signupPassword").value
  });
}
async function authSubmit(e, endpoint, body) {
  e.preventDefault();
  const r = await fetch(API + endpoint, {method:"POST", credentials:"include", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const d = await r.json();
  $("authMsg").textContent = d.success ? "Success." : (d.error || "Something went wrong.");
  if (d.success) showApp(d.user);
}
async function checkAuth() {
  const d = await fetch(API + "/auth/me", {credentials:"include"}).then(r=>r.json());
  if (d.authenticated) showApp(d.user);
}
function showApp(user) {
  $("authView").classList.add("hidden"); $("appView").classList.remove("hidden");
  $("userName").textContent = user.name;
  loadAll();
}
function bindUI() {
  document.querySelectorAll(".nav").forEach(btn => btn.onclick = () => {
    document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".section").forEach(x=>x.classList.remove("active"));
    $(btn.dataset.section).classList.add("active");
  });
  $("logoutBtn").onclick = async () => { await fetch(API+"/auth/logout",{method:"POST",credentials:"include"}); location.reload(); };
  $("themeBtn").onclick = () => {
    document.documentElement.classList.toggle("light");
    localStorage.theme = document.documentElement.classList.contains("light") ? "light" : "dark";
  };
  if(localStorage.theme==="light") document.documentElement.classList.add("light");
  $("locateBtn").onclick = setLocation;
  $("weatherBtn").onclick = loadWeather;
  $("cropBtn").onclick = loadCrops;
}
async function loadAll() {
  await Promise.all([loadLocation(), loadStatus(), loadLatest(), loadAnalytics(), loadHistory(), loadWeather(), loadCrops()]);
  setInterval(loadLatest, 2000);
  setInterval(loadAnalytics, 7000);
  setInterval(loadHistory, 10000);
  setInterval(loadWeather, 60000);
}
async function get(path) { const r=await fetch(API+path,{credentials:"include"}); return r.json(); }
async function loadLocation() {
  const d=await get("/location");
  if(d.location) $("locationText").textContent = `${d.location.latitude.toFixed(4)}, ${d.location.longitude.toFixed(4)}`;
}
function setLocation() {
  if(!navigator.geolocation) return alert("Your browser does not provide location.");
  $("locationText").textContent = "Requesting location…";
  navigator.geolocation.getCurrentPosition(async pos=>{
    const body={latitude:pos.coords.latitude,longitude:pos.coords.longitude,source:"browser geolocation"};
    const r=await fetch(API+"/location",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json();
    $("locationText").textContent = d.success ? `${body.latitude.toFixed(4)}, ${body.longitude.toFixed(4)}` : d.error;
  }, err => $("locationText").textContent = "Location permission denied.");
}
async function loadStatus() {
  const d=await get("/status");
  $("arduinoText").textContent=d.arduino_connected?"Connected":"Disconnected";
  $("arduinoDot").classList.toggle("online",d.arduino_connected);
  $("shapText").textContent=d.shap_available?"Ready":"Unavailable";
  $("shapDot").classList.toggle("online",d.shap_available);
  $("limeText").textContent=d.lime_available?"Ready":"Unavailable";
  $("limeDot").classList.toggle("online",d.lime_available);
  $("sideStatus").textContent=d.arduino_connected?"Arduino connected":"Waiting for Arduino";
  $("sideDot").classList.toggle("online",d.arduino_connected);
}
async function loadLatest() {
  const d=await get("/latest");
  const r=d.reading, p=d.prediction;
  if(!r) { $("dataNotice").textContent=d.error || "Waiting for real Arduino data."; $("dataNotice").className="notice"; return; }
  $("dataNotice").textContent=d.error || "Live real-time reading received.";
  $("phValue").textContent=r.ph.toFixed(2); $("moistureValue").textContent=r.moisture.toFixed(1)+"%";
  $("nitrogenValue").textContent=r.nitrogen.toFixed(1); $("cecValue").textContent=r.cec.toFixed(1);
  if(p) {
    $("fertilityValue").textContent=p.fertility; $("confidenceBadge").textContent=(p.confidence*100).toFixed(1)+"%";
    $("lgbResult").textContent=p.lgb_prediction; $("catResult").textContent=p.cat_prediction;
    $("lgbConf").textContent=(p.lgb_confidence*100).toFixed(1)+"%"; $("catConf").textContent=(p.cat_confidence*100).toFixed(1)+"%";
    $("agreement").textContent=p.model_agreement?"✓ Models agree":"⚠ Models disagree — ensemble uses higher confidence";
  }
  $("lastUpdate").textContent=d.timestamp ? new Date(d.timestamp).toLocaleString() : "—";
  renderExplain(d.explanation);
  loadCrops();
}
function renderExplain(ex) {
  $("shapList").innerHTML=(ex?.shap||[]).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).map(x=>`<div class="explain-row"><b>${x.feature}</b><div class="bar"><i style="width:${Math.min(100,Math.abs(x.value)*30)}%"></i></div><span>${x.value.toFixed(4)}</span></div>`).join("") || '<div class="empty">SHAP is waiting for a valid explanation.</div>';
  $("limeList").innerHTML=(ex?.lime||[]).map(x=>`<div class="lime-item"><b>${escapeHtml(x.feature)}</b><span>${x.weight.toFixed(4)}</span></div>`).join("") || '<div class="empty">LIME is waiting for a valid explanation.</div>';
}
async function loadAnalytics() {
  const d=await get("/analytics");
  $("totalPredictions").textContent=d.total_predictions;
  $("avgConfidence").textContent=d.average_confidence==null?"—":(d.average_confidence*100).toFixed(1)+"%";
  $("agreementRate").textContent=d.model_agreement_rate==null?"—":d.model_agreement_rate.toFixed(1)+"%";
  const h=await get("/history");
  const labels=h.slice().reverse().map(x=>new Date(x.timestamp).toLocaleTimeString());
  if(soilChart) soilChart.destroy();
  soilChart=new Chart($("soilChart"),{type:"line",data:{labels,datasets:[
    {label:"pH",data:h.slice().reverse().map(x=>x.ph),tension:.3},
    {label:"Moisture",data:h.slice().reverse().map(x=>x.moisture),tension:.3},
    {label:"Nitrogen",data:h.slice().reverse().map(x=>x.nitrogen),tension:.3},
    {label:"CEC",data:h.slice().reverse().map(x=>x.cec),tension:.3}
  ]},options:{responsive:true,maintainAspectRatio:false}});
  if(fertilityChart) fertilityChart.destroy();
  fertilityChart=new Chart($("fertilityChart"),{type:"doughnut",data:{labels:d.fertility_distribution.map(x=>x.fertility),datasets:[{data:d.fertility_distribution.map(x=>x.count)}]},options:{responsive:true,maintainAspectRatio:false}});
}
async function loadHistory() {
  const h=await get("/history");
  $("historyBody").innerHTML=h.map(x=>`<tr><td>${new Date(x.timestamp).toLocaleString()}</td><td>${x.ph.toFixed(2)}</td><td>${x.moisture.toFixed(1)}%</td><td>${x.nitrogen.toFixed(1)}</td><td>${x.cec.toFixed(1)}</td><td><span class="tag ${x.fertility.toLowerCase()}">${x.fertility}</span></td><td>${(x.confidence*100).toFixed(1)}%</td></tr>`).join("") || '<tr><td colspan="7" class="empty">No real predictions recorded yet.</td></tr>';
}
async function loadWeather() {
  const d=await get("/weather");
  if(!d.success) return;
  const c=d.current||{};
  $("weatherTemp").textContent=(c.temperature_2m??"—")+" °C";
  $("weatherHum").textContent=(c.relative_humidity_2m??"—")+" %";
  $("weatherRain").textContent=(c.precipitation??"—")+" mm";
  $("weatherWind").textContent=(c.wind_speed_10m??"—")+" km/h";
}
async function loadCrops() {
  const d=await get("/crop-recommendations");
  if(!d.success) { $("cropCards").innerHTML=`<div class="empty">${escapeHtml(d.error||"Waiting for real soil data.")}</div>`; return; }
  $("cropCards").innerHTML=d.recommendations.map((x,i)=>`<article class="crop-card"><span>#${i+1}</span><h3>${x.crop}</h3><div class="score">${x.score}/5</div><p>${x.reason}</p></article>`).join("");
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));}
