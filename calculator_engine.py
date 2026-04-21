"""
Motor de Cálculos Financiero e Ingeniería para Cotizador INVEIN
Implementa reglas de negocio: Transformación (35% MP) y Suministros (20% margen)
"""
import math
import re
from typing import Dict, List
from sqlalchemy.orm import Session
from lamina_catalog import get_lamina_name
from models import SheetPrice, BomTemplate
from pricing_factor_catalog import get_factor_ganancia
from technical_capacities import find_best_capacity_entry, validate_power


class CotizacionResult:
    """Contenedor del resultado final de una cotización"""
    def __init__(self):
        self.detalles_bom: List[Dict] = []
        self.costo_materia_prima: float = 0.0
        self.costo_suministros: float = 0.0
        self.subtotal_transformacion: float = 0.0
        self.subtotal_suministros: float = 0.0
        self.subtotal_neto: float = 0.0
        self.iva: float = 0.0
        self.total_venta: float = 0.0
        self.especificaciones: Dict = {}
        self.desglose_costos: Dict = {}  # MO, Admin, CIF, etc.


class CalculatorEngine:
    """
    Motor de cálculos integrado con BD.
    Regla 1: Transformación → Precio = Costo_MP / 0.35
    Regla 2: Suministros → Precio = Costo × 1.20
    """
    
    # Constantes de desglose para transformación
    FACTORES_DESGLOSE = {
        "mano_obra": 0.22,
        "administracion": 0.07,
        "cif": 0.06,
        "comercial": 0.03,
        "seguridad": 0.03,
        "negociacion": 0.04,
        "utilidad": 0.20
    }
    MATERIA_PRIMA_PCTJ = 0.35  # Porcentaje de MP en transformación
    MARGEN_SUMINISTROS = 1.20  # Factor multiplicador suministros
    IVA_TASA = 0.0  # Oferta comercial sin IVA
    ALTURA_MODULO_METROS = 2.4  # Cantidades base en BOM equivalen a 2.4 m de construccion
    FACTOR_MINIMO_ALTURA = 0.25
    ALTURA_CABEZA_M = 1.2
    ALTURA_BASE_M = 1.0
    ALTURA_PIERNA_INSPECCION_M = 2.4
    
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _es_material_lamina(material_referencia: str) -> bool:
        texto = (material_referencia or "").lower().replace("á", "a")
        return "lamina" in texto or re.search(r"\blam\b", texto) is not None

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        return (texto or "").lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    def _calibre_por_regla_negocio(
        self,
        item: BomTemplate,
        modelo: str,
        altura_total: float,
        calibres_por_parte: Dict[str, int],
    ) -> int:
        """Regla de negocio de calibres de lamina.

        - Solo "Pierna Inspeccion" puede variar calibre.
        - Solo modelo 5x4 permite calibre 14.
        - Solo si altura < 15 m.
        - En cualquier otro caso, calibre 12 por defecto.
        """
        parte = self._normalizar_texto(item.parte)
        modelo_norm = self._normalizar_texto(modelo).replace("*", "x")

        if parte != "pierna inspeccion":
            return 12

        if modelo_norm == "5x4" and altura_total < 15:
            seleccionado = calibres_por_parte.get(item.parte, 12)
            return seleccionado if seleccionado in (12, 14) else 12

        return 12

    def _cantidad_efectiva(self, item: BomTemplate, altura_total: float) -> float:
        """Ajusta cantidades con reglas físicas por tramos de altura del elevador."""
        parte = self._normalizar_texto(item.parte)
        material = self._normalizar_texto(item.material_referencia)
        base = float(item.cantidad)
        factor_altura = self._factor_altura_modular(altura_total)

        # Base y cabeza son tramos fijos (no escalan por altura solicitada).
        if parte in ("base", "cabeza"):
            return base

        # Pierna de inspeccion: siempre va 1 fija.
        if "pierna inspeccion" in parte:
            return base

        # Piernas del elevador: 2.4 m por modulo para completar altura restante.
        if "piernas elevador" in parte or parte == "piernas elevador":
            modulos = self._modulos_piernas_elevador(altura_total)
            return round(base * modulos, 3)

        # Para laminas, la cantidad base del BOM se interpreta como modulo de 2.4 m.
        if self._es_material_lamina(item.material_referencia):
            return round(base * factor_altura, 3)

        # Otros elementos longitudinales sin regla específica por parte.
        if "pierna" in parte:
            return round(base * factor_altura, 3)

        # Componentes usualmente ligados a longitud total.
        if "banda" in material or "cubeta" in material:
            return round(base * factor_altura, 3)

        # Tornillería y pintura de zonas longitudinales.
        if "tornilleria" in material and "pierna" in parte:
            return round(base * factor_altura, 3)

        if "pintura" in material and "pierna" in parte:
            return round(base * factor_altura, 3)

        return base

    def _factor_altura_modular(self, altura_total: float) -> float:
        """Factor por altura asumiendo BOM base para 2.4 m."""
        return max(altura_total / self.ALTURA_MODULO_METROS, self.FACTOR_MINIMO_ALTURA)

    def _modulos_piernas_elevador(self, altura_total: float) -> int:
        """Calcula N módulos de piernas elevador de 2.4 m.

        Regla aplicada:
        - Cabeza fija: 1.2 m
        - Base fija: 1.0 m
        - Una pierna de inspección fija: 2.4 m
        - El resto se completa con piernas elevador de 2.4 m
        """
        altura_restante = float(altura_total) - (
            self.ALTURA_CABEZA_M + self.ALTURA_BASE_M + self.ALTURA_PIERNA_INSPECCION_M
        )

        if altura_restante <= 0:
            return 0

        return math.ceil(altura_restante / self.ALTURA_MODULO_METROS)
    
    def calcular_cotizacion(
        self,
        modelo: str,
        material_lamina: str,
        altura_total: float,
        rpm: float,
        densidad_producto: float,
        diametro_polea: float = 0.5,
        calibres_por_parte: Dict[str, int] = None,
        escenario_llenado: str = "admisible",
        eficiencia_pct: float = 85.0,
    ) -> CotizacionResult:
        """
        Calcula la cotización completa para un elevador.
        
        Args:
            modelo: "5x4", "6x4", "7x5", etc.
            material_lamina: "HR" o "GALV"
            altura_total: altura en metros
            rpm: revoluciones por minuto
            densidad_producto: kg/m³
            diametro_polea: diámetro en metros
            calibres_por_parte: dict con {nombre_parte: calibre}
                               Ej: {"Piernas": 16, "Cabeza": 14}
            escenario_llenado: "admisible" o "agua"
            eficiencia_pct: eficiencia global editable del usuario en porcentaje
        
        Returns:
            CotizacionResult con detalles completos
        """
        resultado = CotizacionResult()
        
        if calibres_por_parte is None:
            calibres_por_parte = {}
        
        try:
            # 1. Obtener BOM del modelo
            bom_items = self.db.query(BomTemplate).filter(
                BomTemplate.modelo_elevador == modelo
            ).all()
            
            if not bom_items:
                raise ValueError(f"Modelo '{modelo}' no encontrado en BOM")
            
            # 2. Procesar cada línea del BOM
            for item in bom_items:
                detalle = self._procesar_linea_bom(
                    item, 
                    modelo,
                    material_lamina,
                    calibres_por_parte,
                    altura_total,
                    resultado
                )
                resultado.detalles_bom.append(detalle)
            
            # 3. Calcular parámetros de ingeniería
            resultado.especificaciones = self._calcular_ingenieria(
                altura_total,
                rpm,
                densidad_producto,
                diametro_polea,
                modelo,
                escenario_llenado,
                eficiencia_pct,
            )
            
            # 4. Calcular totales y desglose
            self._calcular_totales(resultado)
            
            return resultado
            
        except Exception as e:
            resultado.desglose_costos = {"error": str(e)}
            return resultado
    
    def _procesar_linea_bom(
        self,
        item: BomTemplate,
        modelo: str,
        material_lamina: str,
        calibres_por_parte: Dict[str, int],
        altura_total: float,
        resultado: CotizacionResult
    ) -> Dict:
        """
        Procesa una línea del BOM y retorna su desglose de costos.
        Usa los calibres específicos seleccionados por el usuario para cada parte.
        """
        
        cantidad_efectiva = self._cantidad_efectiva(item, altura_total)
        base_cantidad = float(item.cantidad)
        factor_linea = (cantidad_efectiva / base_cantidad) if base_cantidad > 0 else 0.0

        detalle = {
            "parte": item.parte,
            "material": item.material_referencia,
            "cantidad_base_2_4m": base_cantidad,
            "factor_altura": round(factor_linea, 3),
            "factor_ganancia": None,
            "fuente_factor": "regla_default",
            "cantidad": cantidad_efectiva,
            "costo_unitario": 0.0,
            "costo_total": 0.0,
            "costo_venta": 0.0,
            "es_transformacion": item.es_transformacion
        }
        
        # Si es lámina, buscar precio dinámico usando el calibre seleccionado por el usuario
        if self._es_material_lamina(item.material_referencia):
            calibre_seleccionado = self._calibre_por_regla_negocio(
                item,
                modelo,
                altura_total,
                calibres_por_parte,
            )

            # Mostrar nombre comercial de la lámina según data/Lamina.xlsx
            detalle["material"] = f"{get_lamina_name(material_lamina, calibre_seleccionado)} ({material_lamina})"
            
            sheet_price = self.db.query(SheetPrice).filter(
                SheetPrice.material == material_lamina,
                SheetPrice.calibre == calibre_seleccionado
            ).first()
            
            if sheet_price:
                costo_unitario = sheet_price.valor_unitario
            else:
                costo_unitario = item.costo_base_materia_prima
        else:
            costo_unitario = item.costo_base_materia_prima
        
        detalle["costo_unitario"] = costo_unitario
        costo_total = costo_unitario * detalle["cantidad"]
        detalle["costo_total"] = costo_total

        factor_ganancia, fuente_factor = get_factor_ganancia(
            modelo=modelo,
            parte=item.parte,
            material_referencia=item.material_referencia,
            material_lamina_tipo=material_lamina if self._es_material_lamina(item.material_referencia) else None,
            calibre_lamina=calibre_seleccionado if self._es_material_lamina(item.material_referencia) else None,
        )
        factor_aplicado = factor_ganancia if factor_ganancia is not None and factor_ganancia > 0 else 1.0
        detalle["factor_ganancia"] = round(factor_aplicado, 4)
        detalle["fuente_factor"] = fuente_factor if factor_ganancia is not None and factor_ganancia > 0 else "sin_factor_excel"

        # Regla solicitada: precio de venta = costo total material * factor de ganancia.
        costo_venta = costo_total * factor_aplicado

        # Acumuladores financieros por tipo de línea.
        if item.es_transformacion:
            resultado.costo_materia_prima += costo_total
            resultado.subtotal_transformacion += costo_venta
        else:
            resultado.costo_suministros += costo_total
            resultado.subtotal_suministros += costo_venta
        
        detalle["costo_venta"] = costo_venta
        return detalle
    
    def _calcular_ingenieria(
        self,
        altura: float,
        rpm: float,
        densidad: float,
        diametro: float,
        modelo: str,
        escenario_llenado: str,
        eficiencia_pct: float,
    ) -> Dict:
        """Calcula parámetros de ingeniería mecánica."""
        
        especificaciones = {}
        
        try:
            # Resolver diámetro a usar en cálculos/visualización.
            diametro_usado_m = float(diametro)

            # Integración de capacidades técnicas desde data/Capacidades.xls
            cap_entry = find_best_capacity_entry(
                modelo=modelo,
                escenario_llenado=escenario_llenado,
                rpm=rpm,
                altura_m=altura,
            )

            if cap_entry and cap_entry.get("diametro_polea_in") is not None:
                diametro_usado_m = float(cap_entry.get("diametro_polea_in")) * 0.0254

            especificaciones["diametro_polea_in"] = round(diametro_usado_m * 39.3701, 2)

            # Velocidad lineal: v = π × D × RPM / 60
            velocidad_lineal = (math.pi * diametro_usado_m * rpm) / 60
            especificaciones["velocidad_lineal_m_s"] = round(velocidad_lineal, 3)
            
            # Capacidad en Ton/h (simplificado: basado en densidad y velocidad)
            # Factor 0.05 es coeficiente de volumen de cubeta estimado
            capacidad_ton_h = (densidad * 0.05 * velocidad_lineal * 3600) / 1000
            eficiencia_factor = max(min(float(eficiencia_pct) / 100.0, 1.0), 0.01)
            especificaciones["capacidad_ton_h"] = round(capacidad_ton_h * eficiencia_factor, 2)
            
            # Potencia en HP (estimado con altura y rpm)
            # Fórmula: HP = (Altura × Densidad × RPM) / 1000 + 15% factor de seguridad
            hp_base = (altura * densidad * rpm) / 1000
            hp_con_seguridad = hp_base * 1.15
            especificaciones["potencia_hp"] = round(hp_con_seguridad, 2)
            especificaciones["potencia_hp_base"] = round(hp_base, 2)
            
            # Torque estimado (N·m)
            torque = (hp_con_seguridad * 735.5) / (rpm / 60) if rpm > 0 else 0
            especificaciones["torque_nm"] = round(torque, 2)
            
            # Altura de elevación confirmada
            especificaciones["altura_elevacion_m"] = round(altura, 2)
            especificaciones["rpm_operacion"] = round(rpm, 1)

            if cap_entry:
                validacion = validate_power(cap_entry)

                especificaciones["fuente_capacidades"] = "Capacidades.xls"
                especificaciones["escenario_llenado"] = escenario_llenado
                capacidad_teorica = float(
                    cap_entry.get(
                        "capacidad_teorica_ton_h",
                        cap_entry.get("capacidad_ton_h", capacidad_ton_h),
                    )
                )
                capacidad_neta_tabla = cap_entry.get("capacidad_eficiencia_ton_h")

                especificaciones["capacidad_ton_h_teorica"] = round(capacidad_teorica, 2)
                especificaciones["capacidad_ton_h_tabla"] = round(float(cap_entry.get("capacidad_ton_h", capacidad_teorica)), 2)
                if capacidad_neta_tabla is not None:
                    especificaciones["capacidad_ton_h_eficiencia_tabla"] = round(float(capacidad_neta_tabla), 2)
                    # Cuando hay valor tabulado con eficiencia, se usa directo del Excel.
                    especificaciones["capacidad_ton_h"] = round(float(capacidad_neta_tabla), 2)
                else:
                    especificaciones["capacidad_ton_h"] = round(capacidad_teorica, 2)

                if cap_entry.get("capacidad_cubeta") is not None:
                    especificaciones["capacidad_cubeta"] = round(float(cap_entry.get("capacidad_cubeta")), 6)
                if cap_entry.get("cubetas_por_metro") is not None:
                    especificaciones["cubetas_por_metro"] = round(float(cap_entry.get("cubetas_por_metro")), 4)
                if cap_entry.get("total_cubetas_instaladas") is not None:
                    especificaciones["total_cubetas_instaladas"] = round(float(cap_entry.get("total_cubetas_instaladas")), 2)
                if cap_entry.get("volumen_m3") is not None:
                    especificaciones["volumen_m3"] = round(float(cap_entry.get("volumen_m3")), 6)

                especificaciones["potencia_hp"] = round(cap_entry.get("potencia_hp", hp_con_seguridad), 2)
                especificaciones["potencia_hp_tabla"] = round(validacion["potencia_hp_tabla"], 3)
                especificaciones["potencia_hp_desde_torque_nm"] = round(validacion["potencia_hp_desde_nm"], 3)
                especificaciones["potencia_hp_desde_torque_lbin"] = round(validacion["potencia_hp_desde_lbin"], 3)
                especificaciones["error_rel_potencia_nm_pct"] = round(validacion["error_rel_nm"] * 100, 2)
                especificaciones["error_rel_potencia_lbin_pct"] = round(validacion["error_rel_lbin"] * 100, 2)
                especificaciones["unidad_torque_inferida"] = validacion["unidad_torque_inferida"]
                especificaciones["conclusion_validacion_potencia"] = validacion["conclusion"]
                especificaciones["momento_torsion_tabla"] = round(cap_entry.get("momento_torsion", 0.0), 3)
                especificaciones["velocidad_lineal_m_s"] = round(cap_entry.get("velocidad_lineal_m_s", velocidad_lineal), 3)
                rpm_tabla = float(cap_entry.get("rpm", rpm))
                altura_tabla = float(cap_entry.get("altura_m", altura))
                densidad_tabla = float(cap_entry.get("densidad", densidad))
                eficiencia_tabla = float(cap_entry.get("eficiencia", 0.0))

                especificaciones["rpm_tabla"] = round(rpm_tabla, 2)
                especificaciones["altura_tabla_m"] = round(altura_tabla, 2)
                especificaciones["densidad_tabla"] = round(densidad_tabla, 2)
                especificaciones["eficiencia_tabla"] = round(eficiencia_tabla, 3)
                especificaciones["eficiencia_usuario_pct"] = round(float(eficiencia_pct), 2)

                # La especificacion operativa se alinea con la tabla tecnica cuando existe match.
                especificaciones["altura_elevacion_m"] = round(altura_tabla, 2)
                especificaciones["rpm_operacion"] = round(rpm_tabla, 1)
                especificaciones["densidad_operacion"] = round(densidad_tabla, 2)
            else:
                especificaciones["escenario_llenado"] = escenario_llenado
                especificaciones["eficiencia_usuario_pct"] = round(float(eficiencia_pct), 2)
                especificaciones["conclusion_validacion_potencia"] = (
                    "No se encontro coincidencia en Capacidades.xls para el modelo y escenario seleccionados. "
                    "Se uso el calculo interno de ingenieria."
                )
            
        except Exception as e:
            especificaciones["error"] = str(e)
        
        return especificaciones
    
    def _calcular_totales(self, resultado: CotizacionResult) -> None:
        """Calcula subtotales y total final sin IVA."""
        
        # Subtotal neto
        resultado.subtotal_neto = resultado.subtotal_transformacion + resultado.subtotal_suministros
        
        # IVA no aplica
        resultado.iva = 0.0

        # Total venta sin IVA
        resultado.total_venta = resultado.subtotal_neto
        
        # Desglose de costos (para transformación solamente)
        if resultado.subtotal_transformacion > 0:
            mp_en_venta = resultado.costo_materia_prima
            resto = resultado.subtotal_transformacion - mp_en_venta
            
            resultado.desglose_costos = {
                "materia_prima": round(mp_en_venta, 2),
                "materia_prima_pctj": f"{(mp_en_venta/resultado.subtotal_transformacion*100):.1f}%",
                "mano_obra": round(resto * (self.FACTORES_DESGLOSE["mano_obra"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "administracion": round(resto * (self.FACTORES_DESGLOSE["administracion"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "cif": round(resto * (self.FACTORES_DESGLOSE["cif"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "comercial": round(resto * (self.FACTORES_DESGLOSE["comercial"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "seguridad": round(resto * (self.FACTORES_DESGLOSE["seguridad"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "negociacion": round(resto * (self.FACTORES_DESGLOSE["negociacion"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
                "utilidad": round(resto * (self.FACTORES_DESGLOSE["utilidad"] / (1 - self.MATERIA_PRIMA_PCTJ)), 2),
            }
        else:
            resultado.desglose_costos = {
                "suministros": round(resultado.costo_suministros, 2),
                "margen": round(resultado.subtotal_suministros - resultado.costo_suministros, 2),
            }
    
    def generar_reporte_desglose(self, resultado: CotizacionResult) -> str:
        """Genera un reporte textual del desglose de costos."""
        
        lineas = []
        lineas.append("=" * 60)
        lineas.append("DESGLOSE DE COSTOS - COTIZACIÓN INVEIN")
        lineas.append("=" * 60)
        
        if "error" in resultado.desglose_costos:
            lineas.append(f"❌ ERROR: {resultado.desglose_costos['error']}")
            return "\n".join(lineas)
        
        lineas.append("\n📦 COMPONENTES DE TRANSFORMACIÓN:")
        for linea in resultado.detalles_bom:
            if linea["es_transformacion"]:
                lineas.append(
                    f"  {linea['parte']:20} | "
                    f"${linea['costo_venta']:>12,.2f}"
                )
        
        lineas.append("\n🔧 COMPONENTES DE SUMINISTRO:")
        for linea in resultado.detalles_bom:
            if not linea["es_transformacion"]:
                lineas.append(
                    f"  {linea['parte']:20} | "
                    f"${linea['costo_venta']:>12,.2f}"
                )
        
        lineas.append("\n" + "-" * 60)
        lineas.append(f"Subtotal Transformación:  ${resultado.subtotal_transformacion:>12,.2f}")
        lineas.append(f"Subtotal Suministros:     ${resultado.subtotal_suministros:>12,.2f}")
        lineas.append(f"SUBTOTAL:                 ${resultado.subtotal_neto:>12,.2f}")
        lineas.append("IVA:                       No aplica")
        lineas.append(f"TOTAL VENTA:              ${resultado.total_venta:>12,.2f}")
        lineas.append("=" * 60)
        
        return "\n".join(lineas)
