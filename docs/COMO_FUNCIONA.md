# Cómo funciona el extractor (guía para aprender)

Este documento explica **qué pasa por dentro** cuando ejecutas el extractor, y
los conceptos de IA que hay detrás. Léelo con [extractor.py](../extractor.py) y
[esquemas.py](../esquemas.py) abiertos al lado.

---

## 1. La idea general

Un modelo de lenguaje como Claude recibe **texto** y devuelve **texto**. Si le
pides "sácame los datos de esta factura", te contestará algo correcto pero
con un formato distinto cada vez: a veces una lista, a veces un párrafo, a
veces un JSON con nombres de campo diferentes.

Para usar la respuesta en un programa necesitas que **siempre** tenga la misma
forma. Eso es lo que resuelven las **salidas estructuradas** (*structured
outputs*): tú defines un esquema y la API garantiza que la respuesta lo cumple.

```text
 Tu texto  ──►  extractor.py  ──►  API de Claude  ──►  JSON válido  ──►  objeto Python
                     │                  ▲
                     └── esquema ───────┘
                    (esquemas.py)
```

---

## 2. Los conceptos clave

### API y API key

Una **API** es una puerta para que un programa hable con otro. La de Anthropic
recibe peticiones HTTP con tu texto y devuelve la respuesta de Claude.

La **API key** es tu contraseña para esa puerta: identifica tu cuenta y sirve
para cobrarte el uso. Por eso va en `.env` y nunca en el código.

### SDK

El **SDK** (la librería `anthropic`) se encarga de lo tedioso: construir la
petición HTTP, añadir la clave, reintentar si falla la red y convertir la
respuesta en objetos de Python. En vez de escribir HTTP a mano, haces:

```python
cliente = anthropic.Anthropic()
respuesta = cliente.messages.create(...)
```

`anthropic.Anthropic()` busca la clave automáticamente en la variable de
entorno `ANTHROPIC_API_KEY`. Por eso el programa llama primero a
`load_dotenv()`, que copia lo que hay en `.env` a las variables de entorno.

### Mensajes: `system` y `messages`

Una petición a Claude tiene dos partes de texto:

