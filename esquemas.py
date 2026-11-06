"""
Esquemas: la "forma" del JSON que queremos que devuelva la IA.

Cada clase es un modelo de Pydantic. El SDK de Anthropic convierte estas
clases en un JSON Schema y se lo envía a Claude, que queda obligado a
responder con un JSON que cumpla exactamente esa estructura.

Para añadir un tipo nuevo de extracción:
  1. Crea una clase aquí (hereda de BaseModel).
  2. Regístrala en el diccionario ESQUEMAS de abajo.
"""

from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Contacto: datos de una persona sacados de un correo, firma, mensaje...
# --------------------------------------------------------------------------
class Contacto(BaseModel):
    nombre: str = Field(description="Nombre completo de la persona")
    email: str | None = Field(description="Correo electrónico, o null si no aparece")
    telefono: str | None = Field(description="Teléfono tal como aparece, o null")
    empresa: str | None = Field(description="Empresa u organización, o null")
    cargo: str | None = Field(description="Puesto o cargo, o null")
    motivo: str | None = Field(description="Por qué escribe, resumido en una frase, o null")


# --------------------------------------------------------------------------
# Factura: datos de una factura o recibo
# --------------------------------------------------------------------------
class LineaFactura(BaseModel):
    descripcion: str
    cantidad: float
    precio_unitario: float


class Factura(BaseModel):
    numero: str | None = Field(description="Número o identificador de la factura, o null")
    fecha: str | None = Field(description="Fecha de emisión en formato AAAA-MM-DD, o null")
    emisor: str = Field(description="Quién emite la factura (vendedor)")
    cliente: str | None = Field(description="A quién se le factura, o null")
    lineas: list[LineaFactura] = Field(description="Cada producto o servicio facturado")
    subtotal: float | None = Field(description="Importe antes de impuestos, o null")
    impuestos: float | None = Field(description="Importe total de impuestos, o null")
    total: float = Field(description="Importe total a pagar")
    moneda: str = Field(description="Código de moneda ISO 4217, por ejemplo EUR, USD, MXN")


# --------------------------------------------------------------------------
# Reseña: opinión de un cliente sobre un producto o servicio
# --------------------------------------------------------------------------
class Resena(BaseModel):
    producto: str | None = Field(description="Producto o servicio reseñado, o null")
    puntuacion: int = Field(description="Puntuación estimada del 1 (muy mala) al 5 (excelente)")
    sentimiento: Literal["positivo", "neutral", "negativo"]
    puntos_positivos: list[str] = Field(description="Lo que le gustó, en frases cortas")
    puntos_negativos: list[str] = Field(description="Lo que no le gustó, en frases cortas")
    resumen: str = Field(description="Resumen de la reseña en una frase")


# Nombre que se usa en la línea de comandos  ->  clase del esquema
ESQUEMAS: dict[str, type[BaseModel]] = {
    "contacto": Contacto,
    "factura": Factura,
    "resena": Resena,
}
