import json
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")


def latest_run():
    # run folders are named by timestamp (start with "2"), so max() =

    return max(p for p in RAW.iterdir() if p.name.startswith("2"))


if __name__ == "__main__":
    run = latest_run()
    bootstrap = json.loads((run / "bootstrap.json").read_text())
    fixtures = json.loads((run / "fixtures.json").read_text())

    pd.DataFrame(bootstrap["elements"]).info(verbose=True)  # players
    pd.DataFrame(bootstrap["teams"]).info()
    pd.DataFrame(fixtures).info()