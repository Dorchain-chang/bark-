"""Inspect the worldcup26.ir API data - output to file"""
import json

with open('D:/区块链作业/worldcup-push/wc_api_dump.json', encoding='utf-8') as f:
    data = json.load(f)

games = data.get('games', [])
lines = []

lines.append(f'Total games: {len(games)}')

# All keys
all_keys = set()
for g in games:
    all_keys.update(g.keys())
lines.append(f'All keys: {sorted(all_keys)}')

# First 3 games in detail (only English fields)
for i, g in enumerate(games[:3]):
    lines.append(f'\n--- Game {i+1} (id={g.get("id")}) ---')
    for k in sorted(g.keys()):
        if k.endswith('_fa'):
            continue
        v = g[k]
        s = repr(v)
        if len(s) > 200:
            s = s[:200] + '...'
        lines.append(f'  {k}: {s}')

# Stadium IDs
stadiums = set(g.get('stadium_id') for g in games)
lines.append(f'\nStadium IDs: {sorted(stadiums)}')

# Look at finished games for scorer data
finished = [g for g in games if g.get('time_elapsed') == 'finished']
if finished:
    g = finished[0]
    lines.append(f'\n--- Finished game example ---')
    lines.append(f'  home_scorers: {repr(g.get("home_scorers"))}')
    lines.append(f'  away_scorers: {repr(g.get("away_scorers"))}')
    lines.append(f'  local_date: {repr(g.get("local_date"))}')
    lines.append(f'  teams: {g.get("home_team_name_en")} vs {g.get("away_team_name_en")}')
    lines.append(f'  score: {g.get("home_score")} - {g.get("away_score")}')

# Show all scorer examples
lines.append(f'\n--- All scorer data samples ---')
for g in games:
    hs = g.get('home_scorers', 'null')
    as_ = g.get('away_scorers', 'null')
    if hs != 'null' or as_ != 'null':
        lines.append(f'  {g.get("home_team_name_en")} vs {g.get("away_team_name_en")}:')
        lines.append(f'    home: {hs}')
        lines.append(f'    away: {as_}')

# Upcoming games with dates
lines.append(f'\n--- Upcoming games (first 20) ---')
upcoming = [g for g in games if g.get('time_elapsed') != 'finished']
for g in upcoming[:20]:
    lines.append(f'  {g.get("local_date"):20s} {g.get("home_team_name_en"):15s} vs {g.get("away_team_name_en"):15s} [{g.get("time_elapsed")}] ')

with open('D:/区块链作业/worldcup-push/data_inspect.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('OK')
