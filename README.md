# A-Share Quant Research — Original Dashboard

Independent eight-page Streamlit dashboard (no Week 7 integration).

## Launch

```bash
pip install -r requirements.txt
streamlit run dashboard_app.py
```

## Deployment

Upload the **contents** of this folder to the root of the GitHub repository.
On Streamlit Community Cloud select `dashboard_app.py` as entrypoint.

## Important data limitations

Parquet panels are **reduced extracts**, up to 250 stocks and 500 latest trading days,
not the full 2018–2024 research universe. Data coverage, stock counts,
liquidity screens and factor distributions on Overview/Factor Library/Liquidity
pages describe the extract only, not the original full-sample study.
W3/W4 CSV reports, when copied, retain their original study values.
Do not interpret extracted panel metrics as full-universe results.
Check `deployment_manifest.json` for missing/skipped files.
Do not upload private or licensed datasets without permission.
