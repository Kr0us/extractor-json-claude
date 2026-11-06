"""
Pruebas del extractor. NO llaman a la API real (no gastan dinero ni
necesitan API key): usan un cliente "falso" que imita la respuesta de Claude.

Ejecutar:  python -m pytest
"""

from types import SimpleNamespace

import pytest

import extractor
from esquemas import ESQUEMAS, Contacto


class ClienteFalso:
    """Imita anthropic.Anthropic() lo justo para las pruebas."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.ultima_peticion = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.ultima_peticion = kwargs
        return self.respuesta


def respuesta(parsed, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)


CONTACTO = Contacto(
    nombre="Ana Ruiz", email="ana@acme.com", telefono=None,
    empresa="Acme", cargo=None, motivo="Pide presupuesto",
)


def test_extraccion_correcta_envia_el_esquema_adecuado():
    cliente = ClienteFalso(respuesta(CONTACTO))
    resultado = extractor.extraer("Soy Ana de Acme", "contacto", cliente=cliente)

    assert resultado.nombre == "Ana Ruiz"
    assert cliente.ultima_peticion["output_format"] is Contacto
    assert cliente.ultima_peticion["messages"][0]["content"] == "Soy Ana de Acme"


def test_opus_activa_fallback_y_haiku_no():
    cliente = ClienteFalso(respuesta(CONTACTO))
    extractor.extraer("x", "contacto", modelo="claude-opus-5-5", cliente=cliente)
    assert cliente.ultima_peticion["fallbacks"] == "default"

    extractor.extraer("x", "contacto", modelo="claude-haiku-5-5", cliente=cliente)
    assert "fallbacks" not in cliente.ultima_peticion


@pytest.mark.parametrize("motivo", ["refusal", "max_tokens"])
def test_errores_de_parada(motivo):
    cliente = ClienteFalso(respuesta(CONTACTO, stop_reason=motivo))
    with pytest.raises(extractor.ExtraccionError):
        extractor.extraer("x", "contacto", cliente=cliente)


def test_sin_json_valido():
    cliente = ClienteFalso(respuesta(None))
    with pytest.raises(extractor.ExtraccionError):
        extractor.extraer("x", "contacto", cliente=cliente)


def test_tipo_desconocido_y_texto_vacio():
    with pytest.raises(ValueError):
        extractor.extraer("x", "pasaporte", cliente=ClienteFalso(None))
    with pytest.raises(ValueError):
        extractor.extraer("   ", "contacto", cliente=ClienteFalso(None))


def test_todos_los_esquemas_generan_json_schema():
    for nombre, esquema in ESQUEMAS.items():
        schema = esquema.model_json_schema()
        assert schema["type"] == "object", nombre


def test_cli_guarda_archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor, "extraer", lambda texto, tipo, modelo: CONTACTO)
    entrada = tmp_path / "entrada.txt"
    entrada.write_text("Soy Ana", encoding="utf-8")
    salida = tmp_path / "salida.json"

    codigo = extractor.main([str(entrada), "--tipo", "contacto", "-o", str(salida)])

    assert codigo == 0
    assert '"nombre": "Ana Ruiz"' in salida.read_text(encoding="utf-8")
