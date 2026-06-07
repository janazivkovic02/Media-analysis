import pandas as pd
import glob
import os
import json
import csv


#cuvamo putanje
BASE_PATH = r"C:\Users\KORISNIK\Desktop\MU\shared_data\raw"
OUTPUT_PATH = r"C:\Users\KORISNIK\Desktop\MU\shared_data\processed\baza_podataka.csv"


#prolazimo kroz fajlove
files = glob.glob(os.path.join(BASE_PATH, "**", "*.json"), recursive=True)
#ova linija koda traži sve JSON fajlove u folderu koji je definisan sa BASE_PATH, ukljucujuci i sve njegove podfoldere.
#deo "**" znaci da pretraga ide rekurzivno kroz sve nivoe foldera, a "*.json" oznacava da se uzimaju samo fajlovi koji imaju ekstenziju .json
#funkcija glob.glob zatim vraca listu putanja svih pronadjenih fajlova koji odgovaraju tom obrascu

print(f"Pronadjeno fajlova: {len(files)}") #5200

#ucitavamo podatke
data_list = []

for file in files:
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        row = {
            "source": data.get("source"),
            "portal": data.get("portal"),
            "tag_page": data.get("tag_page"),
            "url": data.get("url"),
            "title": data.get("title"),
            "published_date": data.get("published_date"),
            "text": data.get("text")
        }

        data_list.append(row)

    except Exception as e:
        print(f"Greska u fajlu {file}: {e}")


#pravimo bazu podataka
df = pd.DataFrame(data_list)

#uklanjanjamo duplikate ako ih ima
df = df.drop_duplicates(subset="url")

#resetujemo indeks
df = df.reset_index(drop=True)

print(df)

print("\nDimenzija baze:")
print(df.shape) #(5200, 7)
print("\nKolone:")
print(df.columns) #['source', 'portal', 'tag_page', 'url', 'title', 'published_date', 'text']

print("\nBroj clanaka po portalu - sortirano:")
print(df["portal"].value_counts().sort_values(ascending=False))
#nova.rs        1670
#politika.rs    1121 
#danas.rs        895 
#blic.rs         765 
#n1info.rs       530 
#kurir.rs        219

print("\nProvera: da li svaki clanak ima tekst:")
print(df["text"].isna().sum()) #0 - ima!

#uklanjamo tab, nove redove i nepotrebne razmake
df["text"] = (
    df["text"]
    .astype(str)
    .str.replace(r"[\r\n\t]+", " ", regex=True)
    .str.strip()
)

#cuvanje baze
df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig",
    sep=";",
    quoting=csv.QUOTE_ALL
)

#provera da li je baza dobro ucitana
with open(OUTPUT_PATH, "r", encoding="utf-8-sig") as f:
    broj_redova = sum(1 for _ in f)

print(broj_redova) #5201

df2 = pd.read_csv(
    OUTPUT_PATH,
    sep=";",
    encoding="utf-8-sig"
)

print(df2.shape) #(5200,7)
#baza je dobra - svi podaci su tu!

print("\nBaza je spremna!")