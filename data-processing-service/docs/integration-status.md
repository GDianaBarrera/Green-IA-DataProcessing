# Entrega de integración — 2026-09-24

## Cambios locales

Se completan validación temporal, contrato de Monitoring, preservación de metadatos,
errores seguros, correlación, configuración al arranque, lectura paginada de Supabase
y API provisional para preparar CPU. Se conserva el ETL de Excel y los puertos previos.
El OpenAPI exportado es el contrato de esta entrega. No se han publicado commits.

## Evidencia

Las 24 pruebas originales pasaron antes de conectar los cambios nuevos.
Resultado final: 77 pruebas de la suite completa aprobadas, más 3 comprobaciones
adicionales aprobadas de Supabase habilitado, filtros de respuesta y OpenAPI (80 en total).
`git diff --check` sin errores. Dos advertencias de deprecación de Starlette/httpx;
no afectan al resultado. No se cambiaron dependencias para ocultarlas.
La suite ampliada cubre HTTP mediante TestClient y MockTransport, errores upstream,
fechas, cero/null, duplicados, paginación con timestamps repetidos, límites, unidades,
secretos excluidos, permisos y errores a mitad de lectura. Las respuestas son fixtures
explícitos de pruebas, no evidencia de métricas reales ni de precisión predictiva.

Entorno: Windows, Python 3.12.14 aislado y versiones de requirements.txt.
El ejecutable Python 3.14 instalado devuelve Acceso denegado; no se modificó ese entorno.
Docker devolvió permiso denegado al conectarse a su named pipe; falta construir y
probar el contenedor Python 3.14 en el entorno del equipo.

Actualización Docker: ambos archivos Compose pasaron `docker compose ... config --quiet`.
El script `scripts/Test-Docker.ps1` pasó el análisis sintáctico de PowerShell.
El smoke HTTP pasó ejecutando la API y la fuente sintética como procesos locales
aislados; esto valida el script HTTP pero no sustituye ejecutar contenedores.
`compose.local.yaml` permite arrancar sin red externa ni credenciales. La imagen usa
usuario sin privilegios y healthcheck. La suite Docker monta solo el Excel sintético
en lectura; sus pruebas CSV escriben en un directorio temporal, no dentro de /app.
El motor Docker sigue devolviendo acceso denegado aun tras solicitar los permisos de
sesión. Build, suite en Python 3.14 y tráfico Docker no están certificados todavía.
El usuario confirmó que no hay credenciales: Supabase permanece preparado/deshabilitado.

## Revisión posterior con Supabase y confirmación de Docker

Verificación local final: 86 pruebas aprobadas (Python 3.12.14), Compose local validado
con SUPABASE_ENABLED=true y credenciales ficticias transmitidas correctamente, script
de guardado probado con datos ficticios y bloqueo de sobrescritura comprobado.
`git diff --check` sin errores; solo `.env.example` está versionado entre los archivos
de entorno. No se guardaron en el repositorio las credenciales aportadas en el chat.

El usuario informó que `Test-Docker.ps1` terminó con OK y que configuró Supabase en
variables temporales de su propia sesión PowerShell. Ese resultado Docker se registra
como evidencia comunicada por el usuario; esta sesión sigue sin acceso al named pipe.
La sesión del agente no hereda las variables de otro PowerShell. No hay `.env` local
en el servicio al revisar. `Save-LocalConfig.ps1` permite persistirlas desde esa sesión
sin imprimir valores, y sin sobrescribir un archivo existente. `.env*` (salvo ejemplo)
queda excluido de Git y del build. Compose local ahora respeta SUPABASE_ENABLED y
transmite las variables al contenedor; antes lo forzaba a false.

La URL y clave publishable proporcionadas respondieron 200 a una consulta de `logs`
con la selección de columnas esperada y `limit=0`. Otra consulta `select=log_id&limit=1`
devolvió una fila sin JWT de usuario. No se imprimió ni guardó su identificador.
Esto verifica conectividad y visibilidad anónima de al menos un registro; NO verifica
una identidad dedicada de solo lectura, aislamiento por usuario ni ausencia de permisos
de escritura. Revisar GRANT/RLS con el responsable; no se modificaron políticas.
Un token literal `<TU_ACCESS_TOKEN>` o una API key en SUPABASE_READ_TOKEN se rechaza.

