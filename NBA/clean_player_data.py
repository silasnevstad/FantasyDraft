import pandas as pd

# Step 1: Load and Clean Player Data
columns = ['Rank', 'Player', 'Status Type', 'Status Action', 'MIN', 'FGM', 'FGA', 'FTM', 'FTA',
           '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS', 'Research %ROST',
           'Research +/-', 'Fantasy TOT', 'Fantasy AVG']

# Read the CSV file
data = pd.read_csv('players_data.csv', header=None, names=columns)

# Drop the first row if necessary
data = data.drop(0).reset_index(drop=True)

# Drop Status Type and Status Action columns
data = data.drop(columns=['Status Type', 'Status Action'])

# Parse 'Player' column to extract Name, Team, Position
def parse_player_info(s):
    parts = s.split('\n')
    status_indicators = {'DTD', 'O', 'SUSP', 'NA', 'IR', 'GTD', 'OUT', 'Questionable', 'Probable'}
    parts = [p for p in parts if p not in status_indicators]
    parts = [p for p in parts if p.strip()]  # Remove empty strings
    if len(parts) >= 3:
        name = parts[0]
        team = parts[1]
        position = ' '.join(parts[2:])
    elif len(parts) == 2:
        name, team = parts
        position = ''
    elif len(parts) == 1:
        name = parts[0]
        team = ''
        position = ''
    else:
        name = ''
        team = ''
        position = ''
    return pd.Series({'Player': name, 'Team': team, 'Position': position})

# Apply the function to parse 'Player' column
player_info = data['Player'].apply(parse_player_info)

# Drop the original 'Player' column and concatenate new columns
data = data.drop(columns=['Player'])
data = pd.concat([data, player_info], axis=1)

# Reorder columns
columns_order = ['Rank', 'Player', 'Team', 'Position', 'MIN', 'FGM',
                 'FGA', 'FTM', 'FTA', '3PM', 'REB', 'AST', 'STL', 'BLK',
                 'TO', 'PTS', 'Research %ROST', 'Research +/-', 'Fantasy TOT', 'Fantasy AVG']
data = data[columns_order]

# Fill missing values if necessary
data[['Team', 'Position']] = data[['Team', 'Position']].fillna('')

# Parse positions into a list
def parse_positions(pos_str):
    positions = pos_str.split(', ')
    return positions

data['Position List'] = data['Position'].apply(parse_positions)

# Convert columns to numeric, converting '--' to NaN
numeric_columns = ['MIN', 'FGM', 'FGA', 'FTM', 'FTA', '3PM', 'REB', 'AST',
                   'STL', 'BLK', 'TO', 'PTS', 'Fantasy TOT', 'Fantasy AVG']
data[numeric_columns] = data[numeric_columns].apply(pd.to_numeric, errors='coerce')

# Define your league's scoring settings
scoring_settings = {
    'FGM': 2,
    'FGA': -1,
    'FTM': 1,
    'FTA': -1,
    '3PM': 1,
    'REB': 1,
    'AST': 2,
    'STL': 4,
    'BLK': 4,
    'TO': -2,
    'PTS': 1
}

# Calculate Projected Fantasy Points
def calculate_projected_fantasy_points(row):
    total_points = 0
    for stat, value in scoring_settings.items():
        if stat in row and not pd.isnull(row[stat]):
            total_points += row[stat] * value
    return total_points

data['Projected Fantasy Points'] = data.apply(calculate_projected_fantasy_points, axis=1)

# Remove players with NaN or zero 'Projected Fantasy Points'
data = data.dropna(subset=['Projected Fantasy Points'])
data = data[data['Projected Fantasy Points'] > 0]

# Define positions and roster slots
positions = ['PG', 'SG', 'SF', 'PF', 'C']
roster_slots = {
    'PG': 1,
    'SG': 1,
    'SF': 1,
    'PF': 1,
    'C': 1,
    'G': 1,
    'F': 1,
    'UTIL': 3,
    'Bench': 3
}
num_teams = 12

# Calculate position demand across all teams
position_demand = {}
for pos in positions:
    specific_slots = roster_slots.get(pos, 0)
    flex_slots = 0
    if pos in ['PG', 'SG'] and 'G' in roster_slots:
        flex_slots += roster_slots['G']
    if pos in ['SF', 'PF'] and 'F' in roster_slots:
        flex_slots += roster_slots['F']
    if 'UTIL' in roster_slots:
        flex_slots += roster_slots['UTIL']
    bench_slots = roster_slots['Bench'] / len(positions)
    total_slots = (specific_slots + flex_slots + bench_slots) * num_teams
    position_demand[pos] = total_slots

# Calculate replacement levels for each position
replacement_level = {}
for pos in positions:
    players_at_pos = data[data['Position List'].apply(lambda x: pos in x)]
    players_at_pos = players_at_pos.sort_values(by='Projected Fantasy Points', ascending=False).reset_index(drop=True)
    replacement_index = int(position_demand[pos]) - 1
    if replacement_index < len(players_at_pos):
        replacement_player = players_at_pos.iloc[replacement_index]
        replacement_level[pos] = replacement_player['Projected Fantasy Points']
    else:
        replacement_level[pos] = 0

# Calculate VORP for each player
def calculate_vorp(row):
    player_positions = row['Position List']
    max_vorp = None
    for pos in player_positions:
        if pos in replacement_level:
            vorp = row['Projected Fantasy Points'] - replacement_level[pos]
            if (max_vorp is None) or (vorp > max_vorp):
                max_vorp = vorp
    return max_vorp if max_vorp is not None else 0

data['VORP'] = data.apply(calculate_vorp, axis=1)

# Adjust VORP for positional scarcity
position_std = {}
for pos in positions:
    players_at_pos = data[data['Position List'].apply(lambda x: pos in x)]
    position_std[pos] = players_at_pos['Projected Fantasy Points'].std()

def adjust_vorp_for_scarcity(row):
    player_positions = row['Position List']
    max_adjusted_vorp = None
    for pos in player_positions:
        if pos in replacement_level and pos in position_std and position_std[pos] != 0:
            vorp = row['Projected Fantasy Points'] - replacement_level[pos]
            adjusted_vorp = vorp / position_std[pos]
            if (max_adjusted_vorp is None) or (adjusted_vorp > max_adjusted_vorp):
                max_adjusted_vorp = adjusted_vorp
    return max_adjusted_vorp if max_adjusted_vorp is not None else 0

data['Adjusted VORP'] = data.apply(adjust_vorp_for_scarcity, axis=1)

# Create tiers based on Projected Fantasy Points
data['Tier'] = pd.qcut(data['Projected Fantasy Points'], q=5, labels=False) + 1  # Tiers 1 to 5

# Save the cleaned data
data.to_csv('cleaned_players_data.csv', index=False)
