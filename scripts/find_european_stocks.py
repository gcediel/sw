#!/usr/bin/env python3
"""
Busca acciones europeas (incluyendo UK) con mayor volumen medio.
Obtiene los componentes de los principales índices europeos desde Wikipedia,
consulta yfinance para obtener volumen medio de 3 meses y genera un CSV
ordenado por volumen, listo para importar con load_stocks_from_csv.py.

Uso:
    python scripts/find_european_stocks.py                  # genera european_stocks.csv
    python scripts/find_european_stocks.py --top 200        # limitar a top 200 por volumen
    python scripts/find_european_stocks.py --out mi_lista.csv
"""
import sys
import time
import argparse
import logging
import pandas as pd
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Índices europeos: (nombre, URL Wikipedia, índice de tabla, sufijo yfinance, exchange, país)
# ─────────────────────────────────────────────
INDICES = [
    {
        'name': 'FTSE 100 (UK)',
        'url': 'https://en.wikipedia.org/wiki/FTSE_100',
        'table_index': 4,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.L',
        'exchange': 'LSE',
        'country': 'UK',
    },
    {
        'name': 'DAX 40 (Alemania)',
        'url': 'https://en.wikipedia.org/wiki/DAX',
        'table_index': 4,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.DE',
        'exchange': 'XETRA',
        'country': 'Germany',
    },
    {
        'name': 'CAC 40 (Francia)',
        'url': 'https://en.wikipedia.org/wiki/CAC_40',
        'table_index': 4,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.PA',
        'exchange': 'EPA',
        'country': 'France',
    },
    {
        'name': 'AEX (Países Bajos)',
        'url': 'https://en.wikipedia.org/wiki/AEX_index',
        'table_index': 2,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.AS',
        'exchange': 'AMS',
        'country': 'Netherlands',
    },
    {
        'name': 'IBEX 35 (España)',
        'url': 'https://en.wikipedia.org/wiki/IBEX_35',
        'table_index': 3,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.MC',
        'exchange': 'BME',
        'country': 'Spain',
    },
    {
        'name': 'FTSE MIB (Italia)',
        'url': 'https://en.wikipedia.org/wiki/FTSE_MIB',
        'table_index': 1,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.MI',
        'exchange': 'BIT',
        'country': 'Italy',
    },
    {
        'name': 'SMI (Suiza)',
        'url': 'https://en.wikipedia.org/wiki/Swiss_Market_Index',
        'table_index': 1,
        'ticker_col': 'Ticker',
        'name_col': 'Company',
        'suffix': '.SW',
        'exchange': 'SIX',
        'country': 'Switzerland',
    },
    {
        'name': 'OMX Stockholm 30 (Suecia)',
        'url': 'https://en.wikipedia.org/wiki/OMX_Stockholm_30',
        'table_index': 1,
        'ticker_col': 'Symbol',
        'name_col': 'Company',
        'suffix': '.ST',
        'exchange': 'STO',
        'country': 'Sweden',
    },
]

