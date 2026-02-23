# -*- coding: utf-8 -*-
"""
deterministic_sensors.py - Precise Data Fetchers for Ester

EXPLICIT BRIDGE (c=a+b):
  a = user request for precise data (price, version, weather)
  b = deterministic API call with structured response
  c = factual answer with source + timestamp (no hallucination)

HIDDEN BRIDGES:
  - Ashby: requisite variety via multiple sensor types (pypi/crypto/weather/search)
  - Cover&Thomas: channel capacity = structured JSON API >> noisy web snippets
  - Gray's Anatomy: separation of tissues - factual sensors vs conversational LLM

EARTH (engineering/anatomy):
  Like blood glucose meter vs "how do you feel?" - 
  one gives 5.4 mmol/L with timestamp, other gives "fine I guess".
  For life-critical decisions, you want the meter.

Author: Claude (for Owner/Ester project)
Date: 2026-01-15
"""

import json
import urllib.request
import urllib.error
import datetime
import re
import logging
from typing import Optional, Dict, Any, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_sensor_logger = logging.getLogger("ester.sensors")


class DeterministicSensors:
    """
    Precise data fetchers that return structured results with timestamps.
    Unlike web search snippets, these give exact values from authoritative APIs.
    """
    
    TIMEOUT = 10  # seconds
    
    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    @staticmethod
    def _safe_request(url: str, timeout: int = 10) -> Tuple[bool, str]:
        """Safe HTTP GET with error handling."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Ester/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"URL Error: {e.reason}"
        except Exception as e:
            return False, f"Error: {e}"
    
    @classmethod
    def get_pypi_version(cls, package: str) -> Dict[str, Any]:
        """
        Get latest version of a Python package from PyPI.
        Example: get_pypi_version("torch") -> {"ok": true, "version": "2.5.1", ...}
        """
        url = f"https://pypi.org/pypi/{package}/json"
        ok, data = cls._safe_request(url, cls.TIMEOUT)
        ts = cls._utc_now()
        
        if not ok:
            return {"ok": False, "error": data, "ts": ts, "source": "pypi.org"}
        
        try:
            j = json.loads(data)
            version = j.get("info", {}).get("version", "unknown")
            name = j.get("info", {}).get("name", package)
            return {
                "ok": True,
                "package": name,
                "version": version,
                "ts": ts,
                "source": f"https://pypi.org/project/{package}/"
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "pypi.org"}
    
    @classmethod
    def get_crypto_price(cls, coin: str = "bitcoin", currency: str = "usd") -> Dict[str, Any]:
        """
        Get current cryptocurrency price from CoinGecko (free, no API key).
        Example: get_crypto_price("bitcoin", "usd") -> {"ok": true, "price": 98500.00, ...}
        """
        coin_lower = coin.lower().strip()
        currency_lower = currency.lower().strip()
        
        # Map common names
        coin_map = {
            "btc": "bitcoin", "eth": "ethereum", "xrp": "ripple",
            "sol": "solana", "doge": "dogecoin", "ada": "cardano"
        }
        coin_id = coin_map.get(coin_lower, coin_lower)
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency_lower}"
        ok, data = cls._safe_request(url, cls.TIMEOUT)
        ts = cls._utc_now()
        
        if not ok:
            return {"ok": False, "error": data, "ts": ts, "source": "coingecko.com"}
        
        try:
            j = json.loads(data)
            if coin_id not in j:
                return {"ok": False, "error": f"Unknown coin: {coin}", "ts": ts, "source": "coingecko.com"}
            
            price = j[coin_id].get(currency_lower)
            if price is None:
                return {"ok": False, "error": f"No price for {currency}", "ts": ts, "source": "coingecko.com"}
            
            return {
                "ok": True,
                "coin": coin_id,
                "currency": currency_lower.upper(),
                "price": float(price),
                "ts": ts,
                "source": "https://www.coingecko.com/"
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "coingecko.com"}
    
    @classmethod  
    def get_gold_price(cls, currency: str = "usd") -> Dict[str, Any]:
        """
        Get gold price (XAU) - uses Tether Gold (XAUT) as proxy.
        """
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether-gold&vs_currencies=usd,eur"
        ok, data = cls._safe_request(url, cls.TIMEOUT)
        ts = cls._utc_now()
        
        if not ok:
            return {"ok": False, "error": data, "ts": ts, "source": "coingecko.com (XAUT proxy)"}
        
        try:
            j = json.loads(data)
            tg = j.get("tether-gold", {})
            price = tg.get(currency.lower())
            if price is None:
                return {"ok": False, "error": f"No gold price for {currency}", "ts": ts, "source": "coingecko.com"}
            
            return {
                "ok": True,
                "asset": "XAU (Gold, via XAUT proxy)",
                "currency": currency.upper(),
                "price_per_oz": float(price),
                "ts": ts,
                "source": "https://www.coingecko.com/en/coins/tether-gold",
                "note": "Approximation via Tether Gold token"
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "coingecko.com"}
    
    @classmethod
    def get_weather(cls, city: str = "DefaultCity", country: str = "BE") -> Dict[str, Any]:
        """
        Get current weather from Open-Meteo (free, no API key).
        """
        # First geocode the city
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
        ok, data = cls._safe_request(geo_url, cls.TIMEOUT)
        ts = cls._utc_now()
        
        if not ok:
            return {"ok": False, "error": f"Geocoding failed: {data}", "ts": ts, "source": "open-meteo.com"}
        
        try:
            geo = json.loads(data)
            results = geo.get("results", [])
            if not results:
                return {"ok": False, "error": f"City not found: {city}", "ts": ts, "source": "open-meteo.com"}
            
            loc = results[0]
            lat, lon = loc["latitude"], loc["longitude"]
            city_name = loc.get("name", city)
            country_name = loc.get("country", country)
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "open-meteo.com"}
        
        # Now get weather
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )
        ok, data = cls._safe_request(weather_url, cls.TIMEOUT)
        
        if not ok:
            return {"ok": False, "error": f"Weather fetch failed: {data}", "ts": ts, "source": "open-meteo.com"}
        
        try:
            w = json.loads(data)
            cw = w.get("current_weather", {})
            
            # Decode weather code
            wmo_codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                95: "Thunderstorm", 96: "Thunderstorm with hail"
            }
            weather_code = cw.get("weathercode", 0)
            
            return {
                "ok": True,
                "city": city_name,
                "country": country_name,
                "temp_c": cw.get("temperature"),
                "wind_kmh": cw.get("windspeed"),
                "wind_dir": cw.get("winddirection"),
                "condition": wmo_codes.get(weather_code, f"Code {weather_code}"),
                "ts": ts,
                "source": "https://open-meteo.com/"
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "open-meteo.com"}

    @classmethod
    def get_football_standings(cls, league: str = "PL") -> Dict[str, Any]:
        """
        Get football league standings.
        League codes: PL (Premier League), BL1 (Bundesliga), SA (Serie A), PD (La Liga), FL1 (Ligue 1)
        Uses football-data.org (free tier, no API key for basic data).
        """
        league_map = {
            "pl": "PL", "premier": "PL", "epl": "PL", "england": "PL",
            "bl1": "BL1", "bundesliga": "BL1", "germany": "BL1",
            "sa": "SA", "serie a": "SA", "italy": "SA",
            "pd": "PD", "la liga": "PD", "spain": "PD",
            "fl1": "FL1", "ligue 1": "FL1", "france": "FL1"
        }
        
        league_code = league_map.get(league.lower().strip(), league.upper())
        url = f"https://api.football-data.org/v4/competitions/{league_code}/standings"
        
        ts = cls._utc_now()
        
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Ester/1.0",
                "X-Auth-Token": ""  # Free tier works without token for basic data
            })
            with urllib.request.urlopen(req, timeout=cls.TIMEOUT) as resp:
                data = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # Try alternative: free API
            return {"ok": False, "error": f"HTTP {e.code}: Rate limited or unavailable", "ts": ts, "source": "football-data.org"}
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "football-data.org"}
        
        try:
            j = json.loads(data)
            standings = j.get("standings", [])
            if not standings:
                return {"ok": False, "error": "No standings data", "ts": ts, "source": "football-data.org"}
            
            total = standings[0].get("table", [])
            if not total:
                return {"ok": False, "error": "Empty table", "ts": ts, "source": "football-data.org"}
            
            top5 = []
            for row in total[:5]:
                team = row.get("team", {}).get("name", "Unknown")
                pos = row.get("position", 0)
                pts = row.get("points", 0)
                played = row.get("playedGames", 0)
                top5.append({"position": pos, "team": team, "points": pts, "played": played})
            
            leader = top5[0] if top5 else None
            
            return {
                "ok": True,
                "league": j.get("competition", {}).get("name", league_code),
                "season": j.get("season", {}).get("startDate", "unknown")[:4],
                "leader": leader["team"] if leader else "Unknown",
                "leader_points": leader["points"] if leader else 0,
                "top5": top5,
                "ts": ts,
                "source": "https://www.football-data.org/"
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "ts": ts, "source": "football-data.org"}

    @classmethod
    def format_sensor_result(cls, result: Dict[str, Any]) -> str:
        """Format sensor result for LLM consumption."""
        if not result.get("ok"):
            return f"[SENSOR_ERROR] {result.get('error', 'Unknown error')} @ {result.get('ts', 'unknown')} (source: {result.get('source', 'unknown')})"
        
        # Remove internal fields
        display = {k: v for k, v in result.items() if k not in ("ok",)}
        
        lines = ["[SENSOR_DATA]"]
        for k, v in display.items():
            if isinstance(v, list):
                lines.append(f"  {k}:")
                for item in v:
                    if isinstance(item, dict):
                        lines.append(f"    - {item}")
                    else:
                        lines.append(f"    - {item}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    
    @classmethod
    def route_query(cls, query: str) -> Optional[Dict[str, Any]]:
        """
        Auto-route query to appropriate sensor based on keywords.
        Returns None if no sensor matches (fallback to web search).
        """
        q = query.lower().strip()
        
        # PyPI / Python packages
        pypi_keywords = ["pytorch", "torch", "tensorflow", "numpy", "pandas", "transformers", "version"]
        if any(pkg in q for pkg in ["pytorch", "torch"]) and any(kw in q for kw in ["version", "latest", "stable", "current", "release"]):
            return cls.get_pypi_version("torch")
        if "tensorflow" in q and any(kw in q for kw in ["version", "latest", "stable", "current"]):
            return cls.get_pypi_version("tensorflow")
        if "numpy" in q and any(kw in q for kw in ["version", "latest", "stable", "current"]):
            return cls.get_pypi_version("numpy")
        if "pandas" in q and any(kw in q for kw in ["version", "latest", "stable", "current"]):
            return cls.get_pypi_version("pandas")
        
        # Cryptocurrency
        crypto_keywords = ["price", "cost", "rate", "kurs", "stoit", "skolko"]
        if any(k in q for k in crypto_keywords):
            if "bitcoin" in q or "btc" in q or "bitkoin" in q:
                return cls.get_crypto_price("bitcoin")
            if "ethereum" in q or "eth" in q or "efir" in q:
                return cls.get_crypto_price("ethereum")
            if "solana" in q or "sol" in q:
                return cls.get_crypto_price("solana")
        
        # Gold
        if any(x in q for x in ["gold", "xau", "zolot", "untsi"]):
            if any(k in q for k in ["price", "cost", "rate", "kurs", "stoit", "skolko"]):
                return cls.get_gold_price()
        
        # Weather
        weather_keywords = ["weather", "pogoda", "temperature", "temperatura"]
        if any(k in q for k in weather_keywords):
            # Try to extract city
            cities = ["brussels", "bryussel", "moscow", "moskva", "london", "london", 
                     "paris", "parizh", "berlin", "berlin", "kiev", "kiev", "kyiv"]
            for city in cities:
                if city in q:
                    # Map to English name
                    city_map = {
                        "bryussel": "DefaultCity", "moskva": "Moscow", "london": "London",
                        "parizh": "Paris", "berlin": "Berlin", "kiev": "Kyiv"
                    }
                    return cls.get_weather(city_map.get(city, city.title()))
            
            # Default to DefaultCity if no city found
            return cls.get_weather("DefaultCity")
        
        # Football / EPL
        football_keywords = ["epl", "premier league", "standings", "table", "turnirnaya", "premer-liga", "pervoe mesto"]
        if any(k in q for k in football_keywords):
            return cls.get_football_standings("PL")
        
        return None  # No sensor match, fallback to web search


# Global instance
deterministic_sensors = DeterministicSensors()


# === Quick test ===
if __name__ == "__main__":
    import sys
    
    print("=== Deterministic Sensors Test ===\n")
    
    tests = [
        ("PyPI: torch", lambda: deterministic_sensors.get_pypi_version("torch")),
        ("Crypto: BTC", lambda: deterministic_sensors.get_crypto_price("bitcoin")),
        ("Gold: XAU", lambda: deterministic_sensors.get_gold_price()),
        ("Weather: DefaultCity", lambda: deterministic_sensors.get_weather("DefaultCity")),
        ("Football: EPL", lambda: deterministic_sensors.get_football_standings("PL")),
    ]
    
    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            result = fn()
            if result.get("ok"):
                print(f"  OK: {json.dumps(result, indent=2, ensure_ascii=False)}")
            else:
                print(f"  FAIL: {result.get('error')}")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n\n=== Query Routing Test ===\n")
    
    test_queries = [
        "latest stable PyTorch version",
        "What is the current Bitcoin price?",
        "Skolko stoit troyskaya untsiya zolota XAU/USD?",
        "Kakaya pogoda v Bryussele?",
        "Who is first in EPL standings?",
    ]
    
    for q in test_queries:
        print(f"\nQuery: {q}")
        result = deterministic_sensors.route_query(q)
        if result:
            print(f"  Routed to sensor: {deterministic_sensors.format_sensor_result(result)[:200]}...")
        else:
            print("  -> No sensor match, would fallback to web search")