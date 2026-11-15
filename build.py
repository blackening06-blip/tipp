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


NEUTRAL = {"FC Bayern Munich Stadium": (48.219, 11.625)}   # Auslandsspiele unter freiem Himmel
_WX = {}


def weather(team, kick_utc, coords=None):
    """Max. Wind (km/h) und Regen (mm) über 3 Stunden ab Kick-off, None wenn unbekannt."""
    if (team, kick_utc) in _WX:
        return _WX[(team, kick_utc)]
    if not coords and team not in STADIUM:
        print(f"  Wetter {team}: kein Freiluftstadion hinterlegt")
        return None
    lat, lon = coords or STADIUM[team]
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&hourly=wind_speed_10m,precipitation,temperature_2m,weather_code,is_day&wind_speed_unit=kmh&timezone=UTC&past_days=1&forecast_days=10")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tipp-das/1.0"})
        h = json.load(urllib.request.urlopen(req, timeout=20))["hourly"]
        keys = [(kick_utc.replace(minute=0) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(4)]
        idx = [h["time"].index(k) for k in keys if k in h["time"]]
        wind = [h["wind_speed_10m"][i] for i in idx if h["wind_speed_10m"][i] is not None]
        rain = [h["precipitation"][i] for i in idx if h["precipitation"][i] is not None]
        temp = [h["temperature_2m"][i] for i in idx if h["temperature_2m"][i] is not None]
        if not wind:
            print(f"  Wetter {team}: keine Werte für {keys[0]}")
            return None
        print(f"  Wetter {team}: Wind {max(wind):.0f} km/h, Regen {sum(rain):.1f} mm")
        code = max((h["weather_code"][i] for i in idx if h["weather_code"][i] is not None), default=None)  # schlechtestes Wetter im Spiel
        _WX[(team, kick_utc)] = (max(wind), sum(rain), sum(temp) / len(temp) if temp else None, code, h["is_day"][idx[0]])
        return _WX[(team, kick_utc)]
    except Exception as e:
        print(f"  Wetter {team}: Fehler {e}")
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

# Depth Chart (neuester Stand je Team) für Ersatzspieler
DC = nfl.load_depth_charts([SEASON]).to_pandas()
DC = DC[(DC.dt == DC.groupby("team").dt.transform("max")) & DC.pos_abb.isin(["QB", "RB", "WR", "TE"])]
DEPTH = {k: g.sort_values("pos_rank").drop_duplicates("gsis_id")[["gsis_id", "player_name"]].values.tolist()
         for k, g in DC.groupby(["team", "pos_abb"])}
STARTERS = {"QB": 1, "RB": 1, "WR": 3, "TE": 1}   # so viele spielen regulär
TOPN = {"QB": 1, "RB": 1, "WR": 2, "TE": 1}       # so viele zählen als Top-Spieler
CUR = P[P.season == SEASON]


def outs(team):
    """Wichtige Ausfälle (Out, Doubtful, Questionable) eines Teams mit Ersatz laut Depth Chart."""
    res = []
    hurt = lambda pid: status.get(pid) in ("Out", "Doubtful")
    for _, i in INJ[(INJ.team == team) & INJ.report_status.isin(["Out", "Doubtful", "Questionable"]) & INJ.position.isin(list(STARTERS))].iterrows():
        pos, dep = i.position, DEPTH.get((team, i.position), [])
        ids = [d[0] for d in dep]
        rank = ids.index(i.gsis_id) if i.gsis_id in ids else None
        best = CUR[(CUR.team == team) & (CUR.position == pos)].groupby("player_id").fantasy_points_ppr.sum().nlargest(TOPN[pos]).index
        if pos == "QB" and rank != 0:   # QB zählt nur, wenn er aktuell Starter ist (z. B. nach Trade nicht mehr)
            continue
        if not ((rank is not None and rank < TOPN[pos]) or i.gsis_id in best):
            continue
        start = max(STARTERS[pos], rank + 1) if rank is not None else (0 if pos == "QB" else STARTERS[pos])
        sub = next((n for k, (pid, n) in enumerate(dep) if k >= start and pid != i.gsis_id and not hurt(pid)), None)
        st = {"Out": "fällt aus", "Doubtful": "wohl raus (Doubtful)"}.get(i.report_status, "fraglich (Questionable)")
        res.append(dict(team=team, name=i.full_name, pos=pos, st=st, sub=sub, pid=i.gsis_id, out=i.report_status != "Questionable"))
    return res


TEAMS = sorted(set(S.home_team))
OUTS = {t: outs(t) for t in TEAMS}
LAST = CUR.groupby("team").apply(lambda g: g.week.max()).to_dict()   # letzte gespielte Woche je Team

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
    # Rot nur, wenn der eingeplante Starter ausfällt. Länger Verletzte sind in der Linie schon drin.
    qbs = [o for o in OUTS[r.home_team] + OUTS[r.away_team] if o["pos"] == "QB" and o["out"] and o["name"] in (r.home_qb_name, r.away_qb_name)]
    qb = bool(qbs) or bool({r.home_qb_name, r.away_qb_name} & qb_out)
    qb_note = " · ".join(f"Achtung: QB {o['name']} ({o['team']}) {o['st']}" + (f", es spielt {o['sub']}" if o["sub"] else "") for o in qbs) or ("Achtung: Starting-QB fällt aus" if qb else "")
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
    pl = {}   # pid -> [lam, name, team, pos, info]
    for pid, h in P[P.player_id.isin([k for k, v in team_now.items() if v in pts])].groupby("player_id"):
        h = h.tail(8)
        if len(h) >= 3:
            lam = (h.td.sum() + 1.2) / (len(h) + 6) * pts[team_now[pid]] / 22.5
            new = h.season.iloc[-1] == SEASON and h.week.iloc[-1] >= LAST.get(team_now[pid], 0)  # hat zuletzt noch gespielt
            pl[pid] = [lam, h.player_display_name.iloc[-1], team_now[pid], h.position.iloc[-1], "", new]
    # Neuer Ausfall: TD-Anteil geht zur Hälfte an den Ersatz, der Rest anteilig an die Kollegen auf der Position
    for o in [o for t in pts for o in OUTS[t] if o["out"] and o["pos"] != "QB"]:
        if o["pid"] not in pl or not pl[o["pid"]][5]:
            continue
        lam = pl[o["pid"]][0]
        mates = [q for q, v in pl.items() if v[2] == o["team"] and v[3] == o["pos"] and status.get(q) not in ("Out", "Doubtful")]
        subs = [q for q in mates if pl[q][1] == o["sub"]]
        tot = sum(pl[q][0] for q in mates) or 1
        for q in mates:
            pl[q][0] += lam * (0.5 if q in subs else 0) + lam * (0.5 if subs else 1) * pl[q][0] / tot
            pl[q][4] = f"mehr Einsätze, {o['name']} {o['st']}"
    cand = []
    for pid, (lam, nm, tm, pos, info, _) in pl.items():
        if status.get(pid) in ("Out", "Doubtful"):
            continue
        q = " (Q)" if status.get(pid) == "Questionable" else ""
        cand.append((1 - math.exp(-lam), f"TD {nm} ({tm}){q}", {"k": "td", "tm": tm, "lam": round(lam, 4)}, info))
    legs += [(f"TD{i}", lab, p, False, d, info) for i, (p, lab, d, info) in enumerate(sorted(cand, key=lambda c: -c[0])[:4])]
    s = slots.setdefault(sl, {"name": sl, "kick": kick.astimezone(DE).strftime("%H:%M"), "legs": []})
    for kind, label, p, over, d, *info in legs:
        warn = [w for w in [qb_note, wx_note if over else ""] if w]
        s["legs"].append(dict(id=f"{r.game_id}:{kind}", game=r.game_id, match=match, label=label, p=round(p, 3), d=d, gm=gm, info=info[0] if info else "",
                              warn=" · ".join(warn), rec=p >= MIN_P and not qb and not (over and (bad_wx or (outdoor and not wx)))))
for s in slots.values():
    s["legs"].sort(key=lambda l: (-l["p"], bool(l["warn"])))
def qb_now(team, name):
    """Eingeplanter QB, bei Ausfall sein Ersatz laut Depth Chart."""
    o = next((o for o in OUTS[team] if o["pos"] == "QB" and o["out"] and o["name"] == name), None)
    return f"{o['sub']} (für {name})" if o and o["sub"] else (name or "")


import re
T = nfl.load_teams().to_pandas()
TV_URLS = ["https://ran.joyn.de/sports/american-football/nfl/nfl-live-diese-{m}-werden-in-woche{w}-kostenlos-gezeigt-uebertragungen-im-free-tv-{s}-173951"
           .format(m=m, w=week, s=s) for m in ("matches", "spiele") for s in ("stream-ticker", "livestream-und-ticker", "stream-und-ticker")]


def tv():
    """TV-Sender je Spiel: erst tv.json (von Hand), sonst die Wochenübersicht von ran.de."""
    try:
        manual = json.load(open("tv.json", encoding="utf-8")).get(f"{SEASON}-{week}")
        if manual:
            print("  TV: aus tv.json"); return manual
    except Exception:
        pass
    names = {n: a for a, n in zip(T.team_abbr, T.team_name)}
    for url in TV_URLS:
        try:
            html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        res = {}
        for away, home, ch in re.findall(r"Uhr: ([A-Z][\w .]+?) at ([A-Z][\w .]+?)(?: aus \w+)? \(([^)]*)\)", text):
            a, h = names.get(away.strip()), names.get(home.strip())
            if a and h:
                res[f"{a}@{h}"] = "RTL" if "Free-TV/RTL" in ch else "RTL+" if "RTL+" in ch else "Sky" if "Sky" in ch else ""
        if res:
            print(f"  TV: {len(res)} Spiele von ran.de"); return res
    print("  TV: keine Daten gefunden"); return {}


TV = tv()
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
games = []
for _, r in S[S.week == week].iterrows():
    k = datetime.fromisoformat(f"{r.gameday} {r.gametime}").replace(tzinfo=ET).astimezone(DE)
    if r.location == "Neutral" and r.stadium in NEUTRAL:
        w = weather(r.home_team, k.astimezone(UTC), NEUTRAL[r.stadium]); roof = "outdoors"
    else:
        roof = r.roof if r.roof == r.roof else "dach"
        w = weather(r.home_team, k.astimezone(UTC)) if roof in ("outdoors", "open") else None
    wx = ({"roof": "Halle"} if roof in ("dome", "closed") else {"roof": "Dach"} if roof == "dach"
          else {"w": round(w[0]), "r": round(w[1], 1), "t": None if w[2] is None else round(w[2]), "c": w[3], "d": w[4]} if w else {"roof": "?"})
    games.append(dict(t=k.isoformat(), wx=wx, tv=TV.get(f"{r.away_team}@{r.home_team}", ""), day=f"{DAYS[k.weekday()]} {k:%d.%m.}", kick=f"{k:%H:%M}", away=r.away_team, home=r.home_team,
                      score=None if r.result != r.result else f"{int(r.away_score)}:{int(r.home_score)}",
                      qbs=[qb_now(r.away_team, r.away_qb_name), qb_now(r.home_team, r.home_qb_name)],
                      outs=OUTS[r.away_team] + OUTS[r.home_team]))
games.sort(key=lambda g: g["t"])
colors = {a: [c1, c2, nk] for a, c1, c2, nk in zip(T.team_abbr, T.team_color, T.team_color2, T.team_nick)}
DIV = dict(zip(T.team_abbr, T.team_division))
teams = [dict(t=t, div=DIV.get(t, ""), bye=t not in set(S[S.week == week].home_team) | set(S[S.week == week].away_team),
              outs=[{k: v for k, v in o.items() if k != "pid"} for o in OUTS[t]]) for t in TEAMS]
for g in games:
    g["outs"] = [{k: v for k, v in o.items() if k != "pid"} for o in g["outs"]]
out = {"teams": teams, "games": games, "colors": colors, "week": week, "updated": TODAY.strftime("%d.%m. %H:%M"), "slots": [slots[k] for k in ("Früh", "Spät") if k in slots]}
json.dump(out, open("data.json", "w"), ensure_ascii=False)
print(f"Week {week}: {sum(len(s['legs']) for s in out['slots'])} Legs geschrieben")
