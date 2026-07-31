4 Colab notebooks — run in parallel for ~2.5h total wall clock.

  notebook_A_autogluon.py        autogluon              ~70 min
  notebook_B_h2o.py              h2o                    ~70 min
  notebook_C_flaml_mljar.py      flaml + mljar          ~2.3 h
  notebook_D_lightautoml_baselines.py  lightautoml + dummy + randomforest  ~2 h

How to use:
  1. Open a new Colab notebook
  2. Copy each # CELL block into a separate cell
  3. Run top to bottom
  4. Download the reports/run_*.json from Cell 7
  5. Repeat for all 4 notebooks (different browser tabs)

After all 4 finish, merge locally:
  python scripts/merge.py reports/run_autogluon.json reports/run_h2o.json reports/run_flaml_mljar.json reports/run_lama_baselines.json

IMPORTANT:
  - Competition datasets require accepting rules on kaggle.com first:
    GiveMeSomeCredit, santander-customer-satisfaction,
    otto-group-product-classification-challenge,
    house-prices-advanced-regression-techniques, allstate-claims-severity
  - Do NOT commit these files to a public git repo (they contain your Kaggle API key)
