# WorkspaceAlberta Web UI (Python)

This is a lightweight Flask app that walks users through tool selection, problem description, and previewing the generator command.

## Quick start

```bash
cd frontend
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## Notes

- The UI reads tools from `../generator/catalog.json`.
- Selections are stored in a local session cookie.
- The preview step shows the Python generator command and lets you download a markdown summary.
