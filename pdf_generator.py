"""
Generador de cotizaciones en PDF con membrete INVEIN S.A.S.
Utiliza ReportLab para crear PDFs profesionales
"""
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from calculator_engine import CotizacionResult


class CotizacionPDFGenerator:
    """Generador de PDFs profesionales de cotizaciones INVEIN"""
    
    LOGO_TEXT = "INVEIN S.A.S."
    EMPRESA_INFO = {
        "nombre": "INVEIN S.A.S.",
        "linea_negocio": "Equipos Agroindustriales",
        "direccion": "Colombia",
        "telefono": "+57 (1) XXX-XXXX",
        "email": "info@invein.com.co"
    }
    
    def __init__(self, usuario_comercial: str = "Comercial INVEIN"):
        self.usuario_comercial = usuario_comercial
        self.styles = getSampleStyleSheet()
        self._custom_styles()
    
    def _custom_styles(self):
        """Define estilos personalizados"""
        self.styles.add(ParagraphStyle(
            name='Header',
            fontSize=16,
            textColor=colors.HexColor('#F59E0B'),
            spaceAfter=6,
            alignment=1  # Centro
        ))
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            fontSize=11,
            textColor=colors.HexColor('#666666'),
            spaceAfter=3,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            spaceBefore=10,
            borderPadding=5
        ))
    
    def generar_pdf(
        self,
        cotizacion: CotizacionResult,
        modelo: str,
        material_lamina: str,
        usuario_nombre: str = "Cliente INVEIN"
    ) -> bytes:
        """
        Genera PDF de cotización.
        
        Args:
            cotizacion: Objeto CotizacionResult del motor
            modelo: Modelo del elevador (ej: "5x4")
            material_lamina: Material seleccionado
            usuario_nombre: Nombre del usuario comercial
        
        Returns:
            Bytes del PDF
        
        ✅ NOTA: Los calibres específicos de cada parte se muestran en la tabla BOM
                 ya que vienen del objeto cotizacion.detalles_bom
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.5*inch
        )
        
        # Construir elementos del documento
        story = []
        
        # 1. Encabezado con membrete
        story.extend(self._crear_encabezado())
        story.append(Spacer(1, 0.2*inch))
        
        # 2. Título y fecha
        story.extend(self._crear_titulo_fecha())
        story.append(Spacer(1, 0.15*inch))
        
        # 3. Datos de la cotización (modelo, material, etc.)
        story.extend(self._crear_datos_cotizacion(modelo, material_lamina))
        story.append(Spacer(1, 0.1*inch))
        
        # 4. Tabla de detalles BOM
        story.extend(self._crear_tabla_bom(cotizacion))
        story.append(Spacer(1, 0.1*inch))
        
        # 5. Resumen de costos
        story.extend(self._crear_resumen_costos(cotizacion))
        story.append(Spacer(1, 0.1*inch))
        
        # 6. Especificaciones técnicas
        story.extend(self._crear_especificaciones(cotizacion))
        story.append(Spacer(1, 0.15*inch))
        
        # 7. Pie de página
        story.extend(self._crear_pie_pagina())
        
        # Construir PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _crear_encabezado(self) -> list:
        """Crea encabezado con membrete INVEIN"""
        elements = []
        
        # Línea superior decorativa
        elements.append(Paragraph(
            f"<b>{self.LOGO_TEXT}</b>",
            self.styles['Header']
        ))
        
        # Información de la empresa
        empresa_str = f"""
        <font size="9" color="#666666">
        {self.EMPRESA_INFO['linea_negocio']} | 
        {self.EMPRESA_INFO['direccion']}<br/>
        Tel: {self.EMPRESA_INFO['telefono']} | 
        Email: {self.EMPRESA_INFO['email']}
        </font>
        """
        elements.append(Paragraph(empresa_str, self.styles['SubHeader']))
        
        # Línea separadora
        elements.append(Spacer(1, 0.05*inch))
        elements.append(Paragraph("<hr color='#F59E0B' width='100%'/>", self.styles['Normal']))
        
        return elements
    
    def _crear_titulo_fecha(self) -> list:
        """Crea título y datos de cotización"""
        elements = []
        
        hoy = datetime.now()
        vigencia = hoy + timedelta(days=15)
        
        titulo_data = f"""
        <b>COTIZACIÓN ELEVADOR DE CANGILONES</b><br/>
        <font size="9">Cotización No. {hoy.strftime('%Y%m%d%H%M')}</font><br/>
        <font size="8" color="#999999">
        Fecha: {hoy.strftime('%d de %B de %Y')} | 
        Válida hasta: {vigencia.strftime('%d de %B de %Y')}
        </font>
        """
        elements.append(Paragraph(titulo_data, ParagraphStyle(
            'TitleData',
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            alignment=0
        )))
        
        return elements
    
    def _crear_datos_cotizacion(self, modelo: str, material: str) -> list:
        """Crea tabla con parámetros de entrada"""
        elements = []
        
        elements.append(Paragraph("CONFIGURACIÓN TÉCNICA", self.styles['SectionTitle']))
        
        data = [
            ['Parámetro', 'Valor'],
            ['Modelo Elevador', modelo],
            ['Material de Lámina', material],
            ['Especificación', 'Cangilones'],
        ]
        
        table = Table(data, colWidths=[2*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        return elements
    
    def _crear_tabla_bom(self, cotizacion: CotizacionResult) -> list:
        """Crea tabla con desglose de BOM"""
        elements = []
        
        elements.append(Paragraph("DESGLOSE DE MATERIALES Y COMPONENTES", self.styles['SectionTitle']))
        
        # Encabezados
        data = [
            ['Parte', 'Material', 'Cant.', 'Costo Unit.', 'Costo Total', 'Precio Venta']
        ]
        
        # Filas de transformación
        for detalle in cotizacion.detalles_bom:
            if detalle['es_transformacion']:
                data.append([
                    detalle['parte'][:15],
                    detalle['material'][:12],
                    f"{detalle['cantidad']:.0f}",
                    f"${detalle['costo_unitario']:.2f}",
                    f"${detalle['costo_total']:.2f}",
                    f"${detalle['costo_venta']:.2f}"
                ])
        
        # Filas de suministros
        for detalle in cotizacion.detalles_bom:
            if not detalle['es_transformacion']:
                data.append([
                    detalle['parte'][:15],
                    detalle['material'][:12],
                    f"{detalle['cantidad']:.0f}",
                    f"${detalle['costo_unitario']:.2f}",
                    f"${detalle['costo_total']:.2f}",
                    f"${detalle['costo_venta']:.2f}"
                ])
        
        table = Table(data, colWidths=[1.2*inch, 1*inch, 0.6*inch, 1*inch, 1*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (2, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
        ]))
        
        elements.append(table)
        return elements
    
    def _crear_resumen_costos(self, cotizacion: CotizacionResult) -> list:
        """Crea tabla de resumen financiero"""
        elements = []
        
        elements.append(Paragraph("RESUMEN FINANCIERO", self.styles['SectionTitle']))
        
        # Tabla de totales
        data = [
            ['Concepto', 'Valor'],
            ['Subtotal Transformación', f"${cotizacion.subtotal_transformacion:,.2f}"],
            ['Subtotal Suministros', f"${cotizacion.subtotal_suministros:,.2f}"],
            ['SUBTOTAL NETO', f"${cotizacion.subtotal_neto:,.2f}"],
            ['TOTAL VENTA', f"${cotizacion.total_venta:,.2f}"],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 4), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _crear_especificaciones(self, cotizacion: CotizacionResult) -> list:
        """Crea tabla con especificaciones técnicas calculadas"""
        elements = []
        
        if not cotizacion.especificaciones or 'error' in cotizacion.especificaciones:
            return elements
        
        elements.append(Paragraph("ESPECIFICACIONES TÉCNICAS CALCULADAS", self.styles['SectionTitle']))
        
        spec = cotizacion.especificaciones
        data = [
            ['Parámetro', 'Valor'],
            ['Velocidad Lineal', f"{spec.get('velocidad_lineal_m_s', 0):.3f} m/s"],
            ['Capacidad', f"{spec.get('capacidad_ton_h', 0):.2f} Ton/h"],
            ['Potencia Requerida', f"{spec.get('potencia_hp', 0):.2f} HP"],
            ['Torque', f"{spec.get('torque_nm', 0):.2f} N·m"],
            ['Altura Elevación', f"{spec.get('altura_elevacion_m', 0):.2f} m"],
            ['RPM Operación', f"{spec.get('rpm_operacion', 0):.1f}"],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        return elements
    
    def _crear_pie_pagina(self) -> list:
        """Crea pie de página con términos y condiciones"""
        elements = []
        
        pie_texto = f"""
        <font size="7" color="#999999">
        <b>Términos y Condiciones:</b> Esta cotización es válida por 15 días calendario desde la fecha indicada. 
        Los precios están sujetos a cambios sin previo aviso. Se requiere pago del 50% como anticipo. 
        La entrega está condicionada a la confirmación de especificaciones finales.<br/>
        <b>Preparado por:</b> {self.usuario_comercial} | INVEIN S.A.S.
        </font>
        """
        
        elements.append(Paragraph(pie_texto, ParagraphStyle(
            'Footer',
            fontSize=7,
            textColor=colors.HexColor('#999999'),
            alignment=0
        )))
        
        return elements
