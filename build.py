"""Berechnet data.json für die Tipp-das-Seite. Läuft in der GitHub Action."""
import json, math, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import nflreadpy as nfl

ET, DE, UTC = ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin"), ZoneInfo("UTC")
TODAY = datetime.now(DE)
SEASON = TODAY.year if TODAY.month >= 8 else TODAY.year - 1
MIN_P, ALT = 0.70, 7.0               # Empfehlung ab 70 %, Alt-Linien 7 Punkte vorsichtiger
WIND_MAX, RAIN_MAX = 16, 1.0         # km/h, mm in den 3 Spielstunden
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
dec = lambda ml: 1 + (ml / 100 if ml > 0 else 100 / -ml)
# Freiluftstadien (Heimteam -> Koordinaten)
STADIUM = {"BUF": (42.774, -78.787), "NYJ": (40.814, -74.074), "NYG": (40.814, -74.074), "NE": (42.091, -71.264),
           "MIA": (25.958, -80.239), "PHI": (39.901, -75.168), "WAS": (38.908, -76.865), "BAL": (39.278, -76.623),
           "PIT": (40.447, -80.016), "CLE": (41.506, -81.700), "CIN": (39.096, -84.516), "JAX": (30.324, -81.637),
           "TEN": (36.167, -86.771), "KC": (39.049, -94.484), "DEN": (39.744, -105.020), "GB": (44.501, -88.062),
           "CHI": (41.862, -87.617), "SEA": (47.595, -122.332), "SF": (37.403, -121.970), "CAR": (35.226, -80.853),
           "TB": (27.976, -82.503)}


def slot(et_hour):
    return "Früh" if et_hour == 13 else "Spät" if et_hour == 16 else None


def weather(team, kick_utc):
    """Max. Wind (km/h) und Regen (mm) über 3 Stunden ab Kick-off, None wenn unbekannt."""
    if team not in STADIUM:
        return None
    lat, lon = STADIUM[team]
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&hourly=wind_speed_10m,precipitation&timezone=UTC&forecast_days=10")
    try:
        h = json.load(urllib.request.urlopen(url, timeout=20))["hourly"]
        hours = [kick_utc.replace(minute=0) + timedelta(hours=i) for i in range(4)]
        idx = [h["time"].index(t.strftime("%Y-%m-%dT%H:00")) for t in hours if t.strftime("%Y-%m-%dT%H:00") in h["time"]]
        if not idx:
            return None
        return max(h["wind_speed_10m"][i] for i in idx), sum(h["precipitation"][i] for i in idx)
    except Exception:
        return None


S = nfl.load_schedules([SEASON]).to_pandas()
week = int(S[S.result.isna() & (S.game_type == "REG")].week.min())
INJ = nfl.load_injuries([SEASON]).to_pandas().query("week == @week")
status = dict(zip(INJ.gsis_id, INJ.report_status))
qb_out = set(INJ[(INJ.position == "QB") & INJ.report_status.isin(["Out", "Doubtful"])].full_name)
ROS = nfl.load_rosters_weekly([SEASON]).to_pandas()
ROS = ROS[(ROS.week == ROS.week.max()) & (ROS.status == "ACT")]
team_now = dict(zip(ROS.gsis_id, ROS.team))
P = nfl.load_player_stats([SEASON - 1, SEASON]).to_pandas()
P = P[(P.season_type == "REG") & P.position.isin(["QB", "RB", "WR", "TE"])].copy()
P["td"] = P.rushing_tds.fillna(0) + P.receiving_tds.fillna(0)
P = P.sort_values(["season", "week"])