- **`system`**: instrucciones de comportamiento ("eres un extractor de datos,
  no inventes nada…"). Es como el manual de trabajo.
- **`messages`**: la conversación. Aquí solo hay un mensaje del usuario: el
  texto a procesar.

Separarlos tiene una ventaja: el texto del usuario nunca se mezcla con tus
instrucciones.

### Tokens

Los modelos no leen letras ni palabras, leen **tokens** (trozos de unas 3-4
letras de media). Pagas por los tokens que **entran** (tu texto + instrucciones
+ esquema) y por los que **salen** (la respuesta). `max_tokens=16000` es el
límite de salida: si la respuesta lo alcanza, se corta.

### Modelos

Anthropic ofrece varios modelos con distinta potencia y precio:

- **Opus**: el más capaz de uso general. Es el que usa el programa por defecto.
- **Sonnet**: equilibrio entre velocidad y capacidad.
- **Haiku**: el más rápido y barato. Ideal para tareas sencillas como esta.

Merece la pena probar el mismo texto con varios modelos y comparar los resultados.

### Esfuerzo (*effort*)

Los modelos actuales "piensan" antes de responder. El parámetro
`output_config={"effort": "low"}` les dice que esta tarea es sencilla y que no
hace falta pensar mucho: la respuesta llega antes y cuesta menos. Para
problemas difíciles subirías a `"medium"`, `"high"` o más.

---

## 3. Recorrido por el código

### `esquemas.py`: la forma del JSON

```python
class Contacto(BaseModel):
    nombre: str = Field(description="Nombre completo de la persona")
    email: str | None = Field(description="Correo electrónico, o null si no aparece")
```

- `BaseModel` viene de **Pydantic**, una librería que valida datos.
- `str` significa "obligatorio, texto". `str | None` significa "texto **o**
  nada": así Claude puede decir "este dato no aparece" en vez de inventárselo.
- `description` no es solo un comentario: **se envía a Claude** y le ayuda a
  entender qué va en cada campo. Mejorar estas descripciones es una forma de
  mejorar los resultados. A eso se le llama *prompt engineering*.
- `Literal["positivo", "neutral", "negativo"]` obliga a elegir uno de esos tres
  valores exactos.

### `extractor.py` → `extraer()`: la llamada a la IA

```python
respuesta = cliente.beta.messages.parse(
    model=modelo,
    max_tokens=16000,
    system=INSTRUCCIONES,
    messages=[{"role": "user", "content": texto}],
    output_format=esquema,
    output_config={"effort": "low"},
    **extra,
)
```

- `messages.parse(...)` es como `messages.create(...)`, pero además convierte
  tu clase de Pydantic en un *JSON Schema*, se lo envía a la API y valida la
  respuesta. El resultado queda en `respuesta.parsed_output`, ya como objeto
  `Contacto`, `Factura` o `Resena`.
- `output_format=esquema` es la clave de todo: obliga a que la respuesta tenga
  esa estructura.
- `**extra` añade, solo en Opus y Sonnet, un "plan B" del servidor
  (`fallbacks`): si el modelo rechaza la petición por sus filtros de seguridad,
  la API la reintenta automáticamente con otro modelo. Usamos `.beta` porque
  esa función todavía está en beta.

### Comprobar *por qué* terminó la respuesta

```python
if respuesta.stop_reason == "refusal":
    raise ExtraccionError("El modelo se negó a procesar este texto.")
if respuesta.stop_reason == "max_tokens":
    raise ExtraccionError("La respuesta se cortó por longitud (max_tokens).")
```

Esta es una de las lecciones más importantes al trabajar con IA: **nunca des por
hecho que la respuesta está completa**. `stop_reason` dice por qué paró el
modelo:

| `stop_reason` | Qué significa                                  |
|---------------|------------------------------------------------|
| `end_turn`    | Terminó con normalidad                         |
| `max_tokens`  | Se quedó sin espacio y la respuesta está cortada |
| `refusal`     | Se negó por motivos de seguridad               |

### `main()`: la línea de comandos y los errores

`argparse` convierte `--tipo factura ejemplos/factura.txt` en variables de
Python. Después viene una cadena de `except`, **de la más específica a la más
general**, porque no todos los errores se arreglan igual:

- `AuthenticationError` → la clave está mal. Reintentar no sirve.
- `RateLimitError` → demasiadas peticiones seguidas. Toca esperar.
- `APIConnectionError` → no hay internet.

El SDK ya reintenta solo los errores temporales, como los de red o los 429
(hasta 2 veces).

---

## 4. Las pruebas: probar IA sin gastar dinero

[tests/test_extractor.py](../tests/test_extractor.py) usa un `ClienteFalso` que
imita al de Anthropic. La función `extraer()` acepta un `cliente` como
parámetro precisamente para poder sustituirlo en las pruebas. A esta técnica
se le llama **inyección de dependencias**.

Así comprobamos nuestra lógica (qué hacemos con `refusal`, con un tipo
desconocido, si se guarda bien el archivo…) sin conexión y sin coste.

Lo que estas pruebas **no** comprueban es la *calidad* de lo que extrae
Claude. Para eso habría que montar una **evaluación** (*eval*): un conjunto de
textos con su respuesta correcta conocida, y medir cuántos acierta cada modelo.
Es un buen siguiente paso.

---

## 5. Ideas para seguir practicando

Ordenadas de más fácil a más difícil:

1. **Mejora las descripciones** de `esquemas.py` y observa cómo cambian los
   resultados.
2. **Crea un tipo nuevo**: receta, oferta de empleo, ticket de soporte, CV…
3. **Compara modelos**: pasa el mismo texto por Haiku, Sonnet y Opus.
4. **Procesa una carpeta entera** de archivos y guarda un JSON por cada uno, o
   un CSV con todos.
5. **Lee PDFs o imágenes**: la API acepta documentos y fotos directamente (por
   ejemplo, la foto de un ticket de compra).
6. **Construye una eval**: 10-20 textos con su JSON correcto y un script que
   calcule el porcentaje de aciertos.
7. **Mide el coste**: `respuesta.usage.input_tokens` y `output_tokens` dicen
   cuántos tokens gastó cada petición. Muestra el coste estimado al final.

---

## Glosario rápido

| Término                | Significado                                                        |
|------------------------|--------------------------------------------------------------------|
| **LLM**                | *Large Language Model*: modelo de lenguaje como Claude              |
| **Prompt**             | El texto/instrucciones que le das al modelo                         |
| **Token**              | Unidad de texto que procesa el modelo (y por la que se paga)        |
| **Structured outputs** | Forzar que la respuesta cumpla un esquema JSON                      |
| **JSON Schema**        | Formato estándar para describir la forma de un JSON                 |
| **SDK**                | Librería oficial que simplifica el uso de la API                    |
| **Effort**             | Cuánto "piensa" el modelo antes de responder                        |
| **Eval**               | Conjunto de pruebas para medir la calidad de las respuestas de la IA |
