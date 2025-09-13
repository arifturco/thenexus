from collections import defaultdict

# CSV'den okunan veya verdiğin eşleşmeler listesi
matches = [
    "Melih Can,Çağrı Akpınar",
    "Enes Acar,Ufuk Can",
    "Jan Anter,Sadi Kaymak",
    "Arif Türk,Çağlar Akkoç",
    "Diyar Mencutekin,Eren Scoretzka",
    "Enes Acar,Ramazan Kaya",
    "Miraç Karataş,Sadi Kaymak",
    "Ufuk Can,Çağlar Akkoç",
    "Khalat Barzani,Mostafa Mahna",
    # ... buraya tüm eşleşmeleri ekle
]

# Her takımın rakiplerini saklamak için dict
opponents = defaultdict(set)

for match in matches:
    a, b = match.split(",")
    opponents[a].add(b)
    opponents[b].add(a)  # çift yönlü

# Sonuçları yazdır
for team, opps in opponents.items():
    count = len(opps)
    flag = "⚠️" if count > 8 else ""
    print(f"{team}: {count} rakip {flag}")
