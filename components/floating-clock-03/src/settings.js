const api = window.clockSettings;
const ids = [
  'background', 'shape', 'opacity', 'format', 'solidColor', 'gradientPreset', 'panelDepth',
  'clockSurface', 'dateSurface', 'clockSurfaceColor', 'dateSurfaceColor', 'clockTextEffect', 'dateTextEffect',
  'clockFont', 'clockColor', 'clockSize', 'clockOutlineEnabled', 'clockOutlineColor', 'clockOutlineWidth',
  'dateFont', 'dateColor', 'dateSize', 'dateOutlineEnabled', 'dateOutlineColor', 'dateOutlineWidth',
  'masterSize', 'timeDateGap'
];
const status = document.getElementById('status');
const fontChoices = ['Segoe UI Variable', 'Segoe UI', 'Arial', 'Georgia', 'Verdana', 'Trebuchet MS', 'Courier New', 'Tahoma', 'Times New Roman', 'Consolas', 'Cambria', 'Bahnschrift'];
let rangeTimer;
let masterSizeTimer;
let masterSizeRequest = 0;

function setStatus(message) { status.textContent = message; }
function updateOutput(id, value) {
  const output = document.getElementById(`${id}Value`);
  if (!output) return;
  if (id === 'opacity') output.textContent = `${value}%`;
  else if (id === 'masterSize') {
    const scale = Number(value) / 100;
    output.textContent = `${value}% · ${Math.round(320 * scale)} × ${Math.round(112 * scale)} px`;
  } else if (id === 'timeDateGap') output.textContent = `${value} px`;
  else if (id.toLowerCase().includes('width') || id.toLowerCase().includes('size')) output.textContent = `${value} px`;
}
function updateConditionalFields() {
  const background = document.getElementById('background').value;
  document.getElementById('solidColorField').classList.toggle('visible', background === 'solid');
  document.getElementById('gradientField').classList.toggle('visible', background === 'gradient');
  for (const kind of ['clock', 'date']) {
    const enabled = document.getElementById(`${kind}OutlineEnabled`).checked;
    document.getElementById(`${kind}OutlineFields`).classList.toggle('disabled', !enabled);
  }
}
async function saveControl(id) {
  const control = document.getElementById(id);
  let value = control.type === 'checkbox' ? control.checked : control.type === 'range' ? Number(control.value) : control.value;
  if (id === 'opacity') value /= 100;
  if (id === 'masterSize') {
    const requestId = ++masterSizeRequest;
    const result = await api.setMasterSize(value / 100);
    if (requestId !== masterSizeRequest) return;
    if (result) setStatus(`Master size applied: ${result.windowWidth} × ${result.windowHeight} px.`);
    else setStatus('Could not update clock dimensions.');
    return;
  }
  const ok = await api.savePreference(id, value);
  setStatus(ok ? 'All changes are saved automatically.' : 'Could not save this setting.');
  updateConditionalFields();
}
function populate(prefs) {
  const masterPercent = Math.round((Number.isFinite(Number(prefs.masterScale)) ? Number(prefs.masterScale) : ((Number(prefs.windowWidth) || 320) / 320)) * 100);
  const values = { ...prefs, opacity: Math.round((prefs.opacity ?? 1) * 100), masterSize: masterPercent, timeDateGap: prefs.timeDateGap ?? 12 };
  for (const id of ids) {
    const control = document.getElementById(id);
    if (!control || values[id] === undefined || values[id] === null) continue;
    if (control.type === 'checkbox') control.checked = Boolean(values[id]);
    else control.value = values[id];
    updateOutput(id, control.value);
  }
  updateConditionalFields();
}
function bindTabs() {
  document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab === button));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === `panel-${button.dataset.tab}`));
  }));
}
function bindControls() {
  for (const id of ids) {
    const control = document.getElementById(id);
    control.addEventListener('input', () => {
      updateOutput(id, control.value);
      if (control.type === 'range') {
        if (id === 'masterSize') {
          clearTimeout(masterSizeTimer);
          masterSizeTimer = setTimeout(() => saveControl(id), 100);
        } else {
          clearTimeout(rangeTimer);
          rangeTimer = setTimeout(() => saveControl(id), 140);
        }
      } else if (control.type === 'color') saveControl(id);
    });
    control.addEventListener('change', () => {
      updateOutput(id, control.value);
      if (control.type !== 'range' && control.type !== 'color') saveControl(id);
      else if (control.type === 'range') {
        if (id === 'masterSize') { clearTimeout(masterSizeTimer); saveControl(id); }
        else saveControl(id);
      }
    });
  }
  document.getElementById('chooseWallpaper').addEventListener('click', async () => {
    const ok = await api.chooseWallpaper();
    if (ok) { document.getElementById('background').value = 'wallpaper'; updateConditionalFields(); setStatus('Wallpaper selected.'); }
  });
  document.getElementById('resetDefaults').addEventListener('click', async () => {
    const defaults = await api.resetPreferences();
    populate(defaults);
    setStatus('Default settings and master dimensions restored.');
  });
}
(async () => {
  for (const id of ['clockFont', 'dateFont']) {
    const select = document.getElementById(id);
    fontChoices.forEach(font => { const option = document.createElement('option'); option.value = font; option.textContent = font; select.appendChild(option); });
  }
  bindTabs();
  bindControls();
  populate(await api.getPreferences());
  api.onPreferencesUpdated(populate);
})();
