import pandas as pd
import readline
import sys
import os
import pickle

# File name for saving the draft state
STATE_FILE = 'draft_state.pkl'

# Load the cleaned data
try:
    data = pd.read_csv('cleaned_players_data.csv')
except FileNotFoundError:
    print("Error: 'cleaned_players_data.csv' not found. Please ensure the data preparation script has been run successfully.")
    sys.exit(1)

# Convert 'Position List' from string representation to actual list
data['Position List'] = data['Position List'].apply(eval)

# Sort players by Adjusted VORP in descending order
data = data.sort_values(by='Adjusted VORP', ascending=False).reset_index(drop=True)

# Initialize variables
num_teams = 12
num_rounds = 13
valid_positions = list(range(1, num_teams + 1))

# Function to validate user draft position input
def get_user_draft_position():
    while True:
        try:
            user_pos = int(input("Enter your draft position (1-12): "))
            if 1 <= user_pos <= num_teams:
                return user_pos
            else:
                print(f"Invalid input. Please enter a number between 1 and {num_teams}.")
        except ValueError:
            print("Invalid input. Please enter a valid integer.")

# Roster slots based on league settings
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

# Check if a saved state exists
if os.path.exists(STATE_FILE):
    print("A saved draft state was found.")
    while True:
        choice = input("Do you want to resume the previous draft? (yes/no): ").strip().lower()
        if choice in ['yes', 'y']:
            with open(STATE_FILE, 'rb') as f:
                saved_state = pickle.load(f)
            available_players = saved_state['available_players']
            team_rosters = saved_state['team_rosters']
            user_draft_position = saved_state['user_draft_position']
            current_pick_index = saved_state['current_pick_index']
            draft_picks = saved_state['draft_picks']
            user_roster = team_rosters[user_draft_position]
            break
        elif choice in ['no', 'n']:
            os.remove(STATE_FILE)
            user_draft_position = get_user_draft_position()
            # Generate draft order (snake draft)
            draft_order = []
            for round_num in range(num_rounds):
                if round_num % 2 == 0:
                    picks = list(range(1, num_teams + 1))
                else:
                    picks = list(range(num_teams, 0, -1))
                draft_order.extend(picks)
            # Create a list of tuples (pick_number, team_number)
            draft_picks = list(enumerate(draft_order, start=1))
            available_players = data.copy()
            # Initialize team rosters (including other teams)
            team_rosters = {team_num: {position: [] for position in roster_slots.keys()} for team_num in range(1, num_teams + 1)}
            user_roster = team_rosters[user_draft_position]
            current_pick_index = 0
            break
        else:
            print("Please answer 'yes' or 'no'.")
else:
    user_draft_position = get_user_draft_position()
    # Generate draft order (snake draft)
    draft_order = []
    for round_num in range(num_rounds):
        if round_num % 2 == 0:
            picks = list(range(1, num_teams + 1))
        else:
            picks = list(range(num_teams, 0, -1))
        draft_order.extend(picks)
    # Create a list of tuples (pick_number, team_number)
    draft_picks = list(enumerate(draft_order, start=1))
    available_players = data.copy()
    # Initialize team rosters (including other teams)
    team_rosters = {team_num: {position: [] for position in roster_slots.keys()} for team_num in range(1, num_teams + 1)}
    user_roster = team_rosters[user_draft_position]
    current_pick_index = 0

def positions_needed(roster_slots, team_roster):
    """Determine which positions are still needed for a team."""
    needed_positions = []
    for position, limit in roster_slots.items():
        filled = len(team_roster[position])
        if filled < limit:
            needed_positions.append(position)
    return needed_positions

def update_completer(player_list):
    """Update the readline completer with the current list of available players."""

    def completer(text, state):
        options = [name for name in player_list if name.lower().startswith(text.lower())]
        if state < len(options):
            return options[state]
        else:
            return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

def find_player_by_name(name_input):
    matching_players = available_players[available_players['Player'].str.contains(name_input, case=False, na=False)]
    if len(matching_players) == 1:
        return matching_players.iloc[0]['Player']
    elif len(matching_players) > 1:
        print("Multiple players match your input. Please be more specific:")
        print(matching_players['Player'].tolist())
        return None
    else:
        return None

def assign_player_to_roster(player_row, team_roster):
    """Assign a player to the appropriate roster slot."""
    player_name = player_row['Player']
    player_positions = player_row['Position List']
    needed_positions = positions_needed(roster_slots, team_roster)
    assigned = False

    # Assign to the first fitting position
    for pos in player_positions:
        if pos in needed_positions and len(team_roster[pos]) < roster_slots[pos]:
            team_roster[pos].append(player_name)
            assigned = True
            break
        # Assign to G slot if eligible and needed
        if pos in ['PG', 'SG'] and 'G' in needed_positions and len(team_roster['G']) < roster_slots['G']:
            team_roster['G'].append(player_name)
            assigned = True
            break
        # Assign to F slot if eligible and needed
        if pos in ['SF', 'PF'] and 'F' in needed_positions and len(team_roster['F']) < roster_slots['F']:
            team_roster['F'].append(player_name)
            assigned = True
            break
    # Assign to UTIL slot if eligible and needed
    if not assigned and 'UTIL' in needed_positions and len(team_roster['UTIL']) < roster_slots['UTIL']:
        team_roster['UTIL'].append(player_name)
        assigned = True

    # If not assigned to any specific slot, assign to Bench
    if not assigned:
        if len(team_roster['Bench']) < roster_slots['Bench']:
            team_roster['Bench'].append(player_name)
        else:
            print(f"Warning: No available roster spot to assign {player_name}. Player remains undrafted.")

