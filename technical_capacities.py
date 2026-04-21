import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

CAPACIDADES_XLS_PATH = Path(__file__).parent / "data" / "Capacidades.xls"
HP_WATTS = 745.6998715822702
INCH_TO_M = 0.0254

FIELD_ROW_MAP = {
    "eficiencia": 3,
    "altura_m": 4,
    "rpm": 5,
    "diametro_polea_in": 6,
    "velocidad_lineal_m_s": 7,
    "densidad": 9,
    "capacidad_ton_h_teorica": 12,
    "capacidad_ton_h_eficiencia": 13,
    "momento_torsion": 16,
    "potencia_hp": 17,
}


def _normalize_text(text: str) -> str:
    return (
        str(text or "")
        .strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _field_from_concept(concept: str) -> Optional[str]:
    text = _normalize_text(concept)

    if "eficiencia" in text and "% eficiencia" not in text:
        return "eficiencia"
    if "altura elevador" in text:
        return "altura_m"
    if "velocidad angular" in text:
        return "rpm"
    if "diametro de polea" in text:
        return "diametro_polea_in"
    if "velocidad lineal" in text:
        return "velocidad_lineal_m_s"
    if "capacidad cubeta" in text:
        return "capacidad_cubeta"
    if "densidad materia prima" in text:
        return "densidad"
    if "n° cubeta por metro" in text or "n cubeta por metro" in text:
        return "cubetas_por_metro"
    if "capacidad teorica del elevador" in text:
        return "capacidad_teorica_ton_h"
    if "cap. elevador % eficiencia" in text or "cap elevador % eficiencia" in text:
        return "capacidad_eficiencia_ton_h"
    if text.startswith("cap. elevador") or text.startswith("cap elevador"):
        return "capacidad_ton_h"
    if "total de cubetas instaladas" in text:
        return "total_cubetas_instaladas"
    if "volumen_m3" in text:
        return "volumen_m3"
    if "momento de torsion" in text:
        return "momento_torsion"
    if text.startswith("potencia"):
        return "potencia_hp"

    return None


def _is_long_table_format(sheet) -> bool:
    if sheet.nrows == 0:
        return False
    header_a = _normalize_text(sheet.cell_value(0, 0)) if sheet.ncols > 0 else ""
    has_model_col = any(_normalize_text(sheet.cell_value(0, c)) == "modelo" for c in range(min(sheet.ncols, 8)))
    return header_a == "concepto" and has_model_col


def _normalize_model(modelo: str) -> str:
    text = str(modelo or "").upper().strip()
    match = re.search(r"(\d+)\s*[X*]\s*(\d+)", text)
    if match:
        return f"{match.group(1)}X{match.group(2)}"
    return text.replace(" ", "").replace("*", "X")


def _normalize_scenario(scenario: str) -> str:
    text = str(scenario or "").lower().strip()
    if "agua" in text or "total" in text:
        return "agua"
    return "admisible"


def _to_float(value) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _is_row_editable(value) -> bool:
    text = str(value or "").strip().lower()
    if text.startswith("no"):
        return False
    return "editable" in text


@lru_cache(maxsize=1)
def get_editable_flags(file_path: str = str(CAPACIDADES_XLS_PATH)) -> Dict[str, bool]:
    path = Path(file_path)
    if not path.exists():
        return {}

    try:
        import xlrd
    except Exception:
        return {}

    wb = xlrd.open_workbook(str(path))
    sheet = wb.sheet_by_index(0)
    flags: Dict[str, bool] = {}

    if _is_long_table_format(sheet):
        for row_idx in range(1, sheet.nrows):
            field = _field_from_concept(sheet.cell_value(row_idx, 0))
            if not field:
                continue
            if field not in flags:
                flags[field] = _is_row_editable(sheet.cell_value(row_idx, 2))
        return flags

    for field, row_idx in FIELD_ROW_MAP.items():
        if row_idx >= sheet.nrows:
            continue
        flags[field] = _is_row_editable(sheet.cell_value(row_idx, 2))

    return flags


@lru_cache(maxsize=128)
def get_editable_flags_for_model(
    modelo: str,
    file_path: str = str(CAPACIDADES_XLS_PATH),
) -> Dict[str, bool]:
    path = Path(file_path)
    if not path.exists():
        return {}

    try:
        import xlrd
    except Exception:
        return {}

    wb = xlrd.open_workbook(str(path))
    sheet = wb.sheet_by_index(0)
    model_norm = _normalize_model(modelo)

    if _is_long_table_format(sheet):
        flags: Dict[str, bool] = {}
        for row_idx in range(1, sheet.nrows):
            model_raw = str(sheet.cell_value(row_idx, 5)).strip() if sheet.ncols > 5 else ""
            if not model_raw or _normalize_model(model_raw) != model_norm:
                continue

            field = _field_from_concept(sheet.cell_value(row_idx, 0))
            if not field:
                continue

            flags[field] = _is_row_editable(sheet.cell_value(row_idx, 2))

        if flags:
            return flags

    # Fallback: formato antiguo o sin coincidencia exacta por modelo.
    return get_editable_flags(file_path)


@lru_cache(maxsize=1)
def load_capacity_entries(file_path: str = str(CAPACIDADES_XLS_PATH)) -> List[Dict]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        import xlrd
    except Exception:
        return []

    wb = xlrd.open_workbook(str(path))
    sheet = wb.sheet_by_index(0)

    if _is_long_table_format(sheet):
        entries_by_key: Dict = {}

        for row_idx in range(1, sheet.nrows):
            model_raw = str(sheet.cell_value(row_idx, 5)).strip() if sheet.ncols > 5 else ""
            if not model_raw:
                continue

            field = _field_from_concept(sheet.cell_value(row_idx, 0))
            if not field:
                continue

            model_norm = _normalize_model(model_raw)

            for scenario_norm, col_idx, scenario_label in (
                ("admisible", 3, "Cubeta llenado max. admisible"),
                ("agua", 4, "Cubeta llenado de agua"),
            ):
                if col_idx >= sheet.ncols:
                    continue

                key = (model_norm, scenario_norm)
                entry = entries_by_key.setdefault(
                    key,
                    {
                        "modelo": model_raw,
                        "modelo_norm": model_norm,
                        "escenario": scenario_label,
                        "escenario_norm": scenario_norm,
                    },
                )

                value = _to_float(sheet.cell_value(row_idx, col_idx))
                if value is not None:
                    entry[field] = value

        entries: List[Dict] = []
        for entry in entries_by_key.values():
            if entry.get("rpm") is None or entry.get("potencia_hp") is None or entry.get("momento_torsion") is None:
                continue
            entries.append(entry)

        return entries

    rows = {
        "eficiencia": FIELD_ROW_MAP["eficiencia"],
        "altura_m": FIELD_ROW_MAP["altura_m"],
        "rpm": FIELD_ROW_MAP["rpm"],
        "diametro_polea_in": FIELD_ROW_MAP["diametro_polea_in"],
        "velocidad_lineal_m_s": FIELD_ROW_MAP["velocidad_lineal_m_s"],
        "densidad": FIELD_ROW_MAP["densidad"],
        "capacidad_ton_h": FIELD_ROW_MAP["capacidad_ton_h_teorica"],
        "capacidad_eficiencia_ton_h": FIELD_ROW_MAP["capacidad_ton_h_eficiencia"],
        "momento_torsion": FIELD_ROW_MAP["momento_torsion"],
        "potencia_hp": FIELD_ROW_MAP["potencia_hp"],
    }

    entries: List[Dict] = []
    for col in range(3, sheet.ncols):
        modelo = str(sheet.cell_value(1, col)).strip()
        escenario = str(sheet.cell_value(2, col)).strip()
        if not modelo or not escenario:
            continue

        data = {
            "modelo": modelo,
            "modelo_norm": _normalize_model(modelo),
            "escenario": escenario,
            "escenario_norm": _normalize_scenario(escenario),
        }

        for key, row_idx in rows.items():
            data[key] = _to_float(sheet.cell_value(row_idx, col))

        if data["rpm"] is None or data["potencia_hp"] is None or data["momento_torsion"] is None:
            continue

        entries.append(data)

    return entries


def find_best_capacity_entry(
    modelo: str,
    escenario_llenado: str,
    rpm: Optional[float] = None,
    altura_m: Optional[float] = None,
) -> Optional[Dict]:
    modelo_norm = _normalize_model(modelo)
    escenario_norm = _normalize_scenario(escenario_llenado)

    entries = load_capacity_entries()
    candidates = [
        e
        for e in entries
        if e["modelo_norm"] == modelo_norm and e["escenario_norm"] == escenario_norm
    ]

    if not candidates:
        return None

    def score(entry: Dict) -> float:
        score_value = 0.0
        if rpm is not None and entry.get("rpm") is not None:
            score_value += abs(float(rpm) - float(entry["rpm"]))
        if altura_m is not None and entry.get("altura_m") is not None:
            score_value += abs(float(altura_m) - float(entry["altura_m"])) * 2.0
        return score_value

    return min(candidates, key=score)


def _get_model_default_diameter_m(modelo: str) -> Optional[float]:
    modelo_norm = _normalize_model(modelo)
    for entry in load_capacity_entries():
        if entry.get("modelo_norm") != modelo_norm:
            continue
        diam_in = entry.get("diametro_polea_in")
        if diam_in is not None:
            return float(diam_in) * INCH_TO_M
    return None


def validate_power(entry: Dict) -> Dict:
    torque = float(entry["momento_torsion"])
    rpm = float(entry["rpm"])
    potencia_hp_tabla = float(entry["potencia_hp"])

    omega_rad_s = (2.0 * math.pi * rpm) / 60.0

    potencia_hp_as_nm = (torque * omega_rad_s) / HP_WATTS
    potencia_hp_as_lbin = (torque * rpm) / 63025.0

    err_nm = abs(potencia_hp_as_nm - potencia_hp_tabla) / max(potencia_hp_tabla, 1e-9)
    err_lbin = abs(potencia_hp_as_lbin - potencia_hp_tabla) / max(potencia_hp_tabla, 1e-9)

    unidad_inferida = "indeterminada"
    conclusion = "No hay evidencia clara de unidad del torque."

    if err_lbin < 0.02 and err_nm > 0.2:
        unidad_inferida = "lb*in"
        conclusion = (
            "La potencia tabulada cumple cuando el torque se interpreta en lb*in. "
            "El rotulo N*m en la tabla no coincide con la fisica reportada."
        )
    elif err_nm < 0.02:
        unidad_inferida = "N*m"
        conclusion = "La potencia tabulada coincide con P = T * omega usando N*m."

    return {
        "potencia_hp_tabla": potencia_hp_tabla,
        "potencia_hp_desde_nm": potencia_hp_as_nm,
        "potencia_hp_desde_lbin": potencia_hp_as_lbin,
        "error_rel_nm": err_nm,
        "error_rel_lbin": err_lbin,
        "unidad_torque_inferida": unidad_inferida,
        "conclusion": conclusion,
    }


def get_capacity_form_config(
    modelo: str,
    escenario_llenado: str,
    rpm_guess: Optional[float] = None,
    altura_guess: Optional[float] = None,
) -> Dict:
    entry = find_best_capacity_entry(
        modelo=modelo,
        escenario_llenado=escenario_llenado,
        rpm=rpm_guess,
        altura_m=altura_guess,
    )

    # Evita quedar fijado en fallback por un cache tecnico desactualizado.
    if entry is None:
        load_capacity_entries.cache_clear()
        get_editable_flags.cache_clear()
        get_editable_flags_for_model.cache_clear()
        entry = find_best_capacity_entry(
            modelo=modelo,
            escenario_llenado=escenario_llenado,
            rpm=rpm_guess,
            altura_m=altura_guess,
        )

    editable = get_editable_flags_for_model(modelo)

    model_default_diam_m = _get_model_default_diameter_m(modelo)

    values = {
        "eficiencia": 85.0,
        "altura_m": 10.0,
        "rpm": 100.0,
        "densidad": 800.0,
        "diametro_polea_m": model_default_diam_m if model_default_diam_m is not None else 0.5,
    }

    if entry:
        if entry.get("eficiencia") is not None:
            values["eficiencia"] = float(entry["eficiencia"]) * 100.0
        if entry.get("altura_m") is not None:
            values["altura_m"] = float(entry["altura_m"])
        if entry.get("rpm") is not None:
            values["rpm"] = float(entry["rpm"])
        if entry.get("densidad") is not None:
            values["densidad"] = float(entry["densidad"])
        if entry.get("diametro_polea_in") is not None:
            values["diametro_polea_m"] = float(entry["diametro_polea_in"]) * INCH_TO_M

    return {
        "values": values,
        "editable": {
            "eficiencia": editable.get("eficiencia", True),
            "altura_m": editable.get("altura_m", True),
            "rpm": editable.get("rpm", True),
            "densidad": editable.get("densidad", True),
            "diametro_polea_m": editable.get("diametro_polea_in", False) if entry is not None else True,
        },
        "entry_found": entry is not None,
    }
