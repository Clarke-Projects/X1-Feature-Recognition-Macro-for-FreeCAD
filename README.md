# X1 Feature Recognition Macro for FreeCAD

**Conservative, evidence‑based bore/pocket/hex seat detection.**  
Runs as a single FreeCAD macro; outputs a structured feature tree and
machine‑readable evidence ledger (CSV/JSON).

## ✨ What it does

- Detects through‑holes, counterbores, stepped stacks (all three axes).
- Finds anchored circular pockets even without cylinder faces.
- Classifies hex/nut pockets and resolves chamfered mouths to true nut seats.
- Works on **analytic CAD bodies** and **tessellated/imported meshes**.
- **Never** promotes a feature without multiple independent evidence sources.
- Exports a full audit trail (CSV/JSON) for downstream CAM/PLM tools.

## 📂 Output groups
X1_Feature_Tree
├── 01 Accepted Bores
├── 02 Anchored Circular Pockets
├── 03 Hex / Nut Mouth Diagnostics
├── 04 Hex / Nut Chamfer‑Resolved Seats
├── 05–08 FAST diagnostics, reconciliation, side‑probe, ledger
└── 90 Rejected / Debug Diagnostics



## 🚀 How to use

1. Open FreeCAD.
2. Select one or more solid bodies (Part, mesh import, STEP).
3. Run the macro (Macro → Macros… → select `x1_2026_r20b_…FCMacro`).
4. Inspect the group `X1_2026_R20B_Feature_Tree`.
5. Find exported CSV/JSON ledgers on your Desktop (or next to the FreeCAD file).

## ⚙️ Configuration

All parameters are at the top of the file under `# User configuration`.
They are documented and use relative thresholds – no hard‑coded coordinates.

## 📊 Evidence ledger

The CSV/JSON export contains, for every detected feature candidate:
- axis, centre, radius, depth
- evidence sources (FAST stack, side probe, accepted primitive)
- risk flags (suppressed, side‑pair only, unanchored tessellation…)
- promotion readiness (diagnostic, preview, accepted)

This can be consumed directly by CAM tools, PLM systems, or your own scripts.

## 🔒 Design philosophy

- **Prefer zero cylinders over random cylinders.**
- No parameter fitting to a specific test part.
- Every acceptance gate uses relative (part‑independent) thresholds.
- Diagnostic features are shown but not promoted until multiple evidence systems agree.

## 📜 License

MIT (see `LICENSE` file).

## 🧪 Version history

- **R20B** – guarded accepted promotion for missing bore/chamfer entries (FAST stack + side pair).
- **R20A** – preview‑only promotion cylinders, Tier A/B review markers.
- **R18B** – structured feature tree (the stable base).
- … earlier versions described in the macro docstring.

## 🙋 Author

Mathias Clarke 