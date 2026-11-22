The data hall model and MEP routing have been implemented in `output/solution.py`. The model includes a base structure of 128 racks (arranged in an 8x16 grid), a site, a building, and a storey. Simplified overhead service routes (telecom tray, power busway, and chilled water pipe) have been added as IFC entities. The model is saved as an IFC4 file at `output/model.ifc`, and a reconciliation log detailing the assumptions made due to the inability to read the drawing files is provided in `output/reconciliation.json`.

- **Model Script:** `output/solution.py`
- **IFC Model:** `output/model.ifc`
- **Reconciliation Log:** `output/reconciliation.json`