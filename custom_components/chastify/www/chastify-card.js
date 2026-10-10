class ChastifyCard extends HTMLElement {
  setConfig(config) { this._config = config || {}; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }
  getCardSize() { return 5; }
  _find(...names) {
    if (!this._hass?.states) return null;
    const wanted = names.map(n => n.toLowerCase().replaceAll(" ", "_"));
    // Explicit entity overrides let users disambiguate when other integrations
    // expose similarly named entities.
    for (const key of names) {
      const configured = this._config?.entities?.[key] || this._config?.entities?.[key.toLowerCase().replaceAll(" ", "_")];
      if (configured && this._hass.states[configured]) return this._hass.states[configured];
    }
    const all = Object.values(this._hass.states);
    const matches = all.filter(e => {
      const id = e.entity_id.toLowerCase();
      const name = String(e.attributes?.friendly_name || "").toLowerCase().replaceAll(" ", "_");
      return wanted.some(n => id.endsWith("_" + n) || name.endsWith(n));
    });
    // Prefer this integration's historical IDs and entities attached to the
    // integration's "Session" device. Entity IDs do not necessarily contain
    // the integration domain, so requiring "chastify" here hides valid entities.
    const preferred = matches.find(e => {
      const id = e.entity_id.toLowerCase();
      const domain = id.split(".")[0];
      return id.includes("chastify") || id.startsWith(domain + ".session_");
    });
    if (preferred) return preferred;
    return matches.length === 1 ? matches[0] : null;
  }
  _value(e) { return !e || ["unknown", "unavailable"].includes(e.state) ? "—" : e.state; }
  _escape(value) { return String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch])); }
  _press(e) { if (e) this._hass.callService("button", "press", {entity_id:e.entity_id}); }
  _render() {
    if (!this._hass) return;
    const values = [
      ["Time locked", this._find("time_locked")],
      ["Time remaining", this._find("time_remaining")],
      ["Task points", this._find("task_points")],
      ["Points remaining", this._find("task_points_remaining")]
    ];
    const locked = this._find("locked"), frozen = this._find("frozen");
    const actions = [["Refresh",this._find("refresh")],["Freeze",this._find("freeze")],["Unfreeze",this._find("unfreeze")],["Hygienic unlock",this._find("unlock")],["Add 1 hour",this._find("add_1_hour")],["Subtract 1 hour",this._find("subtract_1_hour")]].filter(x => x[1]?.entity_id?.startsWith("button."));
    this.innerHTML = '<ha-card><div class="card"><h2>'+ this._escape(this._config.title || "Chastify") +'</h2><div class="pills"><span>Locked: '+this._escape(this._value(locked))+'</span><span>Frozen: '+this._escape(this._value(frozen))+'</span></div><div class="grid">'+values.map(v=>'<div class="tile"><small>'+v[0]+'</small><b>'+this._escape(this._value(v[1]))+'</b></div>').join("")+'</div><div class="actions">'+actions.map((v,i)=>'<button data-i="'+i+'">'+v[0]+'</button>').join("")+'</div><small class="note">Actions remain subject to Chastify permissions.</small></div></ha-card><style>:host{display:block}ha-card{overflow:hidden;border-radius:20px}.card{padding:16px;color:var(--primary-text-color)}h2{margin:0 0 12px;font-size:20px}.pills{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}.pills span,.tile{background:var(--secondary-background-color);border-radius:12px;padding:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}.tile{display:grid;gap:6px;min-width:0}.tile small,.note{color:var(--secondary-text-color)}.tile b{font-size:16px;overflow-wrap:anywhere}.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:8px;margin-top:12px}button{border:0;border-radius:12px;min-height:44px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;font-weight:600;cursor:pointer}.note{display:block;margin-top:12px}</style>';
    this.querySelectorAll("button").forEach(el => el.onclick = () => {
      const action = actions[Number(el.dataset.i)];
      if (!action) return;
      const consequential = new Set(["Freeze", "Unfreeze", "Hygienic unlock", "Add 1 hour", "Subtract 1 hour"]);
      if (consequential.has(action[0]) && !window.confirm(`Confirm Chastify action: ${action[0]}?`)) return;
      this._press(action[1]);
    });
  }
}
customElements.define("chastify-card", ChastifyCard);
window.customCards = window.customCards || [];
window.customCards.push({type:"chastify-card",name:"Chastify Card",description:"Responsive Chastify session status and controls.",preview:true,getEntitySuggestion:(hass,id)=>id.toLowerCase().includes("chastify")?{config:{type:"custom:chastify-card"}}:null});
