pwd
who am i
who am i
cd
pwd
ls
nano prueba
ls -al
rm prueba
ls
nano app/aggregator.py
nano scripts/init_weekly_aggregation.py
nano scripts/weekly_process.py
chmod +x scripts/*.py
ls -al scripts/
cd /home/stanweinstein
source venv/bin/activate
python3 scripts/init_weekly_aggregation.py
mysql -u stanweinstein -p stanweinstein << 'EOF'
-- Total de semanas agregadas
SELECT COUNT(*) as total_semanas FROM weekly_data;

-- Semanas con MA30 calculada
SELECT COUNT(*) as semanas_con_ma30 
FROM weekly_data 
WHERE ma30 IS NOT NULL;

-- Ver últimas 5 semanas de Apple
SELECT 
    week_end_date,
    close,
    ma30,
    ma30_slope,
    stage
FROM weekly_data
WHERE stock_id = (SELECT id FROM stocks WHERE ticker = 'AAPL')
ORDER BY week_end_date DESC
LIMIT 5;
EOF

crontab -l
crontab -e
