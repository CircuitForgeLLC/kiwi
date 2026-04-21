"""
Recipe browser domain schemas.

Each domain provides a two-level category hierarchy for browsing the recipe corpus.
Keyword matching is case-insensitive against the recipes.category column and the
recipes.keywords JSON array. A recipe may appear in multiple categories (correct).

Category values are either:
  - list[str]  — flat keyword list (no subcategories)
  - dict       — {"keywords": list[str], "subcategories": {name: list[str]}}
                  keywords covers the whole category (used for "All X" browse);
                  subcategories each have their own narrower keyword list.

These are starter mappings based on the food.com dataset structure. Run:

    SELECT category, count(*) FROM recipes
    GROUP BY category ORDER BY count(*) DESC LIMIT 50;

against the corpus to verify coverage and refine keyword lists before the first
production deploy.
"""
from __future__ import annotations

DOMAINS: dict[str, dict] = {
    "cuisine": {
        "label": "Cuisine",
        "categories": {
            "Italian": {
                "keywords": ["italian", "pasta", "pizza", "risotto", "lasagna", "carbonara"],
                "subcategories": {
                    "Sicilian":   ["sicilian", "sicily", "arancini", "caponata",
                                   "involtini", "cannoli"],
                    "Neapolitan": ["neapolitan", "naples", "pizza napoletana",
                                   "sfogliatelle", "ragù"],
                    "Tuscan":     ["tuscan", "tuscany", "ribollita", "bistecca",
                                   "pappardelle", "crostini"],
                    "Roman":      ["roman", "rome", "cacio e pepe", "carbonara",
                                   "amatriciana", "gricia", "supplì"],
                    "Venetian":   ["venetian", "venice", "risotto", "bigoli",
                                   "baccalà", "sarde in saor"],
                    "Ligurian":   ["ligurian", "liguria", "pesto", "focaccia",
                                   "trofie", "farinata"],
                },
            },
            "Mexican": {
                "keywords": ["mexican", "taco", "enchilada", "burrito", "salsa",
                             "guacamole", "mole", "tamale"],
                "subcategories": {
                    "Oaxacan":      ["oaxacan", "oaxaca", "mole negro", "tlayuda",
                                     "chapulines", "mezcal", "tasajo", "memelas"],
                    "Yucatecan":    ["yucatecan", "yucatan", "cochinita pibil", "poc chuc",
                                     "sopa de lima", "panuchos", "papadzules"],
                    "Veracruz":     ["veracruz", "veracruzana", "huachinango",
                                     "picadas", "enfrijoladas", "caldo de mariscos"],
                    "Street Food":  ["taco", "elote", "tlacoyos", "torta", "tamale",
                                     "quesadilla", "tostada", "sope", "gordita"],
                    "Mole":         ["mole", "mole negro", "mole rojo", "mole verde",
                                     "mole poblano", "mole amarillo", "pipián"],
                    "Baja / Cal-Mex": ["baja", "baja california", "cal-mex", "baja fish taco",
                                       "fish taco", "carne asada fries", "california burrito",
                                       "birria", "birria tacos", "quesabirria",
                                       "lobster puerto nuevo", "tijuana", "ensenada",
                                       "agua fresca", "caesar salad tijuana"],
                    "Mexico City":  ["mexico city", "chilaquiles", "tlayuda cdmx",
                                     "tacos de canasta", "torta ahogada", "pozole",
                                     "chiles en nogada"],
                },
            },
            "Asian": {
                "keywords": ["asian", "chinese", "japanese", "thai", "korean", "vietnamese",
                             "stir fry", "stir-fry", "ramen", "sushi", "malaysian",
                             "taiwanese", "singaporean", "burmese", "cambodian",
                             "laotian", "mongolian", "hong kong"],
                "subcategories": {
                    "Korean":       ["korean", "kimchi", "bibimbap", "bulgogi", "japchae",
                                     "doenjang", "gochujang", "tteokbokki", "sundubu",
                                     "galbi", "jjigae", "kbbq", "korean fried chicken"],
                    "Japanese":     ["japanese", "sushi", "ramen", "tempura", "miso",
                                     "teriyaki", "udon", "soba", "bento", "yakitori",
                                     "tonkatsu", "onigiri", "okonomiyaki", "takoyaki",
                                     "kaiseki", "izakaya"],
                    "Chinese":      ["chinese", "dim sum", "fried rice", "dumplings", "wonton",
                                     "spring roll", "szechuan", "sichuan", "cantonese",
                                     "chow mein", "mapo tofu", "lo mein", "hot pot",
                                     "peking duck", "char siu", "congee"],
                    "Thai":         ["thai", "pad thai", "green curry", "red curry",
                                     "coconut milk", "lemongrass", "satay", "tom yum",
                                     "larb", "khao man gai", "massaman", "pad see ew"],
                    "Vietnamese":   ["vietnamese", "pho", "banh mi", "spring rolls",
                                     "vermicelli", "nuoc cham", "bun bo hue",
                                     "banh xeo", "com tam", "bun cha"],
                    "Filipino":     ["filipino", "adobo", "sinigang", "pancit", "lumpia",
                                     "kare-kare", "lechon", "sisig", "halo-halo",
                                     "dinuguan", "tinola", "bistek"],
                    "Indonesian":   ["indonesian", "rendang", "nasi goreng", "gado-gado",
                                     "tempeh", "sambal", "soto", "opor ayam",
                                     "bakso", "mie goreng", "nasi uduk"],
                    "Malaysian":    ["malaysian", "laksa", "nasi lemak", "char kway teow",
                                     "satay malaysia", "roti canai", "bak kut teh",
                                     "cendol", "mee goreng mamak", "curry laksa"],
                    "Taiwanese":    ["taiwanese", "beef noodle soup", "lu rou fan",
                                     "oyster vermicelli", "scallion pancake taiwan",
                                     "pork chop rice", "three cup chicken",
                                     "bubble tea", "stinky tofu", "ba wan"],
                    "Singaporean":  ["singaporean", "chicken rice", "chili crab",
                                     "singaporean laksa", "bak chor mee", "rojak",
                                     "kaya toast", "nasi padang", "satay singapore"],
                    "Burmese":      ["burmese", "myanmar", "mohinga", "laphet thoke",
                                     "tea leaf salad", "ohn no khao swe",
                                     "mont di", "nangyi thoke"],
                    "Hong Kong":    ["hong kong", "hk style", "pineapple bun",
                                     "wonton noodle soup", "hk milk tea", "egg tart",
                                     "typhoon shelter crab", "char siu bao", "jook",
                                     "congee hk", "silk stocking tea", "dan tat",
                                     "siu mai hk", "cheung fun"],
                    "Cambodian":    ["cambodian", "khmer", "amok", "lok lak",
                                     "kuy teav", "bai sach chrouk", "nom banh chok",
                                     "samlor korko", "beef loc lac"],
                    "Laotian":      ["laotian", "lao", "larb", "tam mak hoong",
                                     "or lam", "khao niaw", "ping kai",
                                     "naem khao", "khao piak sen", "mok pa"],
                    "Mongolian":    ["mongolian", "buuz", "khuushuur", "tsuivan",
                                     "boodog", "airag", "khorkhog", "bansh",
                                     "guriltai shol", "suutei tsai"],
                    "South Asian Fusion": ["south asian fusion", "indo-chinese",
                                           "hakka chinese", "chilli chicken",
                                           "manchurian", "schezwan"],
                },
            },
            "Indian": {
                "keywords": ["indian", "curry", "lentil", "dal", "tikka", "masala",
                             "biryani", "naan", "chutney", "pakistani", "sri lankan",
                             "bangladeshi", "nepali"],
                "subcategories": {
                    "North Indian":  ["north indian", "punjabi", "mughal", "tikka masala",
                                      "naan", "tandoori", "butter chicken", "palak paneer",
                                      "chole", "rajma", "aloo gobi"],
                    "South Indian":  ["south indian", "tamil", "kerala", "dosa", "idli",
                                      "sambar", "rasam", "coconut chutney", "appam",
                                      "fish curry kerala", "puttu", "payasam"],
                    "Bengali":       ["bengali", "mustard fish", "hilsa", "shorshe ilish",
                                      "mishti doi", "rasgulla", "kosha mangsho"],
                    "Gujarati":      ["gujarati", "dhokla", "thepla", "undhiyu",
                                      "khandvi", "fafda", "gujarati dal"],
                    "Pakistani":     ["pakistani", "nihari", "haleem", "seekh kebab",
                                      "karahi", "biryani karachi", "chapli kebab",
                                      "halwa puri", "paya"],
                    "Sri Lankan":    ["sri lankan", "kottu roti", "hoppers", "pol sambol",
                                      "sri lankan curry", "lamprais", "string hoppers",
                                      "wambatu moju"],
                    "Bangladeshi":   ["bangladeshi", "bangladesh", "dhaka biryani",
                                      "shutki", "pitha", "hilsa curry", "kacchi biryani",
                                      "bhuna khichuri", "doi maach", "rezala"],
                    "Nepali":        ["nepali", "dal bhat", "momos", "sekuwa",
                                      "sel roti", "gundruk", "thukpa"],
                },
            },
            "Mediterranean": {
                "keywords": ["mediterranean", "greek", "middle eastern", "turkish",
                             "lebanese", "jewish", "palestinian", "yemeni", "egyptian",
                             "syrian", "iraqi", "jordanian"],
                "subcategories": {
                    "Greek":          ["greek", "feta", "tzatziki", "moussaka", "spanakopita",
                                       "souvlaki", "dolmades", "spanakopita", "tiropita",
                                       "galaktoboureko"],
                    "Turkish":        ["turkish", "kebab", "borek", "meze", "baklava",
                                       "lahmacun", "menemen", "pide", "iskender",
                                       "kisir", "simit"],
                    "Syrian":         ["syrian", "fattet hummus", "kibbeh syria",
                                       "muhammara", "maklouba syria", "sfeeha",
                                       "halawet el jibn"],
                    "Lebanese":       ["lebanese", "middle eastern", "hummus", "falafel",
                                       "tabbouleh", "kibbeh", "fattoush", "manakish",
                                       "kafta", "sfiha"],
                    "Jewish":         ["jewish", "israeli", "ashkenazi", "sephardic",
                                       "shakshuka", "sabich", "za'atar", "tahini",
                                       "zhug", "zhoug", "s'khug", "z'houg",
                                       "hawaiij", "hawaij", "hawayej",
                                       "matzo", "latke", "rugelach", "babka", "challah",
                                       "cholent", "gefilte fish", "brisket", "kugel",
                                       "new york jewish", "new york deli", "pastrami",
                                       "knish", "lox", "bagel and lox", "jewish deli"],
                    "Palestinian":    ["palestinian", "musakhan", "maqluba", "knafeh",
                                       "maftoul", "freekeh", "sumac chicken"],
                    "Yemeni":         ["yemeni", "saltah", "lahoh", "bint al-sahn",
                                       "zhug", "zhoug", "hulba", "fahsa",
                                       "hawaiij", "hawaij", "hawayej"],
                    "Egyptian":       ["egyptian", "koshari", "molokhia", "mahshi",
                                       "ful medames", "ta'ameya", "feteer meshaltet"],
                },
            },
            "American": {
                "keywords": ["american", "southern", "comfort food", "cajun", "creole",
                             "hawaiian", "tex-mex", "soul food"],
                "subcategories": {
                    "Southern":     ["southern", "soul food", "fried chicken",
                                     "collard greens", "cornbread", "biscuits and gravy",
                                     "mac and cheese", "sweet potato pie", "okra"],
                    "Cajun/Creole": ["cajun", "creole", "new orleans", "gumbo",
                                     "jambalaya", "etouffee", "dirty rice", "po'boy",
                                     "muffuletta", "red beans and rice"],
                    "Tex-Mex":      ["tex-mex", "southwestern", "chili", "fajita",
                                     "queso", "breakfast taco", "chile con carne"],
                    "New England":  ["new england", "chowder", "lobster", "clam",
                                     "maple", "yankee", "boston baked beans",
                                     "johnnycake", "fish and chips"],
                    "Pacific Northwest": ["pacific northwest", "pnw", "dungeness crab",
                                          "salmon", "cedar plank", "razor clam",
                                          "geoduck", "chanterelle", "marionberry"],
                    "Hawaiian":     ["hawaiian", "hawaii", "plate lunch", "loco moco",
                                     "poke", "spam musubi", "kalua pig", "lau lau",
                                     "haupia", "poi", "manapua", "garlic shrimp",
                                     "saimin", "huli huli", "malasada"],
                },
            },
            "BBQ & Smoke": {
                "keywords": ["bbq", "barbecue", "smoked", "pit", "smoke ring",
                             "low and slow", "brisket", "pulled pork", "ribs"],
                "subcategories": {
                    "Texas BBQ":       ["texas bbq", "central texas bbq", "brisket",
                                        "beef ribs", "post oak", "salt and pepper rub",
                                        "east texas bbq", "lockhart", "franklin style"],
                    "Carolina BBQ":    ["carolina bbq", "north carolina bbq", "whole hog",
                                        "vinegar sauce", "lexington style", "eastern nc",
                                        "south carolina bbq", "mustard sauce"],
                    "Kansas City BBQ": ["kansas city bbq", "kc bbq", "burnt ends",
                                        "sweet bbq sauce", "tomato molasses sauce",
                                        "baby back ribs kc"],
                    "Memphis BBQ":     ["memphis bbq", "dry rub ribs", "wet ribs",
                                        "memphis style", "dry rub pork"],
                    "Alabama BBQ":     ["alabama bbq", "white sauce", "alabama white sauce",
                                        "smoked chicken alabama"],
                    "Kentucky BBQ":    ["kentucky bbq", "mutton bbq", "owensboro bbq",
                                        "black dip", "western kentucky barbecue"],
                    "St. Louis BBQ":   ["st louis bbq", "st. louis ribs", "st louis cut ribs",
                                        "st louis style spare ribs"],
                    "Backyard Grill":  ["backyard bbq", "cookout", "grilled burgers",
                                        "charcoal grill", "kettle grill", "tailgate"],
                },
            },
            "European": {
                "keywords": ["french", "german", "spanish", "british", "irish", "scottish",
                             "welsh", "scandinavian", "nordic", "eastern european"],
                "subcategories": {
                    "French":        ["french", "provencal", "beurre", "crepe",
                                      "ratatouille", "cassoulet", "bouillabaisse"],
                    "Spanish":       ["spanish", "paella", "tapas", "gazpacho",
                                      "tortilla espanola", "chorizo"],
                    "German":        ["german", "bratwurst", "sauerkraut", "schnitzel",
                                      "pretzel", "strudel"],
                    "British":       ["british", "english", "pub food", "cornish",
                                      "shepherd's pie", "bangers", "toad in the hole",
                                      "coronation chicken", "london", "londoner",
                                      "cornish pasty", "ploughman's"],
                    "Irish":         ["irish", "ireland", "colcannon", "coddle",
                                      "irish stew", "soda bread", "boxty", "champ"],
                    "Scottish":      ["scottish", "scotland", "haggis", "cullen skink",
                                      "cranachan", "scotch broth", "glaswegian",
                                      "neeps and tatties", "tablet"],
                    "Scandinavian":  ["scandinavian", "nordic", "swedish", "norwegian",
                                      "danish", "finnish", "gravlax", "swedish meatballs",
                                      "lefse", "smörgåsbord", "fika", "crispbread",
                                      "cardamom bun", "herring", "æbleskiver",
                                      "lingonberry", "lutefisk", "janssons frestelse",
                                      "knäckebröd", "kladdkaka"],
                    "Eastern European": ["eastern european", "polish", "russian", "ukrainian",
                                         "czech", "hungarian", "pierogi", "borscht",
                                         "goulash", "kielbasa", "varenyky", "pelmeni"],
                },
            },
            "Latin American": {
                "keywords": ["latin american", "peruvian", "argentinian", "colombian",
                             "cuban", "caribbean", "brazilian", "venezuelan", "chilean"],
                "subcategories": {
                    "Peruvian":    ["peruvian", "ceviche", "lomo saltado", "anticucho",
                                    "aji amarillo", "causa", "leche de tigre",
                                    "arroz con leche peru", "pollo a la brasa"],
                    "Brazilian":   ["brazilian", "churrasco", "feijoada", "pao de queijo",
                                    "brigadeiro", "coxinha", "moqueca", "vatapa",
                                    "caipirinha", "acai bowl"],
                    "Colombian":   ["colombian", "bandeja paisa", "arepas", "empanadas",
                                    "sancocho", "ajiaco", "buñuelos", "changua"],
                    "Argentinian": ["argentinian", "asado", "chimichurri", "empanadas argentina",
                                    "milanesa", "locro", "dulce de leche", "medialunas"],
                    "Venezuelan":  ["venezuelan", "pabellón criollo", "arepas venezuela",
                                    "hallacas", "cachapas", "tequeños", "caraotas"],
                    "Chilean":     ["chilean", "cazuela", "pastel de choclo", "curanto",
                                    "sopaipillas", "charquicán", "completo"],
                    "Cuban":       ["cuban", "ropa vieja", "moros y cristianos",
                                    "picadillo", "lechon cubano", "vaca frita",
                                    "tostones", "platanos maduros"],
                    "Jamaican":    ["jamaican", "jerk chicken", "jerk pork", "ackee saltfish",
                                    "curry goat", "rice and peas", "escovitch",
                                    "jamaican patty", "callaloo jamaica", "festival"],
                    "Puerto Rican": ["puerto rican", "mofongo", "pernil", "arroz con gandules",
                                     "sofrito", "pasteles", "tostones pr", "tembleque",
                                     "coquito", "asopao"],
                    "Dominican":   ["dominican", "mangu", "sancocho dominicano",
                                    "pollo guisado", "habichuelas guisadas",
                                    "tostones dominicanos", "morir soñando"],
                    "Haitian":     ["haitian", "griot", "pikliz", "riz et pois",
                                    "joumou", "akra", "pain patate", "labouyi"],
                    "Trinidad":    ["trinidadian", "doubles", "roti trinidad", "pelau",
                                    "callaloo trinidad", "bake and shark",
                                    "curry duck", "oil down"],
                },
            },
            "Central American": {
                "keywords": ["central american", "salvadoran", "guatemalan",
                             "honduran", "nicaraguan", "costa rican", "panamanian"],
                "subcategories": {
                    "Salvadoran":   ["salvadoran", "el salvador", "pupusas", "curtido",
                                     "sopa de pata", "nuégados", "atol shuco"],
                    "Guatemalan":   ["guatemalan", "pepián", "jocon", "kak'ik",
                                     "hilachas", "rellenitos", "fiambre"],
                    "Costa Rican":  ["costa rican", "gallo pinto", "casado",
                                     "olla de carne", "arroz con leche cr",
                                     "tres leches cr"],
                    "Honduran":     ["honduran", "baleadas", "sopa de caracol",
                                     "tapado", "machuca", "catrachitas"],
                    "Nicaraguan":   ["nicaraguan", "nacatamal", "vigorón", "indio viejo",
                                     "gallo pinto nicaragua", "güirilas"],
                },
            },
            "African": {
                "keywords": ["african", "west african", "east african", "ethiopian",
                             "nigerian", "ghanaian", "kenyan", "south african",
                             "senegalese", "tunisian"],
                "subcategories": {
                    "West African":        ["west african", "nigerian", "ghanaian",
                                            "jollof rice", "egusi soup", "fufu", "suya",
                                            "groundnut stew", "kelewele", "kontomire",
                                            "waakye", "ofam", "bitterleaf soup"],
                    "Senegalese":          ["senegalese", "senegal", "thieboudienne",
                                            "yassa", "mafe", "thiou", "ceebu jen",
                                            "domoda"],
                    "Ethiopian & Eritrean": ["ethiopian", "eritrean", "injera", "doro wat",
                                             "kitfo", "tibs", "shiro", "misir wat",
                                             "gomen", "ful ethiopian", "tegamino"],
                    "East African":        ["east african", "kenyan", "tanzanian", "ugandan",
                                            "nyama choma", "ugali", "sukuma wiki",
                                            "pilau kenya", "mandazi", "matoke",
                                            "githeri", "irio"],
                    "North African":       ["north african", "tunisian", "algerian", "libyan",
                                            "brik", "lablabi", "merguez", "shakshuka tunisian",
                                            "harissa tunisian", "couscous algerian"],
                    "South African":       ["south african", "braai", "bobotie", "boerewors",
                                            "bunny chow", "pap", "chakalaka", "biltong",
                                            "malva pudding", "koeksister", "potjiekos"],
                    "Moroccan":            ["moroccan", "tagine", "couscous morocco",
                                            "harissa", "chermoula", "preserved lemon",
                                            "pastilla", "mechoui", "bastilla"],
                },
            },
            "Pacific & Oceania": {
                "keywords": ["pacific", "oceania", "polynesian", "melanesian",
                             "micronesian", "maori", "fijian", "samoan", "tongan",
                             "hawaiian", "australian", "new zealand"],
                "subcategories": {
                    "Māori / New Zealand": ["maori", "new zealand", "hangi", "rewena bread",
                                            "boil-up", "paua", "kumara", "pavlova nz",
                                            "whitebait fritter", "kina", "hokey pokey"],
                    "Australian":          ["australian", "meat pie", "lamington",
                                            "anzac biscuits", "damper", "barramundi",
                                            "vegemite", "pavlova australia", "tim tam",
                                            "sausage sizzle", "chiko roll", "fairy bread"],
                    "Fijian":              ["fijian", "fiji", "kokoda", "lovo",
                                            "rourou", "palusami fiji", "duruka",
                                            "vakalolo"],
                    "Samoan":              ["samoan", "samoa", "palusami", "oka",
                                            "fa'ausi", "chop suey samoa", "sapasui",
                                            "koko alaisa", "supo esi"],
                    "Tongan":              ["tongan", "tonga", "lu pulu", "'ota 'ika",
                                            "fekkai", "faikakai topai", "kapisi pulu"],
                    "Papua New Guinean":   ["papua new guinea", "png", "mumu",
                                            "sago", "aibika", "kaukau",
                                            "taro png", "coconut crab"],
                    "Hawaiian":            ["hawaiian", "hawaii", "poke", "loco moco",
                                            "plate lunch", "kalua pig", "haupia",
                                            "spam musubi", "poi", "malasada"],
                },
            },
            "Central Asian & Caucasus": {
                "keywords": ["central asian", "caucasus", "georgian", "armenian", "uzbek",
                             "afghan", "persian", "iranian", "azerbaijani", "kazakh"],
                "subcategories": {
                    "Persian / Iranian": ["persian", "iranian", "ghormeh sabzi", "fesenjan",
                                          "tahdig", "joojeh kabab", "ash reshteh",
                                          "zereshk polo", "khoresh", "mast o khiar",
                                          "kashk-e-bademjan", "mirza ghasemi",
                                          "baghali polo"],
                    "Georgian":          ["georgian", "georgia", "khachapuri", "khinkali",
                                          "churchkhela", "ajapsandali", "satsivi",
                                          "pkhali", "lobiani", "badrijani nigvzit"],
                    "Armenian":          ["armenian", "dolma armenia", "lahmajoun",
                                          "manti armenia", "ghapama", "basturma",
                                          "harissa armenia", "nazook", "tolma"],
                    "Azerbaijani":       ["azerbaijani", "azerbaijan", "plov azerbaijan",
                                          "dolma azeri", "dushbara", "levengi",
                                          "shah plov", "gutab"],
                    "Uzbek":             ["uzbek", "uzbekistan", "plov", "samsa",
                                          "lagman", "shashlik", "manti uzbek",
                                          "non bread", "dimlama", "sumalak"],
                    "Afghan":            ["afghan", "afghanistan", "kabuli pulao", "mantu",
                                          "bolani", "qorma", "ashak", "shorwa",
                                          "aushak", "borani banjan"],
                    "Kazakh":            ["kazakh", "beshbarmak", "kuyrdak", "baursak",
                                          "kurt", "shubat", "kazy"],
                },
            },
        },
    },
    "meal_type": {
        "label": "Meal Type",
        "categories": {
            "Breakfast": {
                "keywords": ["breakfast", "brunch", "eggs", "pancakes", "waffles",
                             "oatmeal", "muffin"],
                "subcategories": {
                    "Eggs":              ["egg", "omelette", "frittata", "quiche",
                                          "scrambled", "benedict", "shakshuka"],
                    "Pancakes & Waffles": ["pancake", "waffle", "crepe", "french toast"],
                    "Baked Goods":       ["muffin", "scone", "biscuit", "quick bread",
                                          "coffee cake", "danish"],
                    "Oats & Grains":     ["oatmeal", "granola", "porridge", "muesli",
                                          "overnight oats"],
                },
            },
            "Lunch": {
                "keywords": ["lunch", "sandwich", "wrap", "salad", "soup", "light meal"],
                "subcategories": {
                    "Sandwiches": ["sandwich", "sub", "hoagie", "panini", "club",
                                   "grilled cheese", "blt"],
                    "Salads":     ["salad", "grain bowl", "chopped", "caesar",
                                   "niçoise", "cobb"],
                    "Soups":      ["soup", "bisque", "chowder", "gazpacho",
                                   "minestrone", "lentil soup"],
                    "Wraps":      ["wrap", "burrito bowl", "pita", "lettuce wrap",
                                   "quesadilla"],
                },
            },
            "Dinner": {
                "keywords": ["dinner", "main dish", "entree", "main course", "supper"],
                "subcategories": {
                    "Casseroles": ["casserole", "bake", "gratin", "lasagna",
                                   "sheperd's pie", "pot pie"],
                    "Stews":      ["stew", "braise", "slow cooker", "pot roast",
                                   "daube", "ragù"],
                    "Grilled":    ["grilled", "grill", "barbecue", "charred",
                                   "kebab", "skewer"],
                    "Stir-Fries": ["stir fry", "stir-fry", "wok", "sauté",
                                   "sauteed"],
                    "Roasts":     ["roast", "roasted", "oven", "baked chicken",
                                   "pot roast"],
                },
            },
            "Snack": {
                "keywords": ["snack", "appetizer", "finger food", "dip", "bite",
                             "starter"],
                "subcategories": {
                    "Dips & Spreads": ["dip", "spread", "hummus", "guacamole",
                                       "salsa", "pate"],
                    "Finger Foods":   ["finger food", "bite", "skewer", "slider",
                                       "wing", "nugget"],
                    "Chips & Crackers": ["chip", "cracker", "crisp", "popcorn",
                                          "pretzel"],
                },
            },
            "Dessert": {
                "keywords": ["dessert", "cake", "cookie", "pie", "sweet", "pudding",
                             "ice cream", "brownie"],
                "subcategories": {
                    "Cakes":         ["cake", "cupcake", "layer cake", "bundt",
                                      "cheesecake", "torte"],
                    "Cookies & Bars": ["cookie", "brownie", "blondie", "bar",
                                       "biscotti", "shortbread"],
                    "Pies & Tarts":  ["pie", "tart", "galette", "cobbler", "crisp",
                                       "crumble"],
                    "Frozen":        ["ice cream", "gelato", "sorbet", "frozen dessert",
                                      "popsicle", "granita"],
                    "Puddings":      ["pudding", "custard", "mousse", "panna cotta",
                                      "flan", "creme brulee"],
                    "Candy":         ["candy", "fudge", "truffle", "brittle",
                                      "caramel", "toffee"],
                },
            },
            "Beverage": ["drink", "smoothie", "cocktail", "beverage", "juice", "shake"],
            "Side Dish": ["side dish", "side", "accompaniment", "garnish"],
        },
    },
    "dietary": {
        "label": "Dietary",
        "categories": {
            "Vegetarian":   ["vegetarian"],
            "Vegan":        ["vegan", "plant-based", "plant based"],
            "Gluten-Free":  ["gluten-free", "gluten free", "celiac"],
            "Low-Carb":     ["low-carb", "low carb", "keto", "ketogenic"],
            "High-Protein": ["high protein", "high-protein"],
            "Low-Fat":      ["low-fat", "low fat", "light"],
            "Dairy-Free":   ["dairy-free", "dairy free", "lactose"],
        },
    },
    "main_ingredient": {
        "label": "Main Ingredient",
        "categories": {
            # keywords use exact inferred_tag strings (main:X) — indexed into recipe_browser_fts.
            "Chicken": {
                "keywords": ["main:Chicken"],
                "subcategories": {
                    "Baked":    ["baked chicken", "roast chicken", "chicken casserole",
                                 "chicken bake"],
                    "Grilled":  ["grilled chicken", "chicken kebab", "bbq chicken",
                                 "chicken skewer"],
                    "Fried":    ["fried chicken", "chicken cutlet", "chicken schnitzel",
                                 "crispy chicken"],
                    "Stewed":   ["chicken stew", "chicken soup", "coq au vin",
                                 "chicken curry", "chicken braise"],
                },
            },
            "Beef": {
                "keywords": ["main:Beef"],
                "subcategories": {
                    "Ground Beef": ["ground beef", "hamburger", "meatball", "meatloaf",
                                    "bolognese", "burger"],
                    "Steak":       ["steak", "sirloin", "ribeye", "flank steak",
                                    "filet mignon", "t-bone"],
                    "Roasts":      ["beef roast", "pot roast", "brisket", "prime rib",
                                    "chuck roast"],
                    "Stews":       ["beef stew", "beef braise", "beef bourguignon",
                                    "short ribs"],
                },
            },
            "Pork": {
                "keywords": ["main:Pork"],
                "subcategories": {
                    "Chops":        ["pork chop", "pork loin", "pork cutlet"],
                    "Pulled/Slow":  ["pulled pork", "pork shoulder", "pork butt",
                                     "carnitas", "slow cooker pork"],
                    "Sausage":      ["sausage", "bratwurst", "chorizo", "andouille",
                                     "Italian sausage"],
                    "Ribs":         ["pork ribs", "baby back ribs", "spare ribs",
                                     "pork belly"],
                },
            },
            "Fish": {
                "keywords": ["main:Fish"],
                "subcategories": {
                    "Salmon":    ["salmon", "smoked salmon", "gravlax"],
                    "Tuna":      ["tuna", "albacore", "ahi"],
                    "White Fish": ["cod", "tilapia", "halibut", "sole", "snapper",
                                   "flounder", "bass"],
                    "Shellfish": ["shrimp", "prawn", "crab", "lobster", "scallop",
                                  "mussel", "clam", "oyster"],
                },
            },
            "Pasta":      ["main:Pasta"],
            "Vegetables": {
                "keywords": ["main:Vegetables"],
                "subcategories": {
                    "Root Veg":    ["potato", "sweet potato", "carrot", "beet",
                                    "parsnip", "turnip"],
                    "Leafy":       ["spinach", "kale", "chard", "arugula",
                                    "collard greens", "lettuce"],
                    "Brassicas":   ["broccoli", "cauliflower", "brussels sprouts",
                                    "cabbage", "bok choy"],
                    "Nightshades": ["tomato", "eggplant", "bell pepper", "zucchini",
                                    "squash"],
                    "Mushrooms":   ["mushroom", "portobello", "shiitake", "oyster mushroom",
                                    "chanterelle"],
                },
            },
            "Eggs":    ["main:Eggs"],
            "Legumes": ["main:Legumes"],
            "Grains":  ["main:Grains"],
            "Cheese":  ["main:Cheese"],
        },
    },
}


