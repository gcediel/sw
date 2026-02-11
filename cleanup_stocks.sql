-- ============================================================
-- LIMPIEZA DE ACCIONES CON DATOS INSUFICIENTES (VERSIÓN CORREGIDA)
-- ============================================================
-- Este script elimina:
-- 1. Acciones SIN datos en daily_data
-- 2. Acciones con menos de 100 registros (insuficiente para análisis)
-- ============================================================

-- PASO 1: Ver cuántas acciones se van a borrar
SELECT '=== PASO 1: ANÁLISIS PREVIO ===' as info;
SELECT '';

-- 1A. Acciones SIN datos
SELECT 'Acciones SIN datos:' as categoria;
SELECT COUNT(*) as total
FROM stocks
WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data);

SELECT '';
SELECT 'Listado de acciones SIN datos (primeras 30):' as info;
SELECT ticker, name, exchange
FROM stocks
WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data)
ORDER BY ticker
LIMIT 30;

SELECT '';
-- 1B. Acciones con POCOS datos (<100 registros)
SELECT 'Acciones con POCOS datos (<100 registros):' as categoria;
SELECT COUNT(*) as total
FROM (
    SELECT s.id
    FROM stocks s
    LEFT JOIN daily_data d ON s.id = d.stock_id
    GROUP BY s.id
    HAVING COUNT(d.id) > 0 AND COUNT(d.id) < 100
) as subq;

SELECT '';
SELECT 'Listado de acciones con POCOS datos (primeras 30):' as info;
SELECT s.ticker, s.name, COUNT(d.id) as registros
FROM stocks s
LEFT JOIN daily_data d ON s.id = d.stock_id
GROUP BY s.id
HAVING registros > 0 AND registros < 100
ORDER BY registros ASC, s.ticker
LIMIT 30;

SELECT '';
-- RESUMEN TOTAL
SELECT '=== RESUMEN ===' as info;
SELECT 
    (
        SELECT COUNT(*)
        FROM stocks
        WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data)
    ) + (
        SELECT COUNT(*)
        FROM (
            SELECT s.id
            FROM stocks s
            LEFT JOIN daily_data d ON s.id = d.stock_id
            GROUP BY s.id
            HAVING COUNT(d.id) > 0 AND COUNT(d.id) < 100
        ) as subq
    ) as total_acciones_a_borrar;

SELECT 
    COUNT(*) - (
        (
            SELECT COUNT(*)
            FROM stocks
            WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data)
        ) + (
            SELECT COUNT(*)
            FROM (
                SELECT s.id
                FROM stocks s
                LEFT JOIN daily_data d ON s.id = d.stock_id
                GROUP BY s.id
                HAVING COUNT(d.id) > 0 AND COUNT(d.id) < 100
            ) as subq
        )
    ) as acciones_que_quedaran
FROM stocks;

-- ============================================================
-- PASO 2: EJECUTAR LIMPIEZA (Descomentar para borrar)
-- ============================================================
-- IMPORTANTE: Revisa el PASO 1 antes de ejecutar esto
-- ============================================================



-- Crear tabla temporal con IDs a borrar (soluciona el error de MySQL)
CREATE TEMPORARY TABLE temp_stocks_to_delete (
    stock_id INT PRIMARY KEY
);

-- Insertar IDs de acciones con pocos datos
INSERT INTO temp_stocks_to_delete (stock_id)
SELECT s.id
FROM stocks s
LEFT JOIN daily_data d ON s.id = d.stock_id
GROUP BY s.id
HAVING COUNT(d.id) > 0 AND COUNT(d.id) < 100;

-- Ver cuántos registros de daily_data se borrarán
SELECT '=== Borrando datos diarios de acciones con <100 registros ===' as info;
SELECT COUNT(*) as registros_a_borrar
FROM daily_data
WHERE stock_id IN (SELECT stock_id FROM temp_stocks_to_delete);

-- Borrar datos diarios de estas acciones
DELETE FROM daily_data
WHERE stock_id IN (SELECT stock_id FROM temp_stocks_to_delete);

SELECT 'Datos diarios borrados' as resultado;

-- Borrar acciones con pocos datos
SELECT '=== Borrando acciones con <100 registros ===' as info;
DELETE FROM stocks
WHERE id IN (SELECT stock_id FROM temp_stocks_to_delete);

SELECT 'Acciones con pocos datos borradas' as resultado;

-- Limpiar tabla temporal
DROP TEMPORARY TABLE temp_stocks_to_delete;

-- Borrar acciones SIN datos
SELECT '=== Borrando acciones sin datos ===' as info;
SELECT COUNT(*) as acciones_sin_datos_a_borrar
FROM stocks
WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data);

DELETE FROM stocks
WHERE id NOT IN (SELECT DISTINCT stock_id FROM daily_data);

SELECT 'Acciones sin datos borradas' as resultado;

-- Verificar resultado final
SELECT '';
SELECT '=== LIMPIEZA COMPLETADA ===' as resultado;
SELECT '';

SELECT 'Acciones restantes:' as info;
SELECT COUNT(*) as total FROM stocks;

SELECT '';
SELECT 'Acciones con datos:' as info;
SELECT COUNT(DISTINCT stock_id) as total FROM daily_data;

SELECT '';
SELECT 'Distribución por exchange:' as info;
SELECT exchange, COUNT(*) as total
FROM stocks
GROUP BY exchange
ORDER BY total DESC;

SELECT '';
SELECT 'Rango de registros por acción:' as info;
SELECT 
    MIN(cnt) as minimo,
    AVG(cnt) as promedio,
    MAX(cnt) as maximo
FROM (
    SELECT COUNT(d.id) as cnt
    FROM stocks s
    JOIN daily_data d ON s.id = d.stock_id
    GROUP BY s.id
) as counts;