# Listas de respaldo para cuando Wikipedia falla (tickers yfinance verificados)
FALLBACK = {
    'FTSE 100 (UK)': [
        ('AZN.L','AstraZeneca'),('SHEL.L','Shell'),('HSBA.L','HSBC Holdings'),
        ('ULVR.L','Unilever'),('BP.L','BP'),('RIO.L','Rio Tinto'),
        ('GSK.L','GSK'),('REL.L','RELX'),('DGE.L','Diageo'),
        ('BHP.L','BHP Group'),('VOD.L','Vodafone'),('BARC.L','Barclays'),
        ('LLOY.L','Lloyds Banking'),('NG.L','National Grid'),('IMB.L','Imperial Brands'),
        ('PRU.L','Prudential'),('BATS.L','British American Tobacco'),('AAL.L','Anglo American'),
        ('AHT.L','Ashtead Group'),('ANTO.L','Antofagasta'),('AUTO.L','Auto Trader'),
        ('AV.L','Aviva'),('BA.L','BAE Systems'),('BNZL.L','Bunzl'),
        ('BT.A.L','BT Group'),('CCH.L','Coca-Cola HBC'),('CPG.L','Compass Group'),
        ('CRH.L','CRH'),('EOAN.L','E.ON'),('FERG.L','Ferguson'),
        ('GLEN.L','Glencore'),('HLMA.L','Halma'),('IAG.L','IAG'),
        ('IHG.L','IHG Hotels'),('III.L','3i Group'),('INF.L','Informa'),
        ('ITRK.L','Intertek'),('JD.L','JD Sports'),('KGF.L','Kingfisher'),
        ('LAND.L','Land Securities'),('LGEN.L','Legal & General'),('MKS.L','Marks & Spencer'),
        ('MNDI.L','Mondi'),('MRO.L','Melrose Industries'),('NWG.L','NatWest'),
        ('OCDO.L','Ocado'),('PSON.L','Pearson'),('PSN.L','Persimmon'),
        ('RKT.L','Reckitt'),('RMV.L','Rightmove'),('RR.L','Rolls-Royce'),
        ('RS1.L','RS Group'),('SGE.L','Sage Group'),('SGRO.L','Segro'),
        ('SKG.L','Smurfit Kappa'),('SMIN.L','Smiths Group'),('SMT.L','Scottish Mortgage'),
        ('SPX.L','Spirax-Sarco'),('SSE.L','SSE'),('STAN.L','Standard Chartered'),
        ('SVT.L','Severn Trent'),('TSCO.L','Tesco'),('TW.L','Taylor Wimpey'),
        ('WEIR.L','Weir Group'),('WPP.L','WPP'),('WTB.L','Whitbread'),
    ],
    'DAX 40 (Alemania)': [
        ('SAP.DE','SAP'),('SIE.DE','Siemens'),('ALV.DE','Allianz'),
        ('MRK.DE','Merck'),('MUV2.DE','Munich Re'),('DTE.DE','Deutsche Telekom'),
        ('BAYN.DE','Bayer'),('BMW.DE','BMW'),('BAS.DE','BASF'),
        ('DB1.DE','Deutsche Boerse'),('VOW3.DE','Volkswagen'),('ADS.DE','Adidas'),
        ('EOAN.DE','E.ON'),('FRE.DE','Fresenius'),('HEN3.DE','Henkel'),
        ('IFX.DE','Infineon'),('LIN.DE','Linde'),('MBG.DE','Mercedes-Benz'),
        ('MTX.DE','MTU Aero'),('RWE.DE','RWE'),('SHL.DE','Siemens Healthineers'),
        ('SY1.DE','Symrise'),('VNA.DE','Vonovia'),('ZAL.DE','Zalando'),
        ('CON.DE','Continental'),('ENR.DE','Siemens Energy'),('DHL.DE','DHL Group'),
        ('AIR.DE','Airbus'),('BEI.DE','Beiersdorf'),('DHER.DE','Delivery Hero'),
        ('DTG.DE','Daimler Truck'),('P911.DE','Porsche AG'),('PAH3.DE','Porsche Auto'),
        ('RHM.DE','Rheinmetall'),('SRT.DE','Sartorius'),('HFG.DE','HelloFresh'),
        ('QIA.DE','Qiagen'),('PUMA.DE','PUMA'),('HEI.DE','HeidelbergMaterials'),
        ('DBK.DE','Deutsche Bank'),
    ],
    'CAC 40 (Francia)': [
        ('MC.PA','LVMH'),('TTE.PA','TotalEnergies'),('SAN.PA','Sanofi'),
        ('AIR.PA','Airbus'),('OR.PA','L\'Oreal'),('BNP.PA','BNP Paribas'),
        ('EL.PA','EssilorLuxottica'),('SU.PA','Schneider Electric'),('AI.PA','Air Liquide'),
        ('RI.PA','Pernod Ricard'),('CAP.PA','Capgemini'),('ACA.PA','Credit Agricole'),
        ('CS.PA','AXA'),('RMS.PA','Hermes'),('GLE.PA','Societe Generale'),
        ('DG.PA','Vinci'),('SGO.PA','Saint-Gobain'),('BN.PA','Danone'),
        ('VIE.PA','Veolia'),('EN.PA','Bouygues'),('DSY.PA','Dassault Systemes'),
        ('ENGI.PA','Engie'),('PUB.PA','Publicis'),('SAF.PA','Safran'),
        ('STM.PA','STMicroelectronics'),('ORA.PA','Orange'),('RNO.PA','Renault'),
        ('STLA.PA','Stellantis'),('LR.PA','Legrand'),('MT.PA','ArcelorMittal'),
        ('TEP.PA','Teleperformance'),('FTI.PA','Technip Energies'),('ERF.PA','Eurofins'),
        ('VIV.PA','Vivendi'),('AF.PA','Air France-KLM'),('SEB.PA','SEB'),
        ('NK.PA','Imerys'),('FR.PA','Valeo'),('UG.PA','Peugeot'),
        ('KER.PA','Kering'),
    ],
    'AEX (Países Bajos)': [
        ('ASML.AS','ASML'),('SHELL.AS','Shell'),('HEIA.AS','Heineken'),
        ('PRX.AS','Prosus'),('INGA.AS','ING Groep'),('AD.AS','Ahold Delhaize'),
        ('AKZA.AS','Akzo Nobel'),('NN.AS','NN Group'),('PHIA.AS','Philips'),
        ('REN.AS','Randstad'),('WKL.AS','Wolters Kluwer'),('AGN.AS','Aegon'),
        ('BESI.AS','BE Semiconductor'),('IMCD.AS','IMCD'),('MT.AS','ArcelorMittal'),
        ('SBM.AS','SBM Offshore'),('VPK.AS','Vopak'),('UNA.AS','Unilever NV'),
        ('DSM.AS','DSM-Firmenich'),('OCI.AS','OCI'),('TKWY.AS','Just Eat Takeaway'),
        ('URW.AS','Unibail-Rodamco'),('STLAM.AS','Stellantis'),('ADYEN.AS','Adyen'),
        ('GLPG.AS','Galapagos'),
    ],
    'IBEX 35 (España)': [
        ('ITX.MC','Inditex'),('SAN.MC','Banco Santander'),('IBE.MC','Iberdrola'),
        ('BBVA.MC','BBVA'),('REP.MC','Repsol'),('TEF.MC','Telefonica'),
        ('CABK.MC','Caixabank'),('ELE.MC','Endesa'),('REE.MC','Red Electrica'),
        ('MAP.MC','Mapfre'),('FER.MC','Ferrovial'),('GAS.MC','Naturgy'),
        ('AMS.MC','Amadeus'),('CLNX.MC','Cellnex'),('ENG.MC','Enagas'),
        ('IAG.MC','IAG'),('IDR.MC','Indra'),('SAB.MC','Sabadell'),
        ('ACX.MC','Acerinox'),('ACS.MC','ACS'),('ANA.MC','Acciona'),
        ('AENA.MC','AENA'),('BKT.MC','Bankinter'),('CIE.MC','CIE Automotive'),
        ('MRL.MC','Merlin Properties'),('ROVI.MC','Laboratorios Rovi'),
        ('UNI.MC','Unicaja'),('VIS.MC','Viscofan'),('LOG.MC','Logista'),
        ('COL.MC','Inmobiliaria Colonial'),('SGC.MC','Sacyr'),('SLR.MC','Solaria'),
        ('TLGO.MC','Talgo'),('TRE.MC','Tecnicas Reunidas'),('NTGY.MC','Naturgy Energy'),
    ],
    'FTSE MIB (Italia)': [
        ('ENI.MI','ENI'),('ENEL.MI','Enel'),('ISP.MI','Intesa Sanpaolo'),
        ('UCG.MI','UniCredit'),('STM.MI','STMicroelectronics'),('LDO.MI','Leonardo'),
        ('G.MI','Generali'),('RACE.MI','Ferrari'),('PRY.MI','Prysmian'),
        ('PST.MI','Poste Italiane'),('MB.MI','Mediobanca'),('MONC.MI','Moncler'),
        ('NEXI.MI','Nexi'),('PIRC.MI','Pirelli'),('REC.MI','Recordati'),
        ('SRG.MI','Snam'),('TEN.MI','Tenaris'),('TRN.MI','Terna'),
        ('A2A.MI','A2A'),('AMP.MI','Amplifon'),('BAMI.MI','Banco BPM'),
        ('BGN.MI','Banca Generali'),('BMED.MI','Banca Mediolanum'),('BPE.MI','BPER Banca'),
        ('CPR.MI','Campari'),('DIA.MI','DiaSorin'),('FBK.MI','FinecoBank'),
        ('HER.MI','Hera'),('INW.MI','Infrastrutture Wireless'),('IP.MI','Interpump'),
        ('SPM.MI','Saipem'),('TIT.MI','Telecom Italia'),('ATL.MI','Atlantia'),
        ('AZM.MI','Azimut'),('EXO.MI','Exor'),('INWT.MI','Inwit'),
        ('MFEA.MI','Mediaforeurope'),('BANCA.MI','Banco BPM'),('SHB.MI','Sanpaolo'),
        ('FCA.MI','Stellantis'),
    ],
    'SMI (Suiza)': [
        ('NESN.SW','Nestle'),('ROG.SW','Roche'),('NOVN.SW','Novartis'),
        ('ABBN.SW','ABB'),('GEBN.SW','Geberit'),('GIVN.SW','Givaudan'),
        ('HOLN.SW','Holcim'),('KNIN.SW','Kuehne + Nagel'),('LONN.SW','Lonza'),
        ('PGHN.SW','Partners Group'),('SGSN.SW','SGS'),('SIKA.SW','Sika'),
        ('SLHN.SW','Swiss Life'),('SRENH.SW','Swiss Re'),('UBSG.SW','UBS'),
        ('ZURN.SW','Zurich Insurance'),('ALC.SW','Alcon'),('CFR.SW','Richemont'),
        ('CSGN.SW','Credit Suisse'),('SREN.SW','Swiss Re'),
    ],
    'OMX Stockholm 30 (Suecia)': [
        ('VOLV-B.ST','Volvo'),('ERIC-B.ST','Ericsson'),('ALFA.ST','Alfa Laval'),
        ('ASSA-B.ST','Assa Abloy'),('ATCO-A.ST','Atlas Copco A'),('ATCO-B.ST','Atlas Copco B'),
        ('BOL.ST','Boliden'),('EQT.ST','EQT'),('ESSITY-B.ST','Essity'),
        ('EVO.ST','Evolution'),('GETI-B.ST','Getinge'),('HEXA-B.ST','Hexagon'),
        ('HM-B.ST','H&M'),('HUSQ-B.ST','Husqvarna'),('INDU-C.ST','Industrivarden'),
        ('INVE-B.ST','Investor'),('KINV-B.ST','Kinnevik'),('NDA-SE.ST','Nordea'),
        ('NIBE-B.ST','NIBE Industrier'),('SAND.ST','Sandvik'),('SCA-B.ST','SCA'),
        ('SEB-A.ST','SEB'),('SECU-B.ST','Securitas'),('SKA-B.ST','Skanska'),
        ('SKF-B.ST','SKF'),('SWED-A.ST','Swedbank'),('SWMA.ST','Swedish Match'),
        ('TEL2-B.ST','Tele2'),('TELIA.ST','Telia'),('LUPE.ST','Lundin Energy'),
    ],
}


