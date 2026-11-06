-- Si más del 3 % de una fuente cae en cuarentena, el archivo viene roto: se para.
SELECT fuente, cuarentena, filas_bronze FROM gold.conciliacion WHERE cuarentena > 0.03 * filas_bronze
