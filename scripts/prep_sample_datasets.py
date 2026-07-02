"""Generate train.csv for sample datasets from sklearn — no download needed."""
from pathlib import Path
import pandas as pd
from sklearn.datasets import load_breast_cancer, load_wine, fetch_california_housing

datasets = [
    ("breast_cancer", load_breast_cancer),
    ("wine",          load_wine),
]

for name, loader in datasets:
    data = loader(as_frame=True)
    df   = data.frame.rename(columns={"target": "target"})
    out  = Path(f"dataset/{name}")
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "train.csv", index=False)
    print(f"  wrote {out}/train.csv  ({df.shape})")

# regression example
data = fetch_california_housing(as_frame=True)
df   = data.frame
out  = Path("dataset/california_housing")
out.mkdir(parents=True, exist_ok=True)
df.to_csv(out / "train.csv", index=False)
print(f"  wrote {out}/train.csv  ({df.shape})")
