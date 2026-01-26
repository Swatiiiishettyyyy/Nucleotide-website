import json
from collections import defaultdict
from pathlib import Path


CATALOGUE_PATH = Path(__file__).parent / "Thyrocare_Catalogue.json"


def _load_catalogue() -> dict:
    with CATALOGUE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_group_name(group_name: str) -> str:
    """
    Normalize raw groupName coming from catalogue.

    Currently we just strip whitespace so that values like
    'PANCREATIC ' and 'PANCREATIC' are treated the same.
    """
    if group_name is None:
        return ""
    return group_name.strip()


def build_group_to_tests_mapping(catalogue: dict) -> dict[str, list[str]]:
    """
    Build mapping of raw groupName/system -> unique test names.

    Example:
    {
        "LIVER": ["ALKALINE PHOSPHATASE", "BILIRUBIN - TOTAL", ...],
        "RENAL": ["BLOOD UREA NITROGEN (BUN)", "CREATININE - SERUM", ...],
        ...
    }
    """
    grouped: dict[str, set[str]] = defaultdict(set)

    for sku in catalogue.get("skuList", []):
        for test in sku.get("testsIncluded", []):
            name = test.get("name")
            raw_group = test.get("groupName", "")
            group = _normalize_group_name(raw_group)
            if not group or not name:
                continue
            grouped[group].add(name)

    # Convert sets to sorted lists for stable output
    return {group: sorted(names) for group, names in grouped.items()}


def build_organ_panel_mapping(group_to_tests: dict[str, list[str]]) -> dict:
    """
    Build high-level organ -> panel -> parameters mapping using the
    group-to-tests mapping derived from the catalogue.

    The mapping below is opinionated and can be adjusted as needed.
    """
    # Map raw group names from catalogue to (organ, panel_label)
    group_to_organ_panel: dict[str, tuple[str, str]] = {
        "LIVER": ("Liver", "LFT (Liver Function Test)"),
        "RENAL": ("Kidney", "RFT (Renal Function Test)"),
        "THYROID": ("Thyroid", "Thyroid Profile"),
        "LIPID": ("Lipid", "Lipid Profile"),
        "DIABETES": ("Metabolic", "Diabetes Panel"),
        "CARDIAC RISK MARKERS": ("Heart/Cardiac", "Cardiac Risk Panel"),
        "COMPLETE HEMOGRAM": ("Blood", "Complete Hemogram"),
        "COMPLETE URINE ANALYSIS": ("Urinary System", "Urine Analysis"),
        "TOXIC ELEMENTS": ("Toxicology", "Toxic Elements Panel"),
        "VITAMINS": ("Vitamins", "Vitamin Panel"),
        "ELEMENTS": ("Trace Elements", "Trace Elements Panel"),
        "HORMONE": ("Endocrine", "Hormone Panel"),
        "ARTHRITIS": ("Joints/Arthritis", "Arthritis Panel"),
        "PANCREATIC": ("Pancreas", "Pancreatic Panel"),
        "ELECTROLYTES": ("Electrolytes", "Electrolyte Panel"),
    }

    organ_mapping: dict[str, dict] = {}

    for raw_group, tests in group_to_tests.items():
        normalized_group = _normalize_group_name(raw_group)
        organ_panel = group_to_organ_panel.get(normalized_group)
        if organ_panel is None:
            # Skip groups we haven't explicitly mapped to an organ yet.
            # They can be added later if needed.
            continue

        organ, panel_label = organ_panel
        organ_entry = organ_mapping.setdefault(
            organ,
            {
                "panels": {}
            },
        )

        # Ensure panel exists for this organ
        panel = organ_entry["panels"].setdefault(
            panel_label,
            {
                "parameters": []
            },
        )

        # Merge and deduplicate parameters
        existing_params = set(panel["parameters"])
        for t in tests:
            if t not in existing_params:
                panel["parameters"].append(t)
                existing_params.add(t)

    return organ_mapping


def generate_and_save_organ_panel_mapping(
    output_path: str | Path = None,
) -> dict:
    """
    High-level helper to:
      1. Load `Thyrocare_Catalogue.json`
      2. Build group -> tests mapping
      3. Build organ -> panel -> parameters mapping
      4. Optionally save to JSON file

    Returns the organ_panel_mapping dict.
    """
    if output_path is None:
        output_path = Path(__file__).parent / "organ_panel_mapping.json"
    else:
        output_path = Path(output_path)

    catalogue = _load_catalogue()
    group_to_tests = build_group_to_tests_mapping(catalogue)
    organ_panel_mapping = build_organ_panel_mapping(group_to_tests)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(organ_panel_mapping, f, indent=2, ensure_ascii=False)

    return organ_panel_mapping


if __name__ == "__main__":
    mapping = generate_and_save_organ_panel_mapping()
    print(f"Organ panel mapping generated with {len(mapping)} organs.")


