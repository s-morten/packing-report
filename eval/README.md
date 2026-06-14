# eval

Self-contained model evaluation and plotting scripts for the packing-report project.

## Usage

```bash
uv run eval/some_script.py
```

Output visualizations are written to the `output/` subdirectory.

## Adding an evaluation

Add a Python script to this directory. It can import from `database_io` (data access) and `insights` (analytics code).

```python
import matplotlib.pyplot as plt
from database_io import get_session
from insights.metrics.low_level.vaep import Vaep

# fetch data, compute metrics, plot results
plt.savefig("output/my_plot.png")
```

## Dependencies

- `database-io`, `insights` (workspace) — data access and analytics
- `matplotlib>=3.8` — plotting
