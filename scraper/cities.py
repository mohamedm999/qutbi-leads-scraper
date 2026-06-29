# Moroccan cities to scrape barbershops from
# Each entry: (city_name, latitude, longitude, search_radius_km)

MOROCCAN_CITIES = [
    ("Casablanca", 33.5731, -7.5898, 15),
    ("Rabat", 34.0209, -6.8416, 12),
    ("Marrakech", 31.6295, -7.9811, 12),
    ("Fes", 34.0331, -5.0003, 12),
    ("Tangier", 35.7595, -5.8340, 12),
    ("Agadir", 30.4278, -9.5981, 10),
    ("Meknes", 33.8731, -5.5407, 10),
    ("Oujda", 34.6814, -1.9086, 10),
    ("Kenitra", 34.2610, -6.5802, 10),
    ("Tetouan", 35.5785, -5.3684, 10),
    ("Sale", 34.0531, -6.7985, 10),
    ("Temara", 33.9255, -6.9150, 8),
    ("El Jadida", 33.2504, -8.5025, 8),
    ("Nador", 35.1681, -2.9287, 8),
    ("Beni Mellal", 32.3373, -6.3505, 8),
    ("Mohammedia", 33.6863, -7.3830, 8),
    ("Khouribga", 32.8811, -6.9064, 8),
    ("Settat", 33.0018, -7.6168, 8),
    ("Taza", 34.2130, -4.0160, 8),
    ("Safi", 32.2983, -9.2372, 8),
]

# Search queries in multiple languages to maximize results
SEARCH_QUERIES = [
    "barbershop",
    "salon de coiffure homme",
    "coiffeur homme",
    "barbier",
    "حلاق",
    "صالون حلاقة",
    "men's hair salon",
    "barber shop",
]