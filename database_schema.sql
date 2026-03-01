-- ============================================
-- Stan Weinstein Trading System
-- Database Schema
-- ============================================

-- Crear base de datos
CREATE DATABASE IF NOT EXISTS stanweinstein 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- Crear usuario (cambiar PASSWORD_AQUI por password real)
CREATE USER IF NOT EXISTS 'stanweinstein'@'localhost' IDENTIFIED BY 'T1o6m1a2I!';

-- Otorgar permisos
GRANT ALL PRIVILEGES ON stanweinstein.* TO 'stanweinstein'@'localhost';
FLUSH PRIVILEGES;

-- Usar la base de datos
USE stanweinstein;

-- ============================================
-- Tabla: stocks
-- Acciones monitorizadas
-- ============================================
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    exchange VARCHAR(50),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ticker (ticker),
    INDEX idx_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Tabla: daily_data
-- Datos diarios de cotización (OHLC)
-- ============================================
CREATE TABLE IF NOT EXISTS daily_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_stock_date (stock_id, date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    INDEX idx_date (date),
    INDEX idx_stock_date (stock_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Tabla: weekly_data
-- Datos semanales agregados + análisis
-- ============================================
CREATE TABLE IF NOT EXISTS weekly_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    week_end_date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    ma30 DECIMAL(12,4),
    ma30_slope DECIMAL(8,4),
    stage TINYINT COMMENT '1=Base, 2=Alcista, 3=Techo, 4=Bajista',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_stock_week (stock_id, week_end_date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    INDEX idx_week_date (week_end_date),
    INDEX idx_stage (stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Tabla: signals
-- Señales de compra/venta
-- ============================================
CREATE TABLE IF NOT EXISTS signals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    signal_date DATE NOT NULL,
    signal_type ENUM('BUY', 'SELL', 'STAGE_CHANGE') NOT NULL,
    stage_from TINYINT,
    stage_to TINYINT,
    price DECIMAL(12,4),
    ma30 DECIMAL(12,4),
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_stock_signal_type (stock_id, signal_date, signal_type),
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    INDEX idx_signal_date (signal_date),
    INDEX idx_notified (notified),
    INDEX idx_stock_signal (stock_id, signal_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Verificación
-- ============================================
SHOW TABLES;

SELECT 'Database schema created successfully!' AS status;
