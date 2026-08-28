"""
country_codes.py

Maps this site's 3-letter country codes (used throughout club_metadata.json,
rankings.json, confederation_mapping.json) to:
  - flag_code: the code used by the flag-icons library (lipis/flag-icons),
    mostly ISO 3166-1 alpha-2, with special handling for UK home nations
    (gb-eng/gb-sct/gb-wls/gb-nir) and Kosovo (xk).
  - name: a readable country/nation name, for dropdown labels etc.

Only covers the 150 codes actually present in club_metadata.json. Built by
hand against ISO 3166-1 alpha-2 - flag football-specific entities (England,
Scotland, Wales, N. Ireland, Kosovo, Gibraltar, Hong Kong, Chinese Taipei)
were checked individually since these are exactly where a naive ISO mapping
breaks down.
"""

COUNTRY_INFO = {
    "ALB": ("al", "Albania"), "ALG": ("dz", "Algeria"), "AND": ("ad", "Andorra"),
    "ANG": ("ao", "Angola"), "ARG": ("ar", "Argentina"), "ARM": ("am", "Armenia"),
    "ARU": ("aw", "Aruba"), "ATG": ("ag", "Antigua and Barbuda"), "AUS": ("au", "Australia"),
    "AUT": ("at", "Austria"), "AZE": ("az", "Azerbaijan"), "BAN": ("bd", "Bangladesh"),
    "BDI": ("bi", "Burundi"), "BEL": ("be", "Belgium"), "BEN": ("bj", "Benin"),
    "BFA": ("bf", "Burkina Faso"), "BHR": ("bh", "Bahrain"), "BHU": ("bt", "Bhutan"),
    "BIH": ("ba", "Bosnia and Herzegovina"), "BLR": ("by", "Belarus"), "BLZ": ("bz", "Belize"),
    "BOL": ("bo", "Bolivia"), "BOT": ("bw", "Botswana"), "BRA": ("br", "Brazil"),
    "BRB": ("bb", "Barbados"), "BUL": ("bg", "Bulgaria"), "CAM": ("kh", "Cambodia"),
    "CAN": ("ca", "Canada"), "CHI": ("cl", "Chile"), "CHN": ("cn", "China"),
    "CIV": ("ci", "Ivory Coast"), "CMR": ("cm", "Cameroon"), "COL": ("co", "Colombia"),
    "CRC": ("cr", "Costa Rica"), "CRO": ("hr", "Croatia"), "CYP": ("cy", "Cyprus"),
    "CZE": ("cz", "Czechia"), "DEN": ("dk", "Denmark"), "DOM": ("do", "Dominican Republic"),
    "ECU": ("ec", "Ecuador"), "EGY": ("eg", "Egypt"), "ENG": ("gb-eng", "England"),
    "ESP": ("es", "Spain"), "EST": ("ee", "Estonia"), "ETH": ("et", "Ethiopia"),
    "FIJ": ("fj", "Fiji"), "FIN": ("fi", "Finland"), "FRA": ("fr", "France"),
    "FRO": ("fo", "Faroe Islands"), "GAB": ("ga", "Gabon"), "GAM": ("gm", "Gambia"),
    "GEO": ("ge", "Georgia"), "GER": ("de", "Germany"), "GHA": ("gh", "Ghana"),
    "GIB": ("gi", "Gibraltar"), "GRE": ("gr", "Greece"), "GRN": ("gd", "Grenada"),
    "GUA": ("gt", "Guatemala"), "GUI": ("gn", "Guinea"), "HAI": ("ht", "Haiti"),
    "HKG": ("hk", "Hong Kong"), "HON": ("hn", "Honduras"), "HUN": ("hu", "Hungary"),
    "IDN": ("id", "Indonesia"), "IND": ("in", "India"), "IRL": ("ie", "Ireland"),
    "IRN": ("ir", "Iran"), "IRQ": ("iq", "Iraq"), "ISL": ("is", "Iceland"),
    "ISR": ("il", "Israel"), "ITA": ("it", "Italy"), "JAM": ("jm", "Jamaica"),
    "JOR": ("jo", "Jordan"), "JPN": ("jp", "Japan"), "KAZ": ("kz", "Kazakhstan"),
    "KEN": ("ke", "Kenya"), "KGZ": ("kg", "Kyrgyzstan"), "KOR": ("kr", "South Korea"),
    "KOS": ("xk", "Kosovo"), "KSA": ("sa", "Saudi Arabia"), "KUW": ("kw", "Kuwait"),
    "LAO": ("la", "Laos"), "LBN": ("lb", "Lebanon"), "LBR": ("lr", "Liberia"),
    "LBY": ("ly", "Libya"), "LES": ("ls", "Lesotho"), "LTU": ("lt", "Lithuania"),
    "LUX": ("lu", "Luxembourg"), "LVA": ("lv", "Latvia"), "MAC": ("mo", "Macau"),
    "MAR": ("ma", "Morocco"), "MAS": ("my", "Malaysia"), "MEX": ("mx", "Mexico"),
    "MKD": ("mk", "North Macedonia"), "MLI": ("ml", "Mali"), "MLT": ("mt", "Malta"),
    "MNE": ("me", "Montenegro"), "MTN": ("mr", "Mauritania"), "MWI": ("mw", "Malawi"),
    "MYA": ("mm", "Myanmar"), "NCA": ("ni", "Nicaragua"), "NED": ("nl", "Netherlands"),
    "NGA": ("ng", "Nigeria"), "NIR": ("gb-nir", "Northern Ireland"), "NOR": ("no", "Norway"),
    "NZL": ("nz", "New Zealand"),
    "OMA": ("om", "Oman"), "PAN": ("pa", "Panama"), "PAR": ("py", "Paraguay"),
    "PER": ("pe", "Peru"), "PHI": ("ph", "Philippines"), "PNG": ("pg", "Papua New Guinea"),
    "POL": ("pl", "Poland"), "POR": ("pt", "Portugal"), "QAT": ("qa", "Qatar"),
    "ROU": ("ro", "Romania"), "RSA": ("za", "South Africa"), "RUS": ("ru", "Russia"),
    "RWA": ("rw", "Rwanda"), "SCO": ("gb-sct", "Scotland"), "SDN": ("sd", "Sudan"),
    "SEN": ("sn", "Senegal"), "SGP": ("sg", "Singapore"), "SLV": ("sv", "El Salvador"),
    "SMR": ("sm", "San Marino"), "SRB": ("rs", "Serbia"), "SUI": ("ch", "Switzerland"),
    "SUR": ("sr", "Suriname"), "SVK": ("sk", "Slovakia"), "SVN": ("si", "Slovenia"),
    "SWE": ("se", "Sweden"), "SWZ": ("sz", "Eswatini"), "SYR": ("sy", "Syria"),
    "TAN": ("tz", "Tanzania"), "THA": ("th", "Thailand"), "TKM": ("tm", "Turkmenistan"),
    "TPE": ("tw", "Chinese Taipei"), "TRI": ("tt", "Trinidad and Tobago"), "TUN": ("tn", "Tunisia"),
    "TUR": ("tr", "Turkey"), "UAE": ("ae", "United Arab Emirates"), "UGA": ("ug", "Uganda"),
    "UKR": ("ua", "Ukraine"), "URU": ("uy", "Uruguay"), "USA": ("us", "United States"),
    "UZB": ("uz", "Uzbekistan"), "VEN": ("ve", "Venezuela"), "VIE": ("vn", "Vietnam"),
    "WAL": ("gb-wls", "Wales"), "ZAM": ("zm", "Zambia"), "ZIM": ("zw", "Zimbabwe"),
}


def flag_span(country_code: str) -> str:
    """Returns the <span> for the flag-icons CSS library, or an empty
    string if the country code isn't recognized (fails safe/blank rather
    than showing a wrong flag)."""
    info = COUNTRY_INFO.get(country_code)
    if not info:
        return ""
    flag_code = info[0]
    return f'<span class="fi fi-{flag_code}"></span>'


def country_name(country_code: str) -> str:
    info = COUNTRY_INFO.get(country_code)
    return info[1] if info else country_code
