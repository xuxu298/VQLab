# qsim virtual-bench GUI (G1)

A thin, **multi-domain** web front-end over the configurator core
(`qsim.configurator.configure`). Pick a domain (QKD link / atomic magnetometer / qubit
processor), then turn its knobs → the simulation, the BOM, the board parameters and the
design-rule checks update together. One generic UI renders any domain (the report shape is
uniform). First step toward the drag-and-drop "virtual quantum bench"; the engine stays
server-side (browser, no install, modest client hardware).

## Run

```bash
pip install flask           # only extra dependency for the GUI
python -m gui.server        # serves http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` and turn the knobs (detector, source, QRNG, distance, gate rate,
modulator extinction ratio, AMZI visibility, channels). The page calls `POST /api/configure`
and renders the feasibility badge, QBER / SKR / link-cost, the SKR-vs-distance + cost figure,
the color-coded design rules, and the Alice/shared/Bob BOM.

## Endpoints

- `GET /` — the single-page UI (`gui/index.html`, vanilla JS, no build step).
- `GET /api/domains` — `[{name, label}, ...]` for the domain dropdown.
- `GET /api/schema/<domain>` — `{schema, defaults}` driving the dynamic knob form.
- `POST /api/configure` — `{domain, knobs}` → `ConfigReport` JSON + a base64 PNG figure.

## Verify the render (headless)

```bash
python -m gui.server &                 # start the server
python -m gui.screenshot               # writes demos/figures/g1_gui.png via Chromium
```

Backend endpoints are covered by `tests/test_gui.py` (Flask test client, no browser needed).

## Scope

This is a **form-based configurator UI** — the first GUI layer. The eventual flagship is a
node-editor where blocks are wired on a canvas; the `DeviceSpec`/scenario data model and this
headless `configure()` core are what that editor will sit on top of.