slots = {}
for _, r in S[(S.week == week) & S.result.isna() & (S.weekday == "Sunday")].iterrows():
    sl = slot(int(r.gametime[:2]))
    if not sl:
        continue
    kick = datetime.fromisoformat(f"{r.gameday} {r.gametime}").replace(tzinfo=ET)
    match = f"{r.away_team} @ {r.home_team}"
    ph = (1 / dec(r.home_moneyline)) / (1 / dec(r.home_moneyline) + 1 / dec(r.away_moneyline))
    fav, dog, pf = (r.home_team, r.away_team, ph) if ph >= .5 else (r.away_team, r.home_team, 1 - ph)
    fs = abs(r.spread_line)
    qb = bool({r.home_qb_name, r.away_qb_name} & qb_out)
    outdoor = r.roof in ("outdoors", "open")
    wx = weather(r.home_team, kick.astimezone(UTC)) if outdoor else None
    bad_wx = bool(wx and (wx[0] >= WIND_MAX or wx[1] >= RAIN_MAX))
    # Warnung nur bei schlechtem oder unbekanntem Wetter, gutes Wetter bleibt ohne Hinweis
    wx_note = ("" if not outdoor else "Achtung Freiluft: Wetter unbekannt" if not wx
               else f"Achtung Freiluft: Wind {wx[0]:.0f} km/h, Regen {wx[1]:.1f} mm" if bad_wx else "")
    pts = {r.home_team: r.total_line / 2 + r.spread_line / 2, r.away_team: r.total_line / 2 - r.spread_line / 2}
    dl = math.floor(fs + ALT) + 0.5
    ol = math.ceil(r.total_line - ALT) - 0.5
    tl = math.floor(pts[fav] - 6) + 0.5
    pen = 0.02 if outdoor else 0     # Freiluft trifft bei Über-Legs etwas seltener
    # d = Definition für die gemeinsame Rechnung mehrerer Legs aus einem Spiel
    legs = [("Sieg", f"Sieg {fav}", pf, False, {"k": "win", "tm": fav}),
            ("SiegD", f"Sieg {dog}", 1 - pf, False, {"k": "win", "tm": dog}),
            ("HC", f"{dog} +{dl:g} Handicap", Phi((dl - fs) / 12.6), False, {"k": "hc", "tm": dog, "ln": dl}),
            ("OU", f"Über {ol:g} Punkte", Phi((r.total_line - ol) / 13) - pen, True, {"k": "ou", "ln": ol}),
            ("TT", f"{fav} über {tl:g} Punkte", Phi((pts[fav] - tl) / 9.1) - pen, True, {"k": "tt", "tm": fav, "ln": tl})]
    gm = {"h": r.home_team, "a": r.away_team, "m": float(r.spread_line), "t": float(r.total_line)}
    cand = []
    for pid, h in P[P.player_id.isin([k for k, v in team_now.items() if v in pts])].groupby("player_id"):
        if status.get(pid) in ("Out", "Doubtful"):
            continue
        h = h.tail(8)
        if len(h) >= 3:
            lam = (h.td.sum() + 1.2) / (len(h) + 6) * pts[team_now[pid]] / 22.5
            q = " (Q)" if status.get(pid) == "Questionable" else ""
            cand.append((1 - math.exp(-lam), f"TD {h.player_display_name.iloc[-1]} ({team_now[pid]}){q}", {"k": "td", "tm": team_now[pid], "lam": round(lam, 4)}))
    legs += [(f"TD{i}", lab, p, False, d) for i, (p, lab, d) in enumerate(sorted(cand, key=lambda c: -c[0])[:4])]
    s = slots.setdefault(sl, {"name": sl, "kick": kick.astimezone(DE).strftime("%H:%M"), "legs": []})
    for kind, label, p, over, d in legs:
        warn = [w for w in ["Achtung: QB fällt aus, Linie prüfen" if qb else "", wx_note if over else ""] if w]
        s["legs"].append(dict(id=f"{r.game_id}:{kind}", game=r.game_id, match=match, label=label, p=round(p, 3), d=d, gm=gm,
                              warn=" · ".join(warn), rec=p >= MIN_P and not qb and not (over and (bad_wx or (outdoor and not wx)))))
for s in slots.values():
    s["legs"].sort(key=lambda l: (-l["p"], bool(l["warn"])))
out = {"week": week, "updated": TODAY.strftime("%d.%m. %H:%M"), "slots": [slots[k] for k in ("Früh", "Spät") if k in slots]}
json.dump(out, open("data.json", "w"), ensure_ascii=False)
print(f"Week {week}: {sum(len(s['legs']) for s in out['slots'])} Legs geschrieben")