def get_index_constituents(index_cfg: dict) -> list:
    """
    Intenta obtener los componentes del índice desde Wikipedia.
    Si falla, usa la lista de respaldo.
    Devuelve lista de (ticker_yfinance, nombre, país, exchange).
    """
    name     = index_cfg['name']
    suffix   = index_cfg['suffix']
    exchange = index_cfg['exchange']
    country  = index_cfg['country']

    try:
        logger.info(f"  Obteniendo {name} desde Wikipedia...")
        tables = pd.read_html(index_cfg['url'], attrs={'class': 'wikitable'})

        if index_cfg['table_index'] >= len(tables):
            raise ValueError(f"Tabla {index_cfg['table_index']} no encontrada (hay {len(tables)})")

        df = tables[index_cfg['table_index']]

        ticker_col = next((c for c in df.columns if index_cfg['ticker_col'].lower() in str(c).lower()), None)
        name_col   = next((c for c in df.columns if index_cfg['name_col'].lower() in str(c).lower()), None)

        if not ticker_col or not name_col:
            raise ValueError(f"Columnas no encontradas. Disponibles: {list(df.columns)}")

        result = []
        for _, row in df.iterrows():
            ticker_raw = str(row[ticker_col]).strip()
            company    = str(row[name_col]).strip()
            if not ticker_raw or ticker_raw == 'nan':
                continue
            ticker = ticker_raw if ticker_raw.endswith(suffix) else ticker_raw + suffix
            result.append((ticker, company, country, exchange))

        logger.info(f"    ✓ {len(result)} acciones obtenidas desde Wikipedia")
        return result

    except Exception as e:
        logger.warning(f"    ⚠ Wikipedia falló ({e}), usando lista de respaldo")
        fallback = FALLBACK.get(name, [])
        return [(t, n, country, exchange) for t, n in fallback]


