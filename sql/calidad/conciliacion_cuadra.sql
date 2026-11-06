-- Ninguna fila de bronze se pierde entre capas.
SELECT * FROM gold.conciliacion WHERE NOT cuadra
