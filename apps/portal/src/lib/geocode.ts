// A tiny local geocoder for the five demo metros (NYC, Newark, Trenton, Chicago, Miami). No network call.
// It finds a 5-digit ZIP, then a 3-digit ZIP prefix, then a city or neighborhood name. Coordinates are
// approximate centroids: good enough to pick the nearest settlement station, not to find your door.
// Anything else falls back to typing latitude and longitude by hand.

export type Metro = "NYC" | "EWR" | "TTN" | "CHI" | "MIA";

export interface Place {
  lat: number;
  lon: number;
  label: string;
  metro: Metro;
  how: "zip" | "zip-prefix" | "name";
  zip?: string;
}

type Row = [lat: number, lon: number, label: string, metro: Metro];

const ZIP: Record<string, Row> = {
  "10001": [40.7506, -73.9972, "Chelsea, Manhattan", "NYC"],
  "10002": [40.7157, -73.9863, "Lower East Side, Manhattan", "NYC"],
  "10003": [40.7317, -73.9892, "East Village, Manhattan", "NYC"],
  "10011": [40.7418, -74.0002, "Chelsea, Manhattan", "NYC"],
  "10019": [40.7651, -73.9858, "Midtown West, Manhattan", "NYC"],
  "10024": [40.7867, -73.9754, "Upper West Side, Manhattan", "NYC"],
  "10036": [40.7590, -73.9897, "Times Square, Manhattan", "NYC"],
  "11101": [40.7447, -73.9485, "Long Island City, Queens", "NYC"],
  "11201": [40.6955, -73.9899, "Brooklyn Heights", "NYC"],
  "11211": [40.7121, -73.9535, "Williamsburg, Brooklyn", "NYC"],
  "11215": [40.6681, -73.9806, "Park Slope, Brooklyn", "NYC"],
  "07030": [40.7453, -74.0279, "Hoboken", "EWR"],
  "07102": [40.7357, -74.1724, "Downtown Newark", "EWR"],
  "07302": [40.7206, -74.0434, "Downtown Jersey City", "EWR"],
  "08540": [40.3573, -74.6672, "Princeton", "TTN"],
  "08608": [40.2206, -74.7597, "Downtown Trenton", "TTN"],
  "60601": [41.8858, -87.6181, "The Loop, Chicago", "CHI"],
  "60614": [41.9227, -87.6533, "Lincoln Park, Chicago", "CHI"],
  "60622": [41.9024, -87.6800, "Wicker Park, Chicago", "CHI"],
  "60638": [41.7810, -87.7700, "Garfield Ridge, Chicago", "CHI"],
  "33125": [25.7826, -80.2340, "Little Havana, Miami", "MIA"],
  "33130": [25.7671, -80.2044, "Brickell, Miami", "MIA"],
  "33139": [25.7839, -80.1340, "South Beach, Miami Beach", "MIA"],
  "33166": [25.8240, -80.3000, "Doral / Miami Springs", "MIA"],
};

const ZIP3: Record<string, Row> = {
  "100": [40.7831, -73.9712, "Manhattan", "NYC"],
  "101": [40.7831, -73.9712, "Manhattan", "NYC"],
  "102": [40.7831, -73.9712, "Manhattan", "NYC"],
  "103": [40.5795, -74.1502, "Staten Island", "NYC"],
  "104": [40.8448, -73.8648, "The Bronx", "NYC"],
  "111": [40.7282, -73.7949, "Queens", "NYC"],
  "112": [40.6782, -73.9442, "Brooklyn", "NYC"],
  "113": [40.7282, -73.7949, "Queens", "NYC"],
  "114": [40.6900, -73.8100, "Queens", "NYC"],
  "116": [40.5900, -73.8000, "Queens (Rockaways)", "NYC"],
  "070": [40.7357, -74.1724, "Newark area", "EWR"],
  "071": [40.7357, -74.1724, "Newark", "EWR"],
  "073": [40.7178, -74.0431, "Jersey City", "EWR"],
  "085": [40.2171, -74.7429, "Trenton area", "TTN"],
  "086": [40.2171, -74.7429, "Trenton", "TTN"],
  "606": [41.8781, -87.6298, "Chicago", "CHI"],
  "607": [41.8781, -87.6298, "Chicago", "CHI"],
  "608": [41.8781, -87.6298, "Chicago", "CHI"],
  "330": [25.7617, -80.1918, "Miami area", "MIA"],
  "331": [25.7617, -80.1918, "Miami", "MIA"],
  "332": [25.7617, -80.1918, "Miami", "MIA"],
};