def get_avg_volume(tickers: list, period_days: int = 90) -> dict:
    """
    Obtiene el volumen medio de los últimos `period_days` días.
    Devuelve dict {ticker: avg_volume}.
    """
    volumes = {}
    total = len(tickers)
    batch_size = 50

    logger.info(f"\nConsultando volumen para {total} acciones (lotes de {batch_size})...")

    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]

        try:
            data = yf.download(
                ' '.join(batch),
                period=f'{period_days}d',
                interval='1d',
                progress=False,
                threads=True,
                auto_adjust=True,
            )

            if data.empty:
                continue

            vol_df = data['Volume'] if isinstance(data.columns, pd.MultiIndex) else data[['Volume']]
            if not isinstance(data.columns, pd.MultiIndex):
                vol_df.columns = batch

            for ticker in batch:
                if ticker in vol_df.columns:
                    avg = vol_df[ticker].dropna().mean()
                    if avg > 0:
                        volumes[ticker] = int(avg)

        except Exception as e:
            logger.warning(f"  Error en lote {i // batch_size + 1}: {e}")

        logger.info(f"  Procesadas {min(i + batch_size, total)}/{total}")
        time.sleep(1)

    return volumes


def main():
    parser = argparse.ArgumentParser(description='Buscar acciones europeas con mayor volumen')
    parser.add_argument('--top', type=int, default=0,
                        help='Limitar output a las N acciones con más volumen (0 = todas)')
    parser.add_argument('--out', default='european_stocks.csv',
                        help='Archivo CSV de salida (default: european_stocks.csv)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BÚSQUEDA DE ACCIONES EUROPEAS CON MAYOR VOLUMEN")
    logger.info("=" * 60)

    # ── 1. Obtener componentes de cada índice ──
    all_stocks = {}  # ticker → (nombre, país, exchange)
    for idx_cfg in INDICES:
        for ticker, name, country, exchange in get_index_constituents(idx_cfg):
            if ticker not in all_stocks:
                all_stocks[ticker] = (name, country, exchange)

    logger.info(f"\nTotal acciones únicas encontradas: {len(all_stocks)}")

    # ── 2. Obtener volumen medio ──
    volumes = get_avg_volume(list(all_stocks.keys()))
    logger.info(f"Volumen obtenido para {len(volumes)}/{len(all_stocks)} acciones")

    # ── 3. Ordenar por volumen ──
    rows = [
        {'name': name, 'ticker': ticker, 'country': country,
         'exchange': exchange, 'avg_volume': volumes.get(ticker, 0)}
        for ticker, (name, country, exchange) in all_stocks.items()
    ]
    rows.sort(key=lambda x: x['avg_volume'], reverse=True)

    rows_with_vol = [r for r in rows if r['avg_volume'] > 0]
    rows_no_vol   = [r for r in rows if r['avg_volume'] == 0]

    if args.top > 0:
        rows_with_vol = rows_with_vol[:args.top]

    # ── 4. Guardar CSV compatible con load_stocks_from_csv.py ──
    with open(args.out, 'w', encoding='utf-8') as f:
        for r in rows_with_vol:
            f.write(f"{r['name']};{r['ticker']};{r['country']}\n")

    # ── 5. Resumen ──
    logger.info(f"\n{'='*60}")
    logger.info(f"RESUMEN")
    logger.info(f"{'='*60}")
    logger.info(f"Acciones con volumen:    {len(rows_with_vol)}")
    logger.info(f"Sin volumen (excluidas): {len(rows_no_vol)}")
    logger.info(f"CSV guardado en:         {args.out}")

    logger.info(f"\nTOP 20 por volumen medio diario:")
    logger.info(f"{'─'*65}")
    logger.info(f"{'#':>3}  {'Ticker':<12} {'País':<12} {'Vol. medio':>15}  Nombre")
    logger.info(f"{'─'*65}")
    for i, r in enumerate(rows_with_vol[:20], 1):
        logger.info(f"{i:>3}  {r['ticker']:<12} {r['country']:<12} {r['avg_volume']:>15,}  {r['name']}")

    if rows_no_vol:
        logger.info(f"\n⚠ Sin datos de volumen ({len(rows_no_vol)}):")
        for r in rows_no_vol:
            logger.info(f"   {r['ticker']:<12} {r['name']}")

    logger.info(f"\n{'='*60}")
    logger.info(f"SIGUIENTE PASO:")
    logger.info(f"  Revisar el CSV y luego importar:")
    logger.info(f"  python scripts/load_stocks_from_csv.py {args.out} --dry-run")
    logger.info(f"  python scripts/load_stocks_from_csv.py {args.out}")
    logger.info(f"{'='*60}")


if __name__ == '__main__':
    main()