def _get_category_def(domain: str, category: str) -> list[str] | dict | None:
    """Return the raw category definition, or None if not found."""
    return DOMAINS.get(domain, {}).get("categories", {}).get(category)


def get_domain_labels() -> list[dict]:
    """Return [{id, label}] for all available domains."""
    return [{"id": k, "label": v["label"]} for k, v in DOMAINS.items()]


def get_keywords_for_category(domain: str, category: str) -> list[str]:
    """Return the keyword list for the category (top-level, covers all subcategories).

    For flat categories returns the list directly.
    For nested categories returns the 'keywords' key.
    Returns [] if category or domain not found.
    """
    cat_def = _get_category_def(domain, category)
    if cat_def is None:
        return []
    if isinstance(cat_def, list):
        return cat_def
    return cat_def.get("keywords", [])


def category_has_subcategories(domain: str, category: str) -> bool:
    """Return True when a category has a subcategory level."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return False
    return bool(cat_def.get("subcategories"))


def get_subcategory_names(domain: str, category: str) -> list[str]:
    """Return subcategory names for a category, or [] if none exist."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return []
    return list(cat_def.get("subcategories", {}).keys())


def get_keywords_for_subcategory(domain: str, category: str, subcategory: str) -> list[str]:
    """Return keyword list for a specific subcategory, or [] if not found."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return []
    return cat_def.get("subcategories", {}).get(subcategory, [])


def get_category_names(domain: str) -> list[str]:
    """Return category names for a domain, or [] if domain unknown."""
    domain_data = DOMAINS.get(domain, {})
    return list(domain_data.get("categories", {}).keys())
