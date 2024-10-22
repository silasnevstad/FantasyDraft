import pickle
import os
import pandas as pd
from PyQt5.QtWidgets import QMessageBox

STATE_FILE = 'draft_state.pkl'


class DraftLogic:
    def __init__(self, data: pd.DataFrame, num_teams=12, num_rounds=13):
        """
        Initialize the DraftLogic with player data and draft settings.
        """
        self.data = data.copy()
        self.num_teams = num_teams
        self.num_rounds = num_rounds
        self.roster_slots = {
            'PG': 1,
            'SG': 1,
            'SF': 1,
            'PF': 1,
            'C': 1,
            'G': 1,      # Guard Flex
            'F': 1,      # Forward Flex
            'UTIL': 3,
            'Bench': 3
        }
        self.positions = ['PG', 'SG', 'SF', 'PF', 'C']
        self.available_players = self.data.copy()
        self.team_rosters = {team_num: {position: [] for position in self.roster_slots.keys()}
                             for team_num in range(1, self.num_teams + 1)}
        self.draft_picks = []
        self.current_pick_index = 0
        self.user_draft_position = None
        self.replacement_level = {}
        self.is_calculation_in_progress = False  # To manage calculation state

        # Initialize draft state if exists
        self.load_draft_state()

    def load_draft_state(self):
        """
        Load the draft state from a file if it exists.
        """
        if os.path.exists(STATE_FILE):
            # Loading state is handled externally to allow user prompt
            pass
        else:
            self.setup_new_draft()

    def setup_new_draft(self):
        """
        Initialize a new draft by setting up draft order and rosters.
        """
        # Generate draft order (snake draft)
        draft_order = []
        for round_num in range(self.num_rounds):
            if round_num % 2 == 0:
                picks = list(range(1, self.num_teams + 1))
            else:
                picks = list(range(self.num_teams, 0, -1))
            draft_order.extend(picks)
        # Create a list of tuples (pick_number, team_number)
        self.draft_picks = list(enumerate(draft_order, start=1))
        self.current_pick_index = 0
        self.recalculate_metrics()

    def initialize_new_draft(self, user_position):
        """
        Set the user's draft position and initialize the draft.
        """
        self.user_draft_position = user_position
        self.setup_new_draft()
        self.save_draft_state()

    def load_existing_draft_state(self):
        """
        Load an existing draft state from a file.
        """
        try:
            with open(STATE_FILE, 'rb') as f:
                saved_state = pickle.load(f)
            self.available_players = saved_state['available_players']
            self.team_rosters = saved_state['team_rosters']
            self.user_draft_position = saved_state['user_draft_position']
            self.draft_picks = saved_state['draft_picks']
            self.current_pick_index = saved_state['current_pick_index']
            self.replacement_level = saved_state.get('replacement_level', {})
            self.recalculate_metrics()
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to load saved draft state: {str(e)}")
            self.setup_new_draft()

    def save_draft_state(self):
        """
        Save the current draft state to a file.
        """
        draft_state = {
            'available_players': self.available_players,
            'team_rosters': self.team_rosters,
            'user_draft_position': self.user_draft_position,
            'current_pick_index': self.current_pick_index,
            'draft_picks': self.draft_picks,
            'replacement_level': self.replacement_level
        }
        try:
            with open(STATE_FILE, 'wb') as f:
                pickle.dump(draft_state, f)
        except Exception as e:
            QMessageBox.warning(None, "Save Error", f"Failed to save draft state: {str(e)}")

    def pick_player(self, player_id, team_num):
        """
        Handle picking a player for a team.
        """
        # Check if player is available
        if player_id not in self.available_players['PlayerID'].values:
            raise ValueError("Selected player is not available.")

        # Get player row
        player_row = self.available_players[self.available_players['PlayerID'] == player_id].iloc[0]

        # Assign player to roster
        self.assign_player_to_roster(player_row, self.team_rosters[team_num], team_num)

        # Remove player from available players
        self.available_players = self.available_players[self.available_players['PlayerID'] != player_id].reset_index(drop=True)

        # Recalculate metrics based on updated available players
        self.recalculate_metrics()

        # Increment pick index
        self.current_pick_index += 1

        # Save state
        self.save_draft_state()

    def assign_player_to_roster(self, player_row, team_roster, team_num):
        """
        Assign a player to the appropriate roster slot based on positions needed.
        """
        player_name = player_row['Player']
        player_positions = player_row['Position List']
        needed_positions = self.positions_needed(team_roster)
        assigned = False

        # Calculate position values for the team
        position_values = self.calculate_position_values(team_num)

        # Sort needed positions based on their calculated value
        sorted_positions = sorted(needed_positions, key=lambda pos: position_values.get(pos, 0), reverse=True)

        for pos in sorted_positions:
            # Direct assignment for specific positions
            if pos in ['PG', 'SG', 'SF', 'PF', 'C']:
                if pos in player_positions and len(team_roster[pos]) < self.roster_slots[pos]:
                    team_roster[pos].append(player_name)
                    assigned = True
                    break
            elif pos == 'G':
                # Guard Flex: Assign if player is PG or SG
                if any(p in ['PG', 'SG'] for p in player_positions) and len(team_roster['G']) < self.roster_slots['G']:
                    team_roster['G'].append(player_name)
                    assigned = True
                    break
            elif pos == 'F':
                # Forward Flex: Assign if player is SF or PF
                if any(p in ['SF', 'PF'] for p in player_positions) and len(team_roster['F']) < self.roster_slots['F']:
                    team_roster['F'].append(player_name)
                    assigned = True
                    break
            elif pos == 'UTIL':
                # UTIL can accept any position
                if len(team_roster['UTIL']) < self.roster_slots['UTIL']:
                    team_roster['UTIL'].append(player_name)
                    assigned = True
                    break

        # If not assigned yet, assign to Bench prioritizing higher Combined Score
        if not assigned:
            if len(team_roster['Bench']) < self.roster_slots['Bench']:
                team_roster['Bench'].append(player_name)
                assigned = True
            else:
                QMessageBox.warning(None, "Roster Full",
                                    f"No available roster spot to assign {player_name}. Player remains undrafted.")

    def positions_needed(self, team_roster):
        """
        Determine which positions are still needed for a team.
        """
        needed_positions = []
        for position, limit in self.roster_slots.items():
            filled = len(team_roster[position])
            if filled < limit:
                needed_positions.append(position)
        return needed_positions

    def calculate_position_values(self, team_num):
        """
        Calculate the highest Adjusted VORP available for each needed position.
        """
        team_roster = self.team_rosters[team_num]
        position_values = {}
        for pos in self.roster_slots.keys():
            if len(team_roster[pos]) >= self.roster_slots[pos]:
                continue  # Position already filled
            if pos == 'G':
                filtered = self.available_players[
                    self.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)]
            elif pos == 'F':
                filtered = self.available_players[
                    self.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)]
            else:
                filtered = self.available_players[self.available_players['Position List'].apply(lambda x: pos in x)]
            if not filtered.empty:
                position_values[pos] = filtered['Adjusted VORP'].max()
            else:
                position_values[pos] = 0
        return position_values

    def calculate_scarcity(self, position):
        """
        Calculate the scarcity of a position based on available players.
        Scarcity is inversely proportional to the number of available players.
        """
        if position == 'G':
            count = self.available_players[
                self.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)
            ].shape[0]
        elif position == 'F':
            count = self.available_players[
                self.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)
            ].shape[0]
        else:
            count = self.available_players[
                self.available_players['Position List'].apply(lambda x: position in x)
            ].shape[0]
        return 1 / count if count > 0 else 0

    def recalculate_metrics(self):
        """
        Recalculate all relevant metrics including VORP, Adjusted VORP, Combined Score, and Tiers.
        """
        self.is_calculation_in_progress = True

        position_demand = {}
        for pos in self.positions:
            specific_slots = self.roster_slots.get(pos, 0)
            flex_slots = 0
            if pos in ['PG', 'SG'] and 'G' in self.roster_slots:
                flex_slots += self.roster_slots['G']
            if pos in ['SF', 'PF'] and 'F' in self.roster_slots:
                flex_slots += self.roster_slots['F']
            if 'UTIL' in self.roster_slots:
                flex_slots += self.roster_slots['UTIL']
            bench_slots = self.roster_slots['Bench'] / len(self.positions)
            total_slots = (specific_slots + flex_slots + bench_slots) * self.num_teams
            position_demand[pos] = total_slots

        # Recalculate replacement levels
        replacement_level = {}
        for pos in self.positions:
            players_at_pos = self.available_players[self.available_players['Position List'].apply(lambda x: pos in x)]
            players_at_pos = players_at_pos.sort_values(by='Projected Fantasy Points', ascending=False).reset_index(drop=True)
            replacement_index = int(position_demand[pos]) - 1
            if replacement_index < len(players_at_pos):
                replacement_player = players_at_pos.iloc[replacement_index]
                replacement_level[pos] = replacement_player['Projected Fantasy Points']
            else:
                replacement_level[pos] = 0

        # Update the replacement_level attribute
        self.replacement_level = replacement_level

        # Recalculate VORP for each available player
        def calculate_vorp(row):
            player_positions = row['Position List']
            max_vorp = None
            for pos in player_positions:
                if pos in self.replacement_level:
                    vorp = row['Projected Fantasy Points'] - self.replacement_level[pos]
                    if (max_vorp is None) or (vorp > max_vorp):
                        max_vorp = vorp
            return max_vorp if max_vorp is not None else 0

        self.available_players['VORP'] = self.available_players.apply(calculate_vorp, axis=1)

        # Recalculate Adjusted VORP based on positional scarcity
        position_std = {}
        for pos in self.positions:
            players_at_pos = self.available_players[self.available_players['Position List'].apply(lambda x: pos in x)]
            position_std[pos] = players_at_pos['Projected Fantasy Points'].std()

        def adjust_vorp_for_scarcity(row):
            player_positions = row['Position List']
            max_adjusted_vorp = None
            for pos in player_positions:
                if pos in self.replacement_level and pos in position_std and position_std[pos] != 0:
                    vorp = row['Projected Fantasy Points'] - self.replacement_level[pos]
                    adjusted_vorp = vorp / position_std[pos]
                    if (max_adjusted_vorp is None) or (adjusted_vorp > max_adjusted_vorp):
                        max_adjusted_vorp = adjusted_vorp
            return max_adjusted_vorp if max_adjusted_vorp is not None else 0

        self.available_players['Adjusted VORP'] = self.available_players.apply(adjust_vorp_for_scarcity, axis=1)

        # Define weights for Combined Score
        weight_vorp = 0.7  # 70% weight
        weight_proj_fp = 0.3  # 30% weight

        # Calculate Combined Score
        self.available_players['Combined Score'] = (
            self.available_players['Adjusted VORP'] * weight_vorp +
            (self.available_players['Projected Fantasy Points'] / self.available_players['Projected Fantasy Points'].max()) * weight_proj_fp
        )

        # Recreate tiers based on updated Combined Score
        try:
            self.available_players['Tier'] = pd.qcut(self.available_players['Combined Score'], q=5, labels=False) + 1
        except ValueError:
            # If there are fewer unique values than bins, assign all to tier 1
            self.available_players['Tier'] = 1

        self.is_calculation_in_progress = False

    def get_available_players(self):
        """
        Get the current list of available players.
        """
        return self.available_players.copy()

    def get_team_roster(self, team_num):
        """
        Get the roster of a specific team.
        """
        return self.team_rosters.get(team_num, {})

    def get_all_rosters(self):
        """
        Get all team rosters.
        """
        return self.team_rosters.copy()

    def get_current_pick_info(self):
        """
        Get information about the current pick.
        """
        if self.current_pick_index < len(self.draft_picks):
            pick_num, team_num = self.draft_picks[self.current_pick_index]
            round_num = ((pick_num - 1) // self.num_teams) + 1
            return pick_num, round_num, team_num
        else:
            return None, None, None

    def generate_top_three_recommendations(self):
        """
        Generate top three position recommendations based on Combined Score and scarcity.
        """
        user_roster = self.team_rosters[self.user_draft_position]
        needed_positions = self.positions_needed(user_roster)
        if not needed_positions:
            return []

        # Calculate combined scores based on Combined Score and scarcity
        position_values = self.calculate_position_values(self.user_draft_position)
        scarcity = {pos: self.calculate_scarcity(pos) for pos in needed_positions}
        combined_scores = {pos: position_values.get(pos, 0) * scarcity.get(pos, 1) for pos in needed_positions}

        # Sort positions based on combined scores
        sorted_positions = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)
        top_three = sorted_positions[:3]

        return top_three

    def generate_recommendations_pie_data(self, top_three):
        """
        Generate data for the recommendations pie chart.
        """
        if not top_three:
            return [], []
        positions_pie = [item[0] for item in top_three]
        scores_pie = [item[1] for item in top_three]
        return positions_pie, scores_pie

    def get_position_recommendation(self):
        """
        Get the next recommended position to draft.
        """
        top_three = self.generate_top_three_recommendations()
        if not top_three:
            return "No positions needed."
        top_position = top_three[0][0]
        return f"Next Recommended Position: {top_position}"