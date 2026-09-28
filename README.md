# Pilsner fantasy helper

Private 16-team Yahoo salary-cap pad for Pilsner Fantasy. **12 H2H cats**, **$200**, **10 seats**. It does not open Yahoo and it does not bid.

| Page | URL | What it is |
| --- | --- | --- |
| Helper | http://127.0.0.1:5340/helper | Live-night input pad: tap a name, then Sold or Me |
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

Stay is the median of Yahoo list + published AAV, never below list. Stretch is the high. Room heat moves Stay only after two hammers in the same price tier.
