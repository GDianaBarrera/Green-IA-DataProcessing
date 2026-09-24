# Contrato para integrar Data Processing en Gateway y Frontend

Revisado contra Gateway 9fca369 y Frontend 0ef8a5c el 2026-09-24.
Este documento no modifica ni certifica esos repositorios. El contrato de este servicio
está exportado en `contracts/data-processing-v1.openapi.json`.

## Gateway: rutas y timeout

En `src/main/resources/application.yaml`, dentro del mismo `routes` que Monitoring,
agregar una ruta explícita. No sustituir las rutas existentes:

```yaml
- id: data-processing-history
  uri: ${GATEWAY_DATA_PROCESSING_BASE_URL:http://data-processing:8000}
  predicates:
    - Path=/api/processing/v1/metrics/history,/api/processing/v1/historical-logs
    - Method=GET
  filters:
    - StripPrefix=3
    - PrefixPath=/api/v1
  metadata:
    connect-timeout: 1000
    response-timeout: 15000
```

El timeout por ruta se expresa en milisegundos. Debe superar el timeout configurado
en Data Processing más el margen de procesamiento. Si se aumenta el upstream timeout,
ajustar también el presupuesto de Gateway. Mantener los servicios en la misma red.

## Gateway: autorización

En `SecurityConfiguration.java`, antes de `anyExchange().denyAll()`, agregar:

```java
.pathMatchers(HttpMethod.GET,
    "/api/processing/v1/metrics/history",
    "/api/processing/v1/historical-logs")
    .hasAnyRole("OPERATOR", "ADMIN")
```

Conservar validación issuer, JWKS, audience, expiración y roles firmados. El claim
`user_role` debe emitirse desde una configuración de confianza de Supabase Auth,
nunca desde user_metadata editable ni desde el formulario. La API key publishable
no es un JWT de sesión. El token de lectura del servidor no se envía al navegador.

Publicar la ruta `/api/processing/v1/prediction/dataset` solo si el consumidor acepta
que prepara datos y no ejecuta inferencia. En ese caso añadirla explícitamente a la
ruta y a los matchers, conservando su condición provisional en el OpenAPI externo.

Actualizar `gateway-v0.1.yaml` con parámetros y respuestas del OpenAPI de este servicio.
Probar 401 sin JWT, 403 con rol insuficiente, éxito con rol permitido, conservación
de query/errores/request ID y reescritura a `/api/v1/...`. Verificar el origen CORS
exacto: `localhost` y `127.0.0.1` son orígenes diferentes.

## Frontend: cambios necesarios

- Reemplazar la sesión basada solo en localStorage/backend antiguo por Supabase Auth
  y enviar el access_token vigente al Gateway en `Authorization: Bearer ...`.
- Construir el selector de métrica desde catalog; catalog no es una lista de hardware.
- En current enviar metric; en history enviar metric, start/end UTC en segundos enteros
  y, cuando corresponda, resourceType, cluster, resourceId y stepSeconds.
- Leer `series` para Monitoring y `records` para Data Processing; no ejecutar `.map()`
  sobre el objeto completo. Mantener labels y recursos separados.
- Para Supabase consumir `/api/processing/v1/historical-logs` desde Gateway, continuar
  con nextCursor y los mismos filtros hasta página vacía. No consultar tablas desde UI.
- Presentar null como ausencia, CPU/RAM históricos como porcentaje, energia_watts como W,
  origin unknown como procedencia sin confirmar y errores 401/403/422/502/503/504 como
  estados explícitos. No mostrar predicciones ni energía kWh derivadas del mock como reales.

Completar primero esas modificaciones y después hacer una prueba real de extremo a
extremo. Un build Docker correcto de Data Processing no demuestra esos otros flujos.
