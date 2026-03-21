# ZeusOps Dashboard

Real-time monitoring dashboard for the ZeusOps AI agent network.

**GitHub:** https://github.com/tsanford01/zeusops-dashboard

## Primary Dashboard

**`index-tron.html`** — 2D TRON Edition  
Open at: http://localhost:8878/index-tron.html

## Alternate

**`index-3d.html`** — 3D Three.js Edition (requires vendor/ JS files)  
Open at: http://localhost:8878/index-3d.html

## Running

```bash
./start-dashboard.sh    # HTTP file server on :8878
./start-pocketbase.sh   # PocketBase on :8090
python3 grid-server.py  # Agent status API on :8877
```