Repositorios revisados nuevamente:

- Gateway `9fca369ccee9c0e5b04eced1a73235edc5911d88`: application.yaml solo enruta
  las tres operaciones Monitoring. SecurityConfiguration.java solo autoriza esas rutas
  y termina en denyAll. Una petición Data Processing no llega a este servicio.
- El timeout global de Gateway es 6 segundos frente a 10 segundos por defecto en
  Data Processing; asignar un presupuesto mayor a las rutas nuevas.
- Gateway exige JWT válido y claim firmado `user_role=OPERATOR|ADMIN`; crear una
  cuenta Supabase no añade automáticamente ese claim. No aceptar roles del navegador.
- Frontend permanece en `0ef8a5c9dbfa108c133e2d59392dc6b032757058`: fetchMonitoring
  no envía Authorization ni los parámetros de consulta requeridos; consume listas
  de snapshots del mock y trata catalog como inventario. Sigue usando el login del
  backend antiguo y localStorage para el usuario. No consume Data Processing.

Estas incompatibilidades externas siguen impidiendo certificar un flujo completo al
hacer push. Ver `gateway-handoff.md` para cambios concretos del repositorio Gateway.

## Dependencias externas verificadas

Fuentes revisadas:

- https://github.com/woshtsu/green-ai-project-docs/blob/main/GUIA-INTEGRACION-DATA-PROCESSING.md
- https://github.com/woshtsu/green-ai-project-docs/blob/main/modelo-bd.md
- https://github.com/woshtsu/green-ai-monitoring/blob/main/src/main/resources/static/openapi/monitoring-v0.1.json
- https://github.com/woshtsu/green-ai-gateway/blob/main/arquitectura-integracion-data-processing.md
- https://github.com/LeonidKisley/Frontend-GreenAi/blob/0ef8a5c9dbfa108c133e2d59392dc6b032757058/app.js

Supabase: no hay .env ni variables SUPABASE configuradas en el proyecto/sesión.
Falta una lectura real acotada con acceso de servidor de solo lectura y confirmación
de permisos efectivos. No se inspeccionaron ni cambiaron tablas o políticas.

Prediction: los documentos describen un núcleo ML experimental y no una API final.
Este servicio publica preparación de entrada; falta acordar el contrato con Prediction,
su URL/endpoint, mínimo de muestras, cadencia, horizonte y tratamiento de huecos.
No se ha inventado una llamada HTTP ni una predicción de ejemplo como resultado real.

Frontend: el repositorio enlazado llama `current/history` sin parámetros y hace `.map()`
sobre sus respuestas, esperando snapshots de un mock. Monitoring requiere `metric`
y, para history, `start/end`, y devuelve un objeto con `series`. Su `catalog` es un
catálogo de métricas, no inventario hardware. También mantiene llamadas a un backend
de login/registro. Esas incompatibilidades deben corregirse en el repositorio frontend;
agregar Data Processing no transforma automáticamente ese contrato antiguo.

Gateway: requiere rutas explícitas `/api/processing/v1/...` hacia este servicio y
reglas de autorización OPERATOR/ADMIN. No basta con una ruta YAML sin seguridad.
No se modificaron repositorios ajenos ni se desplegó una configuración compartida.

## Comprobación de ensamblaje pendiente

1. Construir la imagen y conectarla a la red de Monitoring/Gateway.
2. Comparar una consulta real de Monitoring con la procesada: unidad, valores, labels,
   recurso, origen y warnings, además del HTTP 200.
3. Configurar el acceso de solo lectura y paginar Supabase hasta una página vacía.
4. Registrar las rutas exactas en Gateway y verificar 401 sin token, éxito con rol
   permitido y 403 con rol insuficiente. No guardar tokens como evidencia.
5. Adaptar frontend al contrato real y conectar Prediction cuando publique su API.
