const $ = (id) => document.getElementById(id);
const fmt = (n) => new Intl.NumberFormat('zh-CN').format(n || 0);
let configCache = null;

async function api(path, options={}) {
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || data.message || `HTTP ${res.status}`);
  return data;
}

function renderBars(id, rows, prefix='') {
  const el = $(id);
  if (!rows || rows.length === 0) { el.className='bars empty'; el.textContent='暂无数据'; return; }
  el.className='bars'; const max = Math.max(...rows.map(x => x.count));
  el.innerHTML = rows.map(row => `<div class="bar-row"><div class="bar-label" title="${escapeHtml(prefix + row.label)}">${escapeHtml(prefix + row.label)}</div><div class="track"><div class="fill" style="width:${Math.max(2,row.count/max*100)}%"></div></div><div class="bar-value">${fmt(row.count)}</div></div>`).join('');
}
function escapeHtml(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function loadDashboard() {
  const d = await api('/api/dashboard');
  $('captureCount').textContent=fmt(d.capture_count); $('fileCount').textContent=fmt(d.file_count); $('rawCount').textContent=fmt(d.raw_count); $('editedCount').textContent=fmt(d.edited_count);
  $('editRate').textContent=`修图率 ${d.capture_count ? (d.edited_count/d.capture_count*100).toFixed(1) : '0.0'}%`;
  renderBars('themes', d.themes); renderBars('cameras', d.cameras); renderBars('lenses', d.lenses); renderBars('roles', d.roles); renderBars('apertures', d.apertures, 'F'); renderBars('iso', d.iso, 'ISO '); renderBars('focalLengths', d.focal_lengths); renderBars('shutters', d.shutters);
}

async function loadPhotos() {
  const d = await api('/api/photos?limit=150'); const body=$('photosBody');
  body.innerHTML = d.items.length ? d.items.map(p => `<tr><td>${escapeHtml(p.filename)}<small>${escapeHtml(p.relative_path)}</small></td><td>${escapeHtml(p.theme || '—')}</td><td><span class="role">${escapeHtml(p.role)}</span></td><td>${escapeHtml(p.shot_at || '—')}</td><td>${escapeHtml(p.camera_model || '—')}<small>${escapeHtml(p.lens_model || '')}</small></td><td>${p.focal_length ? escapeHtml(p.focal_length+'mm') : '—'} / ${p.aperture ? 'F'+escapeHtml(p.aperture) : '—'}<small>${escapeHtml(p.exposure_time || '—')} · ISO ${escapeHtml(p.iso || '—')}</small></td></tr>`).join('') : '<tr><td colspan="6" class="muted">尚未扫描任何照片。</td></tr>';
}

async function loadSettings() {
  configCache = await api('/api/settings');
  $('librariesInput').value=(configCache.libraries||[]).map(x => `${x.name || ''} | ${x.path}`).join('\n');
  $('editedKeywords').value=(configCache.edited_dir_keywords||[]).join(', '); $('jpegKeywords').value=(configCache.jpeg_dir_keywords||[]).join(', '); $('rawKeywords').value=(configCache.raw_dir_keywords||[]).join(', ');
}
function splitKeywords(v){return v.split(/[,，]/).map(x=>x.trim()).filter(Boolean)}
async function saveSettings() {
  const libraries=$('librariesInput').value.split('\n').map(x=>x.trim()).filter(Boolean).map(line=>{const i=line.indexOf('|'); if(i<0)return {name:line.split('/').pop()||'照片库',path:line,enabled:true}; return {name:line.slice(0,i).trim(),path:line.slice(i+1).trim(),enabled:true}}).filter(x=>x.path);
  const next={...configCache,libraries,edited_dir_keywords:splitKeywords($('editedKeywords').value),jpeg_dir_keywords:splitKeywords($('jpegKeywords').value),raw_dir_keywords:splitKeywords($('rawKeywords').value)};
  await api('/api/settings',{method:'POST',body:JSON.stringify(next)}); configCache=next; alert('设置已保存。');
}

async function scan() {
  $('scanBtn').disabled=true;
  try { await api('/api/scan',{method:'POST',body:'{}'}); await pollScan(); } catch(e){ alert(e.message); $('scanBtn').disabled=false; }
}
async function pollScan(){
  const s=await api('/api/scan/status'); $('scanState').textContent=s.running?'正在扫描…':(s.error?`扫描错误：${s.error}`:''); $('scanBtn').disabled=!!s.running;
  if(s.running){setTimeout(pollScan,1200)}else{await Promise.all([loadDashboard(),loadPhotos()])}
}

function switchPage(name){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active')); document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===name)); $(`${name}Page`).classList.add('active'); $('pageTitle').textContent={dashboard:'摄影总览',photos:'照片索引',settings:'设置'}[name]; if(name==='photos')loadPhotos(); if(name==='settings')loadSettings();}
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>switchPage(b.dataset.page))); $('scanBtn').addEventListener('click',scan); $('refreshPhotos').addEventListener('click',loadPhotos); $('saveSettings').addEventListener('click',saveSettings);
(async()=>{try{await api('/api/health');$('healthDot').classList.add('ok');$('healthText').textContent='服务正常';await Promise.all([loadDashboard(),loadSettings(),pollScan()])}catch(e){$('healthText').textContent='连接失败';console.error(e)}})();
