# Pilsner fantasy helper

Private pad for **3. Pilsner Fantasy Liga**: 16-team Yahoo salary-cap, **12 H2H cats**, **$200** default cap, **10 seats**. It does not open Yahoo and it does not bid. Draft dollars are your auction cap ($160–$240), not a payment. Third league has no dynasty this year.

| Page | URL | What it is |
| --- | --- | --- |
| Helper | http://127.0.0.1:5340/helper | Live-night input pad: Sold / Me, plus Keep / Locked for dynasty |
| Mock | http://127.0.0.1:5340/draft | Practice auction with clocks and bots |
| Lab | http://127.0.0.1:5340/lab | Batch rooms. Not a forecast |

## Run it

Python 3.9+ with pandas. On this Mac, Homebrew `python3` often lacks pandas — use Xcode’s interpreter if install fails.

```bash
python3 -m pip install -r requirements.txt
python3 src/draft_server.py
```

Then open **http://127.0.0.1:5340/helper**.

On this machine:

```bash
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pip install -r requirements.txt
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 src/draft_server.py
/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -q
```

Helper, mock, and lab keep separate session files under `data/`. Those files stay local and are not in git.

Stay is the median of Yahoo list + published AAV, never below list. Stretch is the high. Room heat moves Stay only after two hammers in the same price tier. Type your draft-dollar number from the Pilsner table if it is not $200. Keep / Locked log dynasty names at Yahoo list and do not move heat.
