import { LitElement, html, css } from "https://unpkg.com/lit@3.1.2/index.js?module";

const styles = css`
  :host {
    --lemon: #ffd54a;
    --lemon-dark: #e6a700;
    --bg: var(--card-background-color, #1c1c1c);
    --fg: var(--primary-text-color, #e1e1e1);
    --muted: var(--secondary-text-color, #9a9a9a);
    --track: var(--divider-color, #333);
  }
  ha-card {
    background: var(--bg);
    color: var(--fg);
    border-radius: 14px;
    padding: 16px;
    box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.4));
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
  }
  ha-card.down {
    border: 1px solid #c0392b;
    opacity: .85;
  }
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .title { display: flex; align-items: center; gap: 10px; }
  .lemon { font-size: 28px; }
  .h-title { font-weight: 600; font-size: 16px; }
  .h-sub { color: var(--muted); font-size: 12px; }
  .refresh {
    background: transparent; border: 1px solid var(--track);
    color: var(--fg); border-radius: 8px; width: 34px; height: 34px;
    font-size: 18px; cursor: pointer;
  }
  .refresh:hover { border-color: var(--lemon); color: var(--lemon); }

  .bars { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; margin-bottom: 14px; }
  .bar-top { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
  .track { height: 7px; background: var(--track); border-radius: 6px; overflow: hidden; }
  .fill { height: 100%; background: linear-gradient(90deg, var(--lemon), var(--lemon-dark)); border-radius: 6px; transition: width .4s ease; }
  .fill.gpu { background: linear-gradient(90deg, #5ad1ff, #2c8fe0); }

  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
  .metric {
    background: rgba(255,255,255,.04); border-radius: 10px; padding: 8px 6px;
    text-align: center; display: flex; flex-direction: column; gap: 1px;
  }
  .m-val { font-size: 18px; font-weight: 700; }
  .m-unit { font-size: 10px; color: var(--muted); }
  .m-label { font-size: 10px; color: var(--muted); }

  .models-title { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
  li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
  li.empty { color: var(--muted); font-style: italic; }
  .m-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .m-dev { color: var(--muted); font-size: 11px; }
  .chip {
    font-size: 10px; padding: 1px 7px; border-radius: 20px;
    background: rgba(255,213,74,.15); color: var(--lemon); text-transform: capitalize;
  }
`;

const BAR_KEYS = [
  { key: "cpu_percent", unit: "%", label: "CPU" },
  { key: "gpu_percent", unit: "%", label: "GPU" },
  { key: "npu_percent", unit: "%", label: "NPU" },
  { key: "memory_gb", unit: "GiB", label: "RAM" },
  { key: "vram_gb", unit: "GiB", label: "VRAM" },
];

const METRIC_KEYS = [
  { key: "ttft_avg", unit: "s", label: "TTFT medio" },
  { key: "tps_avg", unit: "tok/s", label: "Tokens/s" },
  { key: "last_input_tokens", unit: "", label: "Tokens in" },
  { key: "last_output_tokens", unit: "", label: "Tokens out" },
];

class LemonadeCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      config: { attribute: false },
      _error: { state: true },
    };
  }

  static getStubConfig(hass) {
    const cand = Object.keys(hass.states).filter((e) =>
      e.startsWith("sensor.") && e.includes("lemonade")
    );
    const find = (s) => cand.find((e) => e.includes(s)) || "";
    return {
      entities: {
        server_version: find("version"),
        model_loaded: find("model_loaded"),
        loaded_models_count: find("loaded_models_count"),
        cpu_percent: find("cpu_percent"),
        memory_gb: find("memory_gb"),
        gpu_percent: find("gpu_percent"),
        vram_gb: find("vram_gb"),
        npu_percent: find("npu_percent"),
        ttft_avg: find("ttft_avg"),
        tps_avg: find("tps_avg"),
        last_input_tokens: find("last_input_tokens"),
        last_output_tokens: find("last_output_tokens"),
      },
    };
  }

  setConfig(config) {
    if (!config || !config.entities) {
      throw new Error("Debes definir 'entities' en la configuración de la tarjeta.");
    }
    this.config = config;
  }

  get _entities() {
    return this.config.entities || {};
  }

  _state(key) {
    const id = this._entities[key];
    const s = id && this.hass.states[id];
    return s ? s : null;
  }

  _num(key) {
    const s = this._state(key);
    if (!s || s.state === "unavailable" || s.state === "unknown") return null;
    const v = parseFloat(s.state);
    return isNaN(v) ? null : v;
  }

  _attr(key, attr) {
    const s = this._state(key);
    return s ? s.attributes[attr] : undefined;
  }

  _refresh() {
    const id = this._entities.server_version;
    if (id) this.hass.callService("homeassistant", "update_entity", { entity_id: id });
  }

  render() {
    if (this._error) return html`<ha-card>${this._error}</ha-card>`;

    const version = this._state("server_version");
    const model = this._state("model_loaded");
    const count = this._num("loaded_models_count");

    const bars = BAR_KEYS.map((b) => {
      const v = this._num(b.key);
      const pct = v == null ? 0 : b.unit === "%" ? v : Math.min(100, (v / 32) * 100);
      return html`
        <div class="bar">
          <div class="bar-top">
            <span>${b.label}</span>
            <span>${v == null ? "—" : v + " " + b.unit}</span>
          </div>
          <div class="track">
            <div class="fill ${b.key.startsWith("gpu") || b.key.startsWith("vram") ? "gpu" : ""}"
                 style="width:${pct}%"></div>
          </div>
        </div>`;
    });

    const metrics = METRIC_KEYS.map(
      (m) => html`
        <div class="metric">
          <span class="m-val">${this._num(m.key) ?? "—"}</span>
          <span class="m-unit">${m.unit}</span>
          <span class="m-label">${m.label}</span>
        </div>`
    );

    const models = this._attr("loaded_models_count", "loaded_models") || [];
    const modelRows = models.length
      ? models.map(
          (m) => html`
            <li>
              <span class="m-name">${m.model_name || "?"}</span>
              <span class="chip ${m.type || ""}">${m.type || "?"}</span>
              <span class="m-dev">${m.device || ""}</span>
            </li>`
        )
      : html`<li class="empty">Sin modelos cargados</li>`;

    const serverDown = !version || version.state === "unavailable";

    return html`
      <ha-card class="${serverDown ? "down" : ""}">
        <div class="header">
          <div class="title">
            <span class="lemon">🍋</span>
            <div>
              <div class="h-title">Lemonade Server</div>
              <div class="h-sub">
                v${version ? version.state : "—"} ·
                ${model ? model.state : "—"}
              </div>
            </div>
          </div>
          <button class="refresh" @click=${this._refresh} title="Refrescar">⟳</button>
        </div>

        <div class="bars">${bars}</div>

        <div class="metrics">${metrics}</div>

        <div class="models">
          <div class="models-title">
            Modelos cargados${count != null ? " (" + count + ")" : ""}
          </div>
          <ul>${modelRows}</ul>
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("lemonade-card", LemonadeCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "lemonade-card",
  name: "Lemonade Server",
  description: "Telemetría y estado de Lemonade Server",
});
