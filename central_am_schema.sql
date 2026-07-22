-- ============================================================
-- SCRIPT SQL — CENTRAL A&M: PLANES DE SERVICIO
-- Ejecutar en el SQL Editor de Supabase (una sola vez)
-- ============================================================

-- Agregar la columna 'plan' a la tabla de configuración del sistema si no existe
ALTER TABLE configuracion_sistema ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'premium';

-- Asegurar que las empresas existentes tengan el plan premium asignado por defecto
UPDATE configuracion_sistema SET plan = 'premium' WHERE plan IS NULL;

-- ============================================================
-- FIN DEL SCRIPT
-- ============================================================
