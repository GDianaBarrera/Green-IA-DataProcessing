# Green AI — Data Processing

Servicio interno FastAPI para históricos de Monitoring, lectura paginada de Supabase
y preparación de CPU para Prediction. Conserva el ETL Excel existente.

## Ejecutar y verificar

Desde `data-processing-service`, con Python 3.14 y un entorno virtual:

```powershell
python -m pip install -r requirements.txt
$env:MONITORING_BASE_URL = 'http://localhost:8080'
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Swagger: `http://127.0.0.1:8001/docs`. Salud: `/api/v1/health`.
Las variables se leen del entorno al iniciar. FastAPI no carga `.env` automáticamente.

```powershell
python -m pytest -q
python scripts/export_openapi.py
```

Contrato versionado: `contracts/data-processing-v1.openapi.json`.
Errores y respuestas HTTP se prueban con dobles de transporte; eso no acredita conexión real.

## Operaciones

- `GET /api/v1/metrics/history`: `metric`, `start`, `end`, `resourceType=node`,
  `cluster`, `resourceId`, `stepSeconds=15`. Zona obligatoria, segundos enteros,
  inicio anterior al final, sin futuro, máximo 24 horas; paso de 15 a 3600.
  Conserva metadatos, periodo, paso, warnings, labels, origen y calidad.
- `GET /api/v1/historical-logs`: `hardwareId`, `start`, `end`, `limit=100`, `cursor`.
  Máximo 31 días, zona obligatoria, precisión de microsegundos conservada.
  Solo selecciona `log_id,hardware_id,timestamp,cpu_utilization_pct,ram_utilization_pct,temperatura_celsius,energia_watts`.
  El filtro y el límite se aplican en Supabase, sin cargar toda la tabla.
- `GET /api/v1/prediction/dataset`: `start`, `end`, `cluster`, `resourceId`,
  `stepSeconds=15`. Prepara una sola serie de CPU desde Monitoring: ratio a %.
  **Contrato provisional; no llama a un modelo ni produce predicciones.**
  Expone periodo solicitado/efectivo, muestras excluidas, unidades y advertencias.

Ejemplo de consulta (sustituir fechas por un periodo disponible en la fuente):

```text
/api/v1/metrics/history?metric=node.cpu.utilization&start=2026-09-21T15:00:00Z&end=2026-09-21T16:00:00Z&stepSeconds=15
/api/v1/historical-logs?hardwareId=HW-01&start=2026-09-21T15:00:00Z&end=2026-09-21T16:00:00Z&limit=100
```

## Política de datos

Monitoring se valida antes de crear DataFrames. Cero válido sigue siendo cero;
missing/non_finite requieren null. Contratos inválidos, timestamps inválidos y duplicados
contradictorios fallan con 502. Duplicados idénticos por identidad completa y timestamp
se eliminan con advertencia. Se ordenan las muestras por serie, conservando huecos,
sin imputación, remuestreo ni agregación entre interfaces, nodos o clústeres.

Prediction excluye muestras no utilizables, rechaza mezcla de procedencias, múltiples
recursos/series y CPU fuera de [0,1]. Las features son porcentajes y conservan el cero.
El consumidor debe acordar cadencia, mínimo de muestras y horizonte antes de inferir.

Supabase conserva CPU/RAM en %, temperatura en degC y `energia_watts` como potencia W.
No consulta `prediccion_watts`, usuarios ni contraseñas. Valores ausentes, no finitos
o porcentajes fuera de rango se señalan con calidad y null, sin inventar mediciones.
El origen permanece `unknown`; el esquema no acredita procedencia ni clúster.
No se mezclan fuentes ni se infiere un mapeo hardware/nodo.

La paginación usa `(timestamp, log_id)` ascendente y cursor vinculado a hardware/periodo.
Mantener exactamente los mismos filtros al continuar; máximo 500 filas por petición.
Cada página no vacía devuelve `partial` y `nextCursor`, incluso si tiene menos filas
que el límite: Supabase puede imponer su propio tope. Continuar hasta una página vacía,
`no_data`, sin cursor. No se asegura un snapshot: inserciones tardías o modificaciones
durante la lectura pueden requerir repetir la consulta. El cursor no es autorización.

## Configuración

`MONITORING_BASE_URL` usa `http://localhost:8080` en ejecución local y debe ser
`http://monitoring:8080` dentro de Docker. `REQUEST_TIMEOUT_SECONDS=10` debe ser
finito y mayor que 0, máximo 120. Configuración inválida impide el arranque.

Supabase está deshabilitado por defecto y su ruta devuelve 503 `SOURCE_NOT_CONFIGURED`.
Para habilitarlo, configurar `SUPABASE_ENABLED=true`, `SUPABASE_URL` HTTPS,
`SUPABASE_API_KEY` y `SUPABASE_READ_TOKEN`. El token debe corresponder a una identidad
de servidor con permisos mínimos de lectura de las columnas seleccionadas de `logs`.
No usar el token del usuario ni una clave amplia como sustituto de permisos revisados.
`HISTORICAL_MAX_PAGE_SIZE=500` admite 1..500; solicitar un límite no mayor al configurado.
No versionar secretos. El código no crea tablas, no modifica RLS y no hace escrituras.