// Longest names first so "miami beach" wins over "miami".
const NAMES: [string, Row][] = (
  [
    ["staten island", [40.5795, -74.1502, "Staten Island", "NYC"]],
    ["miami beach", [25.7907, -80.1300, "Miami Beach", "MIA"]],
    ["jersey city", [40.7178, -74.0431, "Jersey City", "EWR"]],
    ["manhattan", [40.7831, -73.9712, "Manhattan", "NYC"]],
    ["new york", [40.7831, -73.9712, "Manhattan", "NYC"]],
    ["brooklyn", [40.6782, -73.9442, "Brooklyn", "NYC"]],
    ["princeton", [40.3573, -74.6672, "Princeton", "TTN"]],
    ["hoboken", [40.7453, -74.0279, "Hoboken", "EWR"]],
    ["trenton", [40.2171, -74.7429, "Trenton", "TTN"]],
    ["chicago", [41.8781, -87.6298, "Chicago", "CHI"]],
    ["newark", [40.7357, -74.1724, "Newark", "EWR"]],
    ["queens", [40.7282, -73.7949, "Queens", "NYC"]],
    ["bronx", [40.8448, -73.8648, "The Bronx", "NYC"]],
    ["miami", [25.7617, -80.1918, "Miami", "MIA"]],
    ["nyc", [40.7831, -73.9712, "Manhattan", "NYC"]],
  ] as [string, Row][]
).sort((a, b) => b[0].length - a[0].length);

const place = ([lat, lon, label, metro]: Row, how: Place["how"], zip?: string): Place => ({ lat, lon, label, metro, how, zip });

export function geocode(address: string): Place | null {
  const text = address.toLowerCase();
  const zips = text.match(/\b\d{5}\b/g) ?? [];
  for (const z of zips) if (ZIP[z]) return place(ZIP[z], "zip", z);
  for (const z of zips) if (ZIP3[z.slice(0, 3)]) return place(ZIP3[z.slice(0, 3)], "zip-prefix", z);
  for (const [name, row] of NAMES) if (new RegExp(`\\b${name}\\b`).test(text)) return place(row, "name", zips[0]);
  return null;
}

/** IANA zone for each metro, used as the CSV upload default. */
export const METRO_TZ: Record<Metro, string> = {
  NYC: "America/New_York",
  EWR: "America/New_York",
  TTN: "America/New_York",
  CHI: "America/Chicago",
  MIA: "America/New_York",
};

export function tzForLatLon(lat: number, lon: number): string {
  return lon < -84.5 && lat > 30 ? "America/Chicago" : "America/New_York";
}

/** NAICS codes a demo business can pick. Labels in plain words; the code is what the engine reads. */
export const NAICS: { code: string; label: string }[] = [
  { code: "722515", label: "Ice cream, coffee, juice or snack bar" },
  { code: "722513", label: "Counter-service restaurant" },
  { code: "722511", label: "Sit-down restaurant" },
  { code: "311811", label: "Bakery with a shop" },
  { code: "445298", label: "Specialty food store" },
  { code: "713940", label: "Gym or fitness studio" },
  { code: "713990", label: "Outdoor recreation (mini golf, go-karts, rentals)" },
  { code: "444240", label: "Garden center or nursery" },
  { code: "459110", label: "Sporting goods store" },
  { code: "812930", label: "Parking lot or garage" },
];