def simulate_other_team_pick(team_num):
    """Automatically pick the best available player for other teams based on Adjusted VORP and team needs."""
    global available_players  # Declare as global to modify the variable outside the function
    team_roster = team_rosters[team_num]
    needed_positions = positions_needed(roster_slots, team_roster)

    def player_fits_team_needs(row):
        player_positions = row['Position List']
        for pos in player_positions:
            if pos in needed_positions:
                return True
            if pos in ['PG', 'SG'] and 'G' in needed_positions:
                return True
            if pos in ['SF', 'PF'] and 'F' in needed_positions:
                return True
            if 'UTIL' in needed_positions:
                return True
        return False

    potential_picks = available_players[available_players.apply(player_fits_team_needs, axis=1)]
    if potential_picks.empty:
        potential_picks = available_players

    if not potential_picks.empty:
        # Select the highest Adjusted VORP player
        pick_row = potential_picks.sort_values(by='Adjusted VORP', ascending=False).iloc[0]
        pick_player = pick_row['Player']
        assign_player_to_roster(pick_row, team_roster)
        # Remove player from available players
        available_players = available_players[available_players['Player'] != pick_player]
        # Update completer after the pick
        update_completer(available_players['Player'].tolist())
        print(f"Team {team_num} drafted {pick_player}")
        return pick_player
    else:
        print(f"Team {team_num} has no available players to draft.")
        return None

# Initial autocomplete setup
update_completer(available_players['Player'].tolist())

# Main draft loop starting from the current pick index
while current_pick_index < len(draft_picks):
    pick_num, team_num = draft_picks[current_pick_index]
    round_num = ((pick_num - 1) // num_teams) + 1

    if team_num == user_draft_position:
        print(f"\n=== Your Pick: #{pick_num} (Round {round_num}) ===")
        needed_positions = positions_needed(roster_slots, user_roster)
        print("Positions needed:", needed_positions)

        # Function to determine if a player fills needed positions
        def player_fills_needed_positions(row):
            player_positions = row['Position List']
            for pos in player_positions:
                if pos in needed_positions:
                    return True
                if pos in ['PG', 'SG'] and 'G' in needed_positions:
                    return True
                if pos in ['SF', 'PF'] and 'F' in needed_positions:
                    return True
            if 'UTIL' in needed_positions:
                return True
            return False

        # Get recommended players based on VORP and positions needed
        recommended_players = available_players[available_players.apply(player_fills_needed_positions, axis=1)]
        # Sort by Adjusted VORP
        recommended_players = recommended_players.sort_values(by='Adjusted VORP', ascending=False)

        if recommended_players.empty:
            print("No recommended players available for your current needs.")
            top_players = available_players.sort_values(by='Adjusted VORP', ascending=False).head(10)
        else:
            top_players = recommended_players.head(10)

        print("\nTop recommended players:")
        print(top_players[['Player', 'Team', 'Position', 'Tier', 'Adjusted VORP', 'Projected Fantasy Points']].to_string(index=False))

        if not top_players.empty:
            suggested_player = top_players.iloc[0]['Player']
            print(f"\nSuggested Pick: {suggested_player}")

            # Update completer with current available players
            update_completer(available_players['Player'].tolist())

            # Get user's pick with autocomplete
            while True:
                user_pick = input("\nEnter the player you want to draft (or press Enter to pick the suggested player): ").strip()
                if user_pick == '':
                    user_pick = suggested_player
                    print(f"Auto-selected suggested player: {user_pick}")
                player_name = find_player_by_name(user_pick)
                if player_name:
                    user_pick = player_name
                    break
                else:
                    print("Invalid player. Please enter a valid player name from the available players.")
            # Add to user's team
            player_row = available_players[available_players['Player'] == user_pick].iloc[0]
            assign_player_to_roster(player_row, user_roster)
            # Remove player from available players
            available_players = available_players[available_players['Player'] != user_pick]
            # Update completer after the pick
            update_completer(available_players['Player'].tolist())
        else:
            print("No available players to draft for your pick.")
    else:
        print(f"\n=== Pick #{pick_num} by Team {team_num} (Round {round_num}) ===")
        # Prompt user to input other team's pick with autocomplete
        while True:
            other_pick = input(f"Enter the player drafted by Team {team_num} (or type 'auto' to auto-pick): ").strip()
            if other_pick.lower() == 'auto':
                simulate_other_team_pick(team_num)
                break
            else:
                player_name = find_player_by_name(other_pick)
                if player_name:
                    other_pick = player_name
                    # Assign the picked player to the team's roster
                    player_row = available_players[available_players['Player'] == other_pick].iloc[0]
                    assign_player_to_roster(player_row, team_roster=team_rosters[team_num])
                    # Remove player from available players
                    available_players = available_players[available_players['Player'] != other_pick]
                    # Update completer after the pick
                    update_completer(available_players['Player'].tolist())
                    print(f"Team {team_num} drafted {other_pick}")
                    break
                else:
                    print("Invalid player. Please enter a valid player name from the available players or type 'auto' to auto-pick.")

    # Save the current state after each pick
    current_pick_index += 1  # Move to the next pick
    draft_state = {
        'available_players': available_players,
        'team_rosters': team_rosters,
        'user_draft_position': user_draft_position,
        'current_pick_index': current_pick_index,
        'draft_picks': draft_picks,
    }
    with open(STATE_FILE, 'wb') as f:
        pickle.dump(draft_state, f)

# After the draft, display your team
print("\n=== Your Final Team ===")
for position, players in user_roster.items():
    print(f"{position}: {players}")

# Remove the saved state file as the draft is complete
if os.path.exists(STATE_FILE):
    os.remove(STATE_FILE)
