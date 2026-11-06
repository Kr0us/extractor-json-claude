# Extractor de datos a JSON con Claude

Herramienta de línea de comandos que toma **texto desordenado** (un correo, una
factura, una reseña…) y devuelve sus datos como **JSON estructurado**, usando la
API de Claude.

```text
FACTURA Nº 2026-0147                         {
Fecha: 3 de noviembre de 2026                  "numero": "2026-0147",
Papelería El Lápiz S.L.          ──────►       "fecha": "2026-11-03",
- 10 cuadernos A4 .... 2,50 € c/u              "emisor": "Papelería El Lápiz S.L.",
...                                            "lineas": [ ... ],
TOTAL: 106,48 €                                "total": 106.48,
                                               "moneda": "EUR"
                                             }
```

Es un proyecto pensado para **aprender a trabajar con IA**: el código es corto
y está comentado. Si quieres entender cómo funciona por dentro, lee
[docs/COMO_FUNCIONA.md](docs/COMO_FUNCIONA.md).

---

## Qué puede extraer

| Tipo       | Para qué sirve                      | Campos principales                                    |
|------------|-------------------------------------|-------------------------------------------------------|
| `contacto` | Correos, firmas, mensajes           | nombre, email, teléfono, empresa, cargo, motivo       |
| `factura`  | Facturas y recibos                  | número, fecha, emisor, cliente, líneas, total, moneda |
| `resena`   | Opiniones de clientes               | puntuación 1-5, sentimiento, puntos +/-, resumen      |

Puedes añadir los tuyos (ver [Añadir un tipo nuevo](#añadir-un-tipo-nuevo)).

---

## Requisitos

- Python 3.10 o superior
- Una **API key de Anthropic**. Se crea en <https://platform.claude.com/> y se
  factura aparte de la suscripción de Claude.

---

## Instalación

```bash
git clone https://github.com/Kr0us/extractor-json-claude.git
cd extractor-json-claude

# 1. Crear un entorno virtual (una "caja" aislada para las librerías del proyecto)
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar tu API key
cp .env.example .env
nano .env        # pega tu clave en ANTHROPIC_API_KEY
```

> **Ubuntu/WSL:** si `python3 -m venv` falla con *"ensurepip is not available"*,
> instala el paquete que falta y repite el paso 1:
> `sudo apt install python3-venv` (o `python3.14-venv`, según tu versión).

Cada vez que abras una terminal nueva, activa el entorno con
`source .venv/bin/activate` antes de usar el extractor.

---

## Uso

**Desde un archivo:**

```bash
python extractor.py --tipo factura ejemplos/factura.txt
```

**Con texto directo:**

```bash
python extractor.py --tipo contacto --texto "Soy Ana Ruiz, de Acme. Mi correo es ana@acme.com"
```

**Por tubería (útil para combinar con otros comandos):**

```bash
cat ejemplos/resena.txt | python extractor.py --tipo resena
```

**Guardar el resultado en un archivo:**

```bash
python extractor.py --tipo factura ejemplos/factura.txt -o salida.json
```

### Opciones

| Opción            | Descripción                                                    |
|-------------------|----------------------------------------------------------------|
| `archivo`         | Archivo de texto a procesar (opcional si usas `--texto` o una tubería) |
| `-t`, `--tipo`    | **Obligatorio.** `contacto`, `factura` o `resena`              |
| `--texto "..."`   | Texto a procesar directamente                                  |
| `-o`, `--salida`  | Guardar el JSON en un archivo en vez de mostrarlo              |
| `-m`, `--modelo`  | Modelo de Claude a usar (por defecto `claude-opus-5-5`)        |

### Elegir modelo (y coste)

Por defecto se usa **Claude Opus 5.5**. Para practicar, **Claude Haiku 5.5**
cuesta mucho menos y extrae bien textos sencillos como estos:

```bash
python extractor.py --tipo factura ejemplos/factura.txt --modelo claude-haiku-5-5
```

O déjalo fijo en tu `.env` con `CLAUDE_MODEL=claude-haiku-5-5`.

| Modelo             | Entrada / salida (por millón de tokens) | Una factura de ejemplo (aprox.) |
|--------------------|-----------------------------------------|---------------------------------|
| `claude-opus-5-5`  | $4 / $20                                | ~1 céntimo                      |
| `claude-haiku-5-5` | $0.10 / $0.50                           | mucho menos de 1 céntimo        |

*(Cifras orientativas: el coste real depende de la longitud del texto. Puedes
ver tu gasto en la consola de Anthropic.)*

### Códigos de salida

| Código | Significado                                                   |
|--------|---------------------------------------------------------------|
| `0`    | Todo bien                                                     |
| `1`    | Problema con la entrada (archivo no existe, texto vacío…)     |
| `2`    | La IA no pudo devolver un resultado válido                    |
| `3`    | Problema con la API (clave, límite de peticiones, conexión…)  |

---

## Añadir un tipo nuevo

1. Abre [esquemas.py](esquemas.py) y crea una clase con los campos que quieras:

   ```python
   class Receta(BaseModel):
       nombre: str
       raciones: int | None = Field(description="Número de raciones, o null")
       ingredientes: list[str]
       pasos: list[str]
   ```

2. Regístrala al final del archivo:

   ```python
   ESQUEMAS = {
       ...
       "receta": Receta,
   }
   ```

3. Úsala con `--tipo receta`. No hay que tocar nada más.

---

## Pruebas

Las pruebas usan un cliente falso, así que **no gastan dinero ni necesitan API key**:

```bash
python -m pytest
```

---

## Estructura del proyecto

```text
.
├── extractor.py          # Programa principal: llama a Claude y gestiona la línea de comandos
├── esquemas.py           # Qué campos extraer en cada tipo (modelos de Pydantic)
├── ejemplos/             # Textos de prueba
├── tests/                # Pruebas automáticas
├── docs/COMO_FUNCIONA.md # Explicación de los conceptos para aprender
├── requirements.txt      # Librerías necesarias
└── .env.example          # Plantilla de configuración (copiar como .env)
```

---

## Seguridad

- **Nunca subas tu archivo `.env`** ni pegues tu API key en el código. El
  `.gitignore` ya lo excluye.
- Si crees que tu clave se ha filtrado, revócala en la consola de Anthropic y
  crea otra.
- El texto que procesas se envía a la API de Anthropic. No le pases datos
  sensibles que no debas compartir.
