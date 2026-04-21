import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Set

PDF_CATALOG_PATH = Path(__file__).parent / "data" / "1-ML_Catalog_SPN.pdf"

KNOWN_FAMILIES = [
    "TIGER-TUFF",
    "TIGER-CC",
    "HD-MAX",
    "HD-STAX",
    "CC-MAX",
    "DURA-BUKET",
    "MAXI-TUFF",
    "DI-MAX",
]

KNOWN_MATERIALS = [
    "Polietileno",
    "Nylon",
    "Nylon FDA",
    "Uretano",
    "Hierro ductil",
]


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _normalize_text(text: str) -> str:
    return _strip_accents(text or "").upper().replace("\n", " ")


def _normalize_family(value: str) -> str:
    text = _normalize_text(value)
    text = text.replace(" ", "").replace("_", "-")
    text = text.replace("TIGERTUFF", "TIGER-TUFF")
    text = text.replace("TIGERCC", "TIGER-CC")
    text = text.replace("HDMAX", "HD-MAX")
    text = text.replace("HDSTAX", "HD-STAX")
    text = text.replace("CCMAX", "CC-MAX")
    text = text.replace("DURABUKET", "DURA-BUKET")
    text = text.replace("MAXITUFF", "MAXI-TUFF")
    text = text.replace("DIMAX", "DI-MAX")
    return text


def _extract_sizes(page_text: str) -> Set[str]:
    sizes: Set[str] = set()
    for a, b in re.findall(r"\b(\d{1,2})\s*[xX]\s*(\d{1,2})\b", page_text):
        n1 = int(a)
        n2 = int(b)

        # Filtro anti-ruido OCR: en catalogo real los cangilones suelen caer en estos rangos.
        if not (4 <= n1 <= 24 and 4 <= n2 <= 16):
            continue

        sizes.add(f"{n1} x {n2}")
    return sizes


def _extract_materials(page_text: str) -> Set[str]:
    upper = _normalize_text(page_text)
    out: Set[str] = set()
    if "POLIETILENO" in upper:
        out.add("Polietileno")
    if "NYLON FDA" in upper:
        out.add("Nylon FDA")
    if "NYLON" in upper:
        out.add("Nylon")
    if "URETANO" in upper:
        out.add("Uretano")
    if "HIERRO DUCTIL" in upper:
        out.add("Hierro ductil")
    return out


def _extract_profiles(page_text: str) -> Set[str]:
    upper = _normalize_text(page_text)
    out: Set[str] = set()
    if "PERFIL ESTANDAR" in upper:
        out.add("Estandar")
    if "PERFIL BAJO" in upper:
        out.add("Bajo")
    return out


@lru_cache(maxsize=1)
def get_bucket_catalog_options(pdf_path: str = str(PDF_CATALOG_PATH)) -> Dict:
    path = Path(pdf_path)
    if not path.exists():
        return {
            "familias": KNOWN_FAMILIES,
            "perfiles_por_familia": {k: ["Estandar", "Bajo"] for k in KNOWN_FAMILIES},
            "materiales_por_familia": {k: KNOWN_MATERIALS for k in KNOWN_FAMILIES},
            "tamanos_por_familia": {k: [] for k in KNOWN_FAMILIES},
            "source": "fallback",
        }

    try:
        from pypdf import PdfReader
    except Exception:
        return {
            "familias": KNOWN_FAMILIES,
            "perfiles_por_familia": {k: ["Estandar", "Bajo"] for k in KNOWN_FAMILIES},
            "materiales_por_familia": {k: KNOWN_MATERIALS for k in KNOWN_FAMILIES},
            "tamanos_por_familia": {k: [] for k in KNOWN_FAMILIES},
            "source": "fallback-no-pypdf",
        }

    reader = PdfReader(str(path))

    families_found: Set[str] = set()
    profiles_by_family: Dict[str, Set[str]] = {k: set() for k in KNOWN_FAMILIES}
    materials_by_family: Dict[str, Set[str]] = {k: set() for k in KNOWN_FAMILIES}
    sizes_by_family: Dict[str, Set[str]] = {k: set() for k in KNOWN_FAMILIES}

    family_tokens = {_normalize_family(f): f for f in KNOWN_FAMILIES}

    for page in reader.pages:
        txt = page.extract_text() or ""
        upper = _normalize_text(txt)

        page_families: Set[str] = set()
        for token_norm, canonical in family_tokens.items():
            compact = token_norm.replace("-", "")
            if token_norm in upper.replace(" ", "") or compact in upper.replace(" ", ""):
                page_families.add(canonical)

        if not page_families:
            continue

        page_profiles = _extract_profiles(txt)
        page_materials = _extract_materials(txt)
        page_sizes = _extract_sizes(txt)

        for fam in page_families:
            families_found.add(fam)
            profiles_by_family[fam].update(page_profiles)
            materials_by_family[fam].update(page_materials)
            sizes_by_family[fam].update(page_sizes)

    if not families_found:
        families_found = set(KNOWN_FAMILIES)

    familias = sorted(families_found)

    perfiles_por_familia = {
        fam: sorted(profiles_by_family[fam]) if profiles_by_family[fam] else ["Estandar", "Bajo"]
        for fam in familias
    }
    materiales_por_familia = {
        fam: sorted(materials_by_family[fam]) if materials_by_family[fam] else KNOWN_MATERIALS
        for fam in familias
    }
    tamanos_por_familia = {
        fam: sorted(sizes_by_family[fam], key=lambda x: tuple(int(z.strip()) for z in x.split("x")))
        for fam in familias
    }

    return {
        "familias": familias,
        "perfiles_por_familia": perfiles_por_familia,
        "materiales_por_familia": materiales_por_familia,
        "tamanos_por_familia": tamanos_por_familia,
        "source": "pdf",
    }
