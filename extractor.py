"""
Extractor de datos a JSON con Claude.

Lee un texto desordenado (un correo, una factura, una reseña...) y devuelve
sus datos como JSON estructurado según uno de los esquemas de esquemas.py.

Uso rápido:
    python extractor.py --tipo factura ejemplos/factura.txt
    python extractor.py --tipo contacto --texto "Soy Ana Ruiz, ana@acme.com"
    cat ejemplos/resena.txt | python extractor.py --tipo resena

Consulta README.md para la guía completa.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from esquemas import ESQUEMAS

# Modelo por defecto. Se puede cambiar con --modelo o con la variable de
# entorno CLAUDE_MODEL (por ejemplo, claude-haiku-5-5 es mucho más barato).
MODELO_POR_DEFECTO = "claude-opus-5-5"

# Modelos que admiten el "plan B" automático del servidor (fallbacks): si el
# modelo rechaza la petición por seguridad, la API la reintenta con otro.
MODELOS_CON_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}

# Instrucciones de sistema: le dicen a Claude cómo comportarse.
INSTRUCCIONES = (
    "Eres un extractor de datos. Lee el texto del usuario y rellena los campos "
    "del esquema con la información que aparece en él. "
    "No inventes datos: si un campo no aparece en el texto, usa null "
    "(o una lista vacía si es una lista). "
    "Responde en el mismo idioma que el texto original."
)


class ExtraccionError(Exception):
    """La IA no pudo devolver un resultado válido."""


def extraer(
    texto: str,
    tipo: str,
    modelo: str = MODELO_POR_DEFECTO,
    cliente: anthropic.Anthropic | None = None,
) -> BaseModel:
    """Envía el texto a Claude y devuelve un objeto Pydantic ya validado."""
    if tipo not in ESQUEMAS:
        raise ValueError(f"Tipo desconocido: {tipo!r}. Opciones: {', '.join(ESQUEMAS)}")
    if not texto.strip():
        raise ValueError("El texto está vacío.")

    esquema = ESQUEMAS[tipo]
    cliente = cliente or anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno

    # Parámetros extra solo para los modelos que admiten fallback.
    extra = {}
    if modelo in MODELOS_CON_FALLBACK:
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    respuesta = cliente.beta.messages.parse(
        model=modelo,
        max_tokens=16000,
        system=INSTRUCCIONES,
        messages=[{"role": "user", "content": texto}],
        output_format=esquema,  # <- aquí se fuerza la estructura del JSON
        output_config={"effort": "low"},  # tarea sencilla: poco "pensar" = más rápido y barato
        **extra,
    )

    # Siempre hay que mirar POR QUÉ terminó la respuesta antes de usarla.
    if respuesta.stop_reason == "refusal":
        raise ExtraccionError("El modelo se negó a procesar este texto.")
    if respuesta.stop_reason == "max_tokens":
        raise ExtraccionError("La respuesta se cortó por longitud (max_tokens).")
    if respuesta.parsed_output is None:
        raise ExtraccionError("La respuesta no contenía un JSON válido.")

    return respuesta.parsed_output


def leer_entrada(args: argparse.Namespace) -> str:
    """Obtiene el texto desde --texto, un archivo, o la entrada estándar."""
    if args.texto is not None:
        return args.texto
    if args.archivo is not None:
        return Path(args.archivo).read_text(encoding="utf-8")
    if not sys.stdin.isatty():  # se le pasó algo con una tubería (|)
        return sys.stdin.read()
    raise SystemExit("Indica un archivo, usa --texto \"...\", o pasa texto por una tubería.")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()  # carga las variables del archivo .env si existe

    parser = argparse.ArgumentParser(description="Extrae datos de un texto a JSON usando Claude.")
    parser.add_argument("archivo", nargs="?", help="Archivo de texto a procesar")
    parser.add_argument("-t", "--tipo", required=True, choices=ESQUEMAS.keys(), help="Qué datos extraer")
    parser.add_argument("--texto", help="Texto a procesar directamente (en vez de un archivo)")
    parser.add_argument("-o", "--salida", help="Guardar el JSON en este archivo")
    parser.add_argument(
        "-m", "--modelo",
        default=os.getenv("CLAUDE_MODEL", MODELO_POR_DEFECTO),
        help=f"Modelo de Claude (por defecto: {MODELO_POR_DEFECTO})",
    )
    args = parser.parse_args(argv)

    try:
        texto = leer_entrada(args)
        resultado = extraer(texto, args.tipo, modelo=args.modelo)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ExtraccionError as e:
        print(f"No se pudo extraer: {e}", file=sys.stderr)
        return 2
    except TypeError as e:
        # El SDK lanza TypeError si no encuentra ninguna credencial configurada.
        if "authentication" not in str(e):
            raise
        print("No hay API key configurada. Crea el archivo .env (ver .env.example).", file=sys.stderr)
        return 3
    except anthropic.AuthenticationError:
        print("API key inválida. Revisa ANTHROPIC_API_KEY en tu archivo .env", file=sys.stderr)
        return 3
    except anthropic.RateLimitError:
        print("Demasiadas peticiones. Espera un poco y vuelve a intentarlo.", file=sys.stderr)
        return 3
    except anthropic.APIStatusError as e:
        print(f"Error de la API ({e.status_code}): {e.message}", file=sys.stderr)
        return 3
    except anthropic.APIConnectionError:
        print("No se pudo conectar con la API. Revisa tu conexión a internet.", file=sys.stderr)
        return 3

    salida_json = json.dumps(resultado.model_dump(), ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).write_text(salida_json + "\n", encoding="utf-8")
        print(f"Guardado en {args.salida}")
    else:
        print(salida_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