## Errores y correlación

Todos los errores documentados usan `application/problem+json`, `code`, `status`,
`detail`, `instance` y `requestId`. No devuelven cuerpos upstream ni datos de conexión.

- 422 `INVALID_QUERY`: parámetros, fechas, límites o dataset no utilizable.
- 502 `UPSTREAM_INVALID_RESPONSE`: JSON, esquema o semántica de fuente inválidos.
- 503 `SOURCE_UNAVAILABLE`: fallo de conexión/disponibilidad.
- 503 `SOURCE_NOT_CONFIGURED`: Supabase deshabilitado.
- 503 `SOURCE_ACCESS_DENIED`: la identidad del servicio no puede leer Supabase.
- 504 `SOURCE_TIMEOUT`: timeout local o informado por la fuente.
- 500 `INTERNAL_ERROR`: error inesperado con detalle seguro.

`X-Request-Id` admite 1..128 caracteres alfanuméricos y `._:-`; si falta o es inválido,
se genera UUID. Se envía a ambas fuentes y se devuelve al cliente. No hay fallback
entre fuentes ni reintentos implícitos; un fallo no se presenta como datos vacíos.

## Docker y Gateway

### Arranque local sin Supabase

Con Docker Desktop iniciado, ejecutar desde `data-processing-service`:

```powershell
docker compose -f compose.local.yaml up -d --build --wait
```

Abrir `http://localhost:8001/docs`. Este modo crea su propia red, publica el puerto
solo en localhost. Supabase queda deshabilitado por defecto; se habilita con las
variables SUPABASE del entorno o `.env`. Monitoring se busca en el host
en 8080 mediante `host.docker.internal`; si no está ejecutándose, las consultas de
Monitoring devuelven 503 y la salud del servicio sigue disponible.
No requiere copiar `.env` ni crear redes manualmente. Para parar únicamente este servicio:

```powershell
docker compose -f compose.local.yaml down
```

Si las credenciales están solo en la sesión de PowerShell donde se probó Supabase,
guardarlas desde **esa misma sesión** sin copiarlas al chat:

```powershell
& .\scripts\Save-LocalConfig.ps1
docker compose --env-file .env -f compose.local.yaml up -d --build --wait
```

El script rechaza marcadores como `<TU_ACCESS_TOKEN>` y no sobrescribe un `.env`
existente. Un valor por línea; `HISTORICAL_MAX_PAGE_SIZE=500` sin coma final.
La clave publishable identifica la aplicación, no reemplaza el JWT de lectura
dedicado. Conectar una extensión de VS Code no configura automáticamente el contenedor.
Guardar las credenciales tampoco comprueba sus permisos efectivos de solo lectura.

### Verificación completa del contenedor

```powershell
& .\scripts\Test-Docker.ps1
```

El script comprueba el motor, valida ambos Compose, construye la imagen Python 3.14,
ejecuta la suite y prueba HTTP entre contenedores con una fuente Monitoring **sintética**
aislada. Valida cero/null, metadatos, request ID, preparación provisional y el 503
de Supabase deshabilitado. Monta el Excel sintético existente en solo lectura para
las pruebas ETL; no incluye datasets en la imagen. Elimina únicamente los contenedores
y la red temporales creados en esa ejecución. Conserva la imagen con un tag único.
Un fallo detiene la verificación: no se informa éxito si falla build, pytest o HTTP.

La imagen corre como usuario sin privilegios y tiene healthcheck propio.
`.dockerignore` excluye archivos de entorno, claves y datasets.

### Conectar con la red del equipo

```powershell
docker build -t green-ai-data-processing:local .
docker compose --env-file .env up -d --build
```

`compose.yaml` usa la red externa `${GREENAI_NETWORK:-greenai-net}` existente y
expone 8000 solo dentro de esa red. Monitoring y Gateway deben pertenecer a ella;
el servicio de Monitoring debe resolver como `monitoring` o configurar su URL.
El contenedor escucha en 0.0.0.0:8000 fijo; no hay variables HOST/PORT ignoradas.
El navegador consume Gateway; no publicar este servicio directamente en Internet.
La salud comprueba el proceso, no la disponibilidad de las fuentes.

Gateway debe registrar explícitamente cada ruta con permisos OPERATOR/ADMIN:

```text
GET /api/processing/v1/metrics/history -> /api/v1/metrics/history
GET /api/processing/v1/historical-logs -> /api/v1/historical-logs
GET /api/processing/v1/prediction/dataset -> /api/v1/prediction/dataset (provisional)
```

Validar JWT de Supabase en Gateway; preservar query, estado, cuerpo y request ID.
`hardwareId` no implementa aislamiento por usuario. Antes de prometerlo se necesita
una política de autorización por hardware. CORS se configura en Gateway.

## Estado de integración — 2026-09-24

Base original: 24 pruebas aprobadas con las dependencias fijadas, Python 3.12.14
aislado. Windows impidió ejecutar el Python 3.14 del entorno virtual existente.
Ver `docs/integration-status.md` para evidencia final y dependencias externas.
La imagen Python 3.14 conserva su Dockerfile; no afirmar que fue ejecutada sin
construirla. El acceso al daemon Docker está bloqueado en esta sesión.
