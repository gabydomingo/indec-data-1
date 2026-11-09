# Cuanto subio cada rubro del IPC desde dic-2016 (indice base 100)
# Datos: API del INDEC, dataset ipc_nacional
# Saca un CSV para armar el grafico en Looker Studio

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("INDEC_API_TOKEN")
URL = "https://api.indec.gob.ar/v1/ipc_nacional"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# nombres cortos para que entren en el grafico
RUBROS = {
    "0": "Nivel general",
    "01": "Alimentos y bebidas",
    "02": "Alcohol y tabaco",
    "03": "Ropa y calzado",
    "04": "Vivienda y servicios",
    "05": "Equipamiento del hogar",
    "06": "Salud",
    "07": "Transporte",
    "08": "Comunicacion",
    "09": "Recreacion y cultura",
    "10": "Educacion",
    "11": "Restaurantes y hoteles",
    "12": "Bienes y servicios varios",
}


def pedir(params):
    for _ in range(3):
        r = requests.get(URL, headers=HEADERS, params=params, timeout=30)
        if r.status_code == 429:  # demasiadas consultas, espero y pruebo de nuevo
            time.sleep(10)
            continue
        r.raise_for_status()
        return r.json()
    raise SystemExit("La API sigue tirando 429, probar mas tarde")


def pedir_todo(params):
    # la API devuelve como mucho 1000 filas por consulta
    filas = []
    offset = 0
    while True:
        pagina = pedir({**params, "limit": 1000, "offset": offset})
        filas += pagina
        if len(pagina) < 1000:
            return filas
        offset += 1000


if not TOKEN:
    raise SystemExit("Falta INDEC_API_TOKEN en el .env")

filtros = {"region": "eq.Nacional", "tipo_de_indicador": "eq.Indice"}

# ultimo mes publicado
ultimo = pedir({**filtros, "order": "periodo.desc", "limit": 1})
periodo = str(ultimo[0]["periodo"])
print("Periodo:", periodo)

# ordeno por clasificador y codigo para que no se repitan filas al paginar
df = pd.DataFrame(pedir_todo({**filtros, "periodo": f"eq.{periodo}", "order": "clasificador,codigo"}))
df["codigo"] = df["codigo"].astype(str)
df["valor"] = pd.to_numeric(df["valor"])

# nivel general + las 12 divisiones (son las de codigo de 2 digitos)
general = (df["clasificador"] == "IPC") & (df["codigo"] == "0")
divisiones = (df["clasificador"] == "COICOP Argentina 2019") & (df["codigo"].str.len() == 2)
df = df[general | divisiones]

if len(df) != 13:
    print("Ojo, esperaba 13 filas y llegaron", len(df))

salida = pd.DataFrame({
    "codigo": df["codigo"],
    "rubro": df["descripcion"],
    "rubro_corto": df["codigo"].map(RUBROS),
    "tipo": df["codigo"].map(lambda c: "Nivel general" if c == "0" else "Rubro"),
    "indice": df["valor"].round(2),
    "veces": (df["valor"] / 100).round(1),
    "aumento_pct": (df["valor"] - 100).round(1),  # base 100, asi que el aumento es valor - 100
    "periodo": periodo[:4] + "-" + periodo[4:],
})
salida = salida.sort_values("veces", ascending=False)
salida.to_csv("ipc_rubros_desde_2016.csv", index=False)

print(salida[["rubro_corto", "veces", "aumento_pct"]].to_string(index=False))
