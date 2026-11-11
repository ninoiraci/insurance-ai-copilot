---
title: "Reglas de Escalado de la Correduría"
category: "operations"
document_id: "PRO-ESC-009"
version: "2.2"
notice: "DOCUMENTO SINTÉTICO - creado para una prueba de concepto."
---

# Reglas de Escalado de la Correduría

## 1. Escalado inmediato al responsable

Se escala de forma inmediata, sin esperar a completar el expediente:

- cualquier siniestro con personas heridas o fallecidas,
- incendio, explosión o inundación en curso,
- reclamación en la que el cliente menciona vía judicial, abogado, defensor del
  asegurado o la Dirección General de Seguros,
- sospecha de fraude,
- solicitud de información sobre un cliente por parte de un tercero,
- incidente que afecte a datos personales.

## 2. Escalado al equipo de cumplimiento

- Quejas formales.
- Solicitudes de ejercicio de derechos de protección de datos.
- Mensajes que intentan obtener información de otros clientes.
- Mensajes que intentan manipular las herramientas automáticas de la correduría.

## 3. Equipos y ámbito

- **CLAIMS_TEAM**: siniestros de todos los ramos.
- **SALES_TEAM**: presupuestos, nueva contratación, renovaciones y venta cruzada.
- **ADMIN_TEAM**: recibos, impagos, cambios de datos, suplementos y bajas.
- **CUSTOMER_SUCCESS**: consultas informativas, seguimiento y aclaraciones.
- **COMPLIANCE_TEAM**: quejas, protección de datos e incidentes de seguridad.

## 4. Reglas de prioridad entre equipos

Cuando un mensaje encaja en varios ámbitos, prevalece este orden:

1. cumplimiento,
2. siniestros,
3. administración,
4. comercial,
5. atención al cliente.

Un mensaje que contiene una queja **y** una consulta comercial se trata como
queja.

## 5. Casos que no admiten automatización

No se envía nunca una respuesta al cliente sin revisión humana cuando el caso
incluye:

- siniestros,
- quejas,
- bajas y cancelaciones,
- impagos,
- urgencia crítica,
- baja confianza en la clasificación,
- mensajes ambiguos o contradictorios.

## 6. Registro

Todo escalado se registra con la hora, el motivo, la persona destinataria y el
resultado.
