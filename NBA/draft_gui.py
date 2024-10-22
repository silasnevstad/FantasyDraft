import sys
import os
import pickle
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
    QComboBox, QListWidget, QListWidgetItem, QInputDialog, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush

# File name for saving the draft state
STATE_FILE = 'draft_state.pkl'

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

class DraftSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.available_players = None
        self.setWindowTitle("Fantasy Draft Simulator")
        self.setGeometry(100, 100, 1800, 1000)

        # Load data
        self.load_data()

        # Initialize draft state
        self.initialize_draft_state()

        # Setup UI
        self.setup_ui()

        # Update UI elements
        self.update_player_table()
        self.update_roster_display()
        self.update_other_rosters_display()
        self.update_position_recommendation()
        self.update_current_pick_label()
        self.update_positional_requirements_chart()
        self.update_top_three_recommendations()

    def load_data(self):
        try:
            if not os.path.exists('cleaned_players_data.csv'):
                raise FileNotFoundError("The file 'cleaned_players_data.csv' does not exist.")
            self.data = pd.read_csv('cleaned_players_data.csv')
            required_columns = {'Player', 'Team', 'Position List', 'Tier', 'Adjusted VORP', 'Projected Fantasy Points'}
            if not required_columns.issubset(set(self.data.columns)):
                missing = required_columns - set(self.data.columns)
                raise ValueError(f"Missing columns in data: {', '.join(missing)}")
            self.data['Position List'] = self.data['Position List'].apply(lambda x: eval(x) if isinstance(x, str) else x)
            self.data = self.data.sort_values(by='Adjusted VORP', ascending=False).reset_index(drop=True)
            self.available_players = self.data.copy()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Error", f"Error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while loading data: {str(e)}")
            sys.exit(1)

    def initialize_draft_state(self):
        self.num_teams = 12
        self.num_rounds = 13

        if os.path.exists(STATE_FILE):
            choice = QMessageBox.question(
                self, "Resume Draft",
                "A saved draft state was found. Do you want to resume the previous draft?",
                QMessageBox.Yes | QMessageBox.No
            )
            if choice == QMessageBox.Yes:
                try:
                    with open(STATE_FILE, 'rb') as f:
                        saved_state = pickle.load(f)
                    self.available_players = saved_state['available_players']
                    self.team_rosters = saved_state['team_rosters']
                    self.user_draft_position = saved_state['user_draft_position']
                    self.draft_picks = saved_state['draft_picks']
                    self.current_pick_index = saved_state['current_pick_index']
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to load saved draft state: {str(e)}")
                    self.setup_new_draft()
            else:
                try:
                    os.remove(STATE_FILE)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete saved draft state: {str(e)}")
                self.setup_new_draft()
        else:
            self.setup_new_draft()

    def setup_new_draft(self):
        while True:
            draft_position, ok = QInputDialog.getInt(
                self, "Draft Position", f"Enter your draft position (1-{self.num_teams}):", 1, 1, self.num_teams, 1
            )
            if not ok:
                sys.exit(0)
            if 1 <= draft_position <= self.num_teams:
                self.user_draft_position = draft_position
                break
            else:
                QMessageBox.warning(self, "Invalid Input", f"Please enter a number between 1 and {self.num_teams}.")

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
        # Initialize team rosters (including other teams)
        self.team_rosters = {team_num: {position: [] for position in roster_slots.keys()} for team_num in range(1, self.num_teams + 1)}
        self.current_pick_index = 0

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left panel: Player list, filters, and search
        left_panel = QVBoxLayout()

        # Header
        header_label = QLabel("Available Players")
        header_label.setFont(QFont("Arial", 18, QFont.Bold))
        left_panel.addWidget(header_label)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search Player:")
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Enter player name...")
        self.search_bar.textChanged.connect(self.update_player_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_bar)
        left_panel.addLayout(search_layout)

        # Filter by position
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter by Position:")
        self.position_filter = QComboBox()
        self.position_filter.addItem("All")
        for pos in roster_slots.keys():
            self.position_filter.addItem(pos)
        self.position_filter.currentIndexChanged.connect(self.update_player_table)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.position_filter)
        left_panel.addLayout(filter_layout)

        # Player table
        self.player_table = QTableWidget()
        self.player_table.setColumnCount(6)
        self.player_table.setHorizontalHeaderLabels(['Player', 'Team', 'Position', 'Tier', 'Adjusted VORP', 'Projected FP'])
        self.player_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.player_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.player_table.setSelectionMode(QTableWidget.SingleSelection)
        self.player_table.setStyleSheet("alternate-background-color: #f0f0f0;")
        self.player_table.setSortingEnabled(True)  # Enable sorting
        left_panel.addWidget(self.player_table)

        # Pick button
        self.pick_button = QPushButton("Pick Selected Player")
        self.pick_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.pick_button.clicked.connect(self.handle_pick)
        left_panel.addWidget(self.pick_button)

        # Save Draft Button
        self.save_button = QPushButton("Save Draft")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #008CBA;
                color: white;
                padding: 12px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #007BB5;
            }
        """)
        self.save_button.clicked.connect(self.save_draft_state)
        left_panel.addWidget(self.save_button)

        main_layout.addLayout(left_panel, 60)

        # Right panel: Rosters, Draft Info, Recommendations, and Visuals
        right_panel = QVBoxLayout()

        # Current Pick Info
        self.current_pick_label = QLabel("Current Pick: ")
        self.current_pick_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.current_pick_label.setStyleSheet("color: #FFD700;")  # Gold color for prominence
        right_panel.addWidget(self.current_pick_label)

        # Your Roster
        roster_label = QLabel("Your Current Roster:")
        roster_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(roster_label)
        self.roster_list = QListWidget()
        self.roster_list.setStyleSheet("background-color: #3C3C3C; color: #FFFFFF;")
        right_panel.addWidget(self.roster_list)

        # Other Teams' Rosters
        other_rosters_label = QLabel("Other Teams' Rosters:")
        other_rosters_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(other_rosters_label)
        self.other_rosters_list = QListWidget()
        self.other_rosters_list.setStyleSheet("background-color: #3C3C3C; color: #FFFFFF;")
        right_panel.addWidget(self.other_rosters_list)

        # Top Three Position Recommendations
        recommendations_label = QLabel("Top 3 Position Recommendations:")
        recommendations_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(recommendations_label)
        self.top_three_recommendations = QListWidget()
        self.top_three_recommendations.setStyleSheet("background-color: #3C3C3C; color: #FFFFFF;")
        right_panel.addWidget(self.top_three_recommendations)

        # Positional Requirements Chart
        chart_label = QLabel("Positional Requirements:")
        chart_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(chart_label)
        self.figure, self.ax = plt.subplots(figsize=(6,5))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_panel.addWidget(self.canvas)

        main_layout.addLayout(right_panel, 40)

    def update_player_table(self):
        filter_pos = self.position_filter.currentText()
        search_text = self.search_bar.text().lower()
        if filter_pos == "All":
            filtered_players = self.available_players
        else:
            filtered_players = self.available_players[
                self.available_players['Position List'].apply(lambda x: filter_pos in x)
            ]
        if search_text:
            filtered_players = filtered_players[
                filtered_players['Player'].str.lower().str.contains(search_text)
            ]

        self.player_table.setRowCount(len(filtered_players))

        for row_idx, (_, player) in enumerate(filtered_players.iterrows()):
            player_item = QTableWidgetItem(player['Player'])
            team_item = QTableWidgetItem(player['Team'])
            position_item = QTableWidgetItem(', '.join(player['Position List']))
            tier_item = QTableWidgetItem(str(player['Tier']))
            vorp_item = QTableWidgetItem(str(player['Adjusted VORP']))
            fp_item = QTableWidgetItem(str(player['Projected Fantasy Points']))

            # Highlight top 10 players based on Adjusted VORP
            if row_idx < 10:
                for item in [player_item, team_item, position_item, tier_item, vorp_item, fp_item]:
                    item.setBackground(QBrush(QColor(255, 215, 0, 100)))  # Light Gold

            self.player_table.setItem(row_idx, 0, player_item)
            self.player_table.setItem(row_idx, 1, team_item)
            self.player_table.setItem(row_idx, 2, position_item)
            self.player_table.setItem(row_idx, 3, tier_item)
            self.player_table.setItem(row_idx, 4, vorp_item)
            self.player_table.setItem(row_idx, 5, fp_item)

        self.player_table.resizeColumnsToContents()

    def handle_pick(self):
        if self.current_pick_index >= len(self.draft_picks):
            QMessageBox.information(self, "Draft Completed", "All picks have been made.")
            return

        pick_num, team_num = self.draft_picks[self.current_pick_index]
        round_num = ((pick_num - 1) // self.num_teams) + 1

        selected_items = self.player_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a player to pick.")
            return

        player_name = selected_items[0].text()
        try:
            player_row = self.available_players[self.available_players['Player'] == player_name].iloc[0]
        except IndexError:
            QMessageBox.warning(self, "Selection Error", "Selected player not found in available players.")
            return

        # Assign player to the current pick's team
        self.assign_player_to_roster(player_row, self.team_rosters[team_num], team_num)

        # Remove the player from available players
        self.available_players = self.available_players[self.available_players['Player'] != player_name].reset_index(drop=True)

        # Update UI elements
        self.update_player_table()
        self.update_roster_display()
        self.update_other_rosters_display()
        self.update_position_recommendation()
        self.current_pick_index += 1
        self.update_current_pick_label()
        self.update_positional_requirements_chart()
        self.update_top_three_recommendations()
        self.save_draft_state()

        # Auto-recommend next pick if it's the user's turn
        if team_num == self.user_draft_position:
            self.auto_recommend_pick()

    def assign_player_to_roster(self, player_row, team_roster, team_num):
        player_name = player_row['Player']
        player_positions = player_row['Position List']
        needed_positions = self.positions_needed(team_roster)
        assigned = False

        # Calculate position values for the team
        position_values = self.calculate_position_values(team_num)

        # Sort needed positions based on their calculated value
        sorted_positions = sorted(needed_positions, key=lambda pos: position_values.get(pos, 0), reverse=True)

        for pos in sorted_positions:
            if pos in player_positions and len(team_roster[pos]) < roster_slots[pos]:
                team_roster[pos].append(player_name)
                assigned = True
                break
            # Assign to G slot if eligible and needed
            if pos == 'G' and any(p in ['PG', 'SG'] for p in player_positions) and len(team_rosters[team_num]['G']) < roster_slots['G']:
                team_roster['G'].append(player_name)
                assigned = True
                break
            # Assign to F slot if eligible and needed
            if pos == 'F' and any(p in ['SF', 'PF'] for p in player_positions) and len(team_rosters[team_num]['F']) < roster_slots['F']:
                team_roster['F'].append(player_name)
                assigned = True
                break

        # Assign to UTIL slot if eligible and needed
        if not assigned:
            if 'UTIL' in needed_positions and len(team_roster['UTIL']) < roster_slots['UTIL']:
                team_roster['UTIL'].append(player_name)
                assigned = True

        # Assign to Bench if still not assigned
        if not assigned:
            if len(team_roster['Bench']) < roster_slots['Bench']:
                team_roster['Bench'].append(player_name)
                assigned = True
            else:
                QMessageBox.warning(self, "Roster Full", f"No available roster spot to assign {player_name}. Player remains undrafted.")

    def positions_needed(self, team_roster):
        needed_positions = []
        for position, limit in roster_slots.items():
            filled = len(team_roster[position])
            if filled < limit:
                needed_positions.append(position)
        return needed_positions

    def update_roster_display(self):
        self.roster_list.clear()
        user_roster = self.team_rosters[self.user_draft_position]
        for position, players in user_roster.items():
            players_str = ', '.join(players) if players else 'None'
            item = QListWidgetItem(f"{position}: {players_str}")
            self.roster_list.addItem(item)

    def update_other_rosters_display(self):
        self.other_rosters_list.clear()
        for team_num, roster in self.team_rosters.items():
            if team_num == self.user_draft_position:
                continue  # Skip your own team
            roster_items = []
            for pos, players in roster.items():
                players_str = ', '.join(players) if players else 'None'
                roster_items.append(f"{pos}: {players_str}")
            roster_str = '; '.join(roster_items)
            item = QListWidgetItem(f"Team {team_num}: {roster_str}")
            self.other_rosters_list.addItem(item)

    def update_position_recommendation(self):
        user_roster = self.team_rosters[self.user_draft_position]
        needed_positions = self.positions_needed(user_roster)
        if not needed_positions:
            recommendation = "No positions needed."
        else:
            # Recommend positions based on value over replacement and scarcity
            position_values = self.calculate_position_values(self.user_draft_position)
            # Calculate scarcity: lower available players means higher scarcity
            scarcity = {pos: self.calculate_scarcity(pos) for pos in needed_positions}
            # Combine value and scarcity
            combined_scores = {pos: position_values.get(pos, 0) * scarcity.get(pos, 1) for pos in needed_positions}
            # Get top recommendation
            top_position = max(combined_scores, key=combined_scores.get)
            recommendation = f"Next Recommended Position: {top_position}"
        self.position_recommendation_label.setText(recommendation)

    def calculate_position_values(self, team_num):
        # Calculate the highest Adjusted VORP available for each needed position
        team_roster = self.team_rosters[team_num]
        position_values = {}
        for pos in roster_slots.keys():
            if len(team_roster[pos]) >= roster_slots[pos]:
                continue  # Position already filled
            if pos == 'G':
                filtered = self.available_players[self.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)]
            elif pos == 'F':
                filtered = self.available_players[self.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)]
            else:
                filtered = self.available_players[self.available_players['Position List'].apply(lambda x: pos in x)]
            if not filtered.empty:
                position_values[pos] = filtered['Adjusted VORP'].max()
            else:
                position_values[pos] = 0
        return position_values

    def calculate_scarcity(self, position):
        # Scarcity is inversely proportional to the number of available players
        if position == 'G':
            count = self.available_players[self.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)].shape[0]
        elif position == 'F':
            count = self.available_players[self.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)].shape[0]
        else:
            count = self.available_players[self.available_players['Position List'].apply(lambda x: position in x)].shape[0]
        return 1 / count if count > 0 else 0

    def update_current_pick_label(self):
        if self.current_pick_index < len(self.draft_picks):
            pick_num, team_num = self.draft_picks[self.current_pick_index]
            round_num = ((pick_num - 1) // self.num_teams) + 1
            if team_num == self.user_draft_position:
                pick_info = f"Pick #{pick_num} (Round {round_num}) - Your Pick"
                color = "#FFD700"  # Gold
            else:
                pick_info = f"Pick #{pick_num} (Round {round_num}) - Team {team_num}'s Pick"
                color = "#FFFFFF"  # White
            self.current_pick_label.setText(f"Current Pick: {pick_info}")
            self.current_pick_label.setStyleSheet(f"color: {color};")
        else:
            self.current_pick_label.setText("Draft Completed")
            self.current_pick_label.setStyleSheet("color: #FF0000;")  # Red

    def save_draft_state(self):
        draft_state = {
            'available_players': self.available_players,
            'team_rosters': self.team_rosters,
            'user_draft_position': self.user_draft_position,
            'current_pick_index': self.current_pick_index,
            'draft_picks': self.draft_picks,
        }
        try:
            with open(STATE_FILE, 'wb') as f:
                pickle.dump(draft_state, f)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save draft state: {str(e)}")

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, 'Quit', 'Do you want to save the draft before exiting?',
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.save_draft_state()
            event.accept()
        elif reply == QMessageBox.No:
            event.accept()
        else:
            event.ignore()

    def update_positional_requirements_chart(self):
        # Calculate needed positions
        user_roster = self.team_rosters[self.user_draft_position]
        needed_positions = self.positions_needed(user_roster)

        # Count needed per position
        needed_counts = {pos: roster_slots[pos] - len(user_roster[pos]) for pos in needed_positions}

        # Count available players per position
        available_counts = {}
        for pos in needed_positions:
            if pos == 'G':
                count = self.available_players[self.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)].shape[0]
            elif pos == 'F':
                count = self.available_players[self.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)].shape[0]
            else:
                count = self.available_players[self.available_players['Position List'].apply(lambda x: pos in x)].shape[0]
            available_counts[pos] = count

        # Clear the previous plot
        self.ax.clear()

        positions = list(needed_counts.keys())
        needed = list(needed_counts.values())
        available = [available_counts.get(pos, 0) for pos in positions]

        x = range(len(positions))
        self.ax.bar(x, needed, width=0.4, label='Needed', align='center', color='#FF6347')  # Tomato color
        self.ax.bar(x, available, width=0.4, bottom=needed, label='Available', align='center', color='#4682B4')  # SteelBlue color

        self.ax.set_xticks(x)
        self.ax.set_xticklabels(positions)
        self.ax.set_ylabel('Number of Players')
        self.ax.set_title('Positional Requirements vs Available Players')
        self.ax.legend()

        self.figure.tight_layout()
        self.canvas.draw()

    def update_top_three_recommendations(self):
        self.top_three_recommendations.clear()
        user_roster = self.team_rosters[self.user_draft_position]
        needed_positions = self.positions_needed(user_roster)
        if not needed_positions:
            item = QListWidgetItem("No positions needed.")
            self.top_three_recommendations.addItem(item)
            return

        # Calculate combined scores based on VORP and scarcity
        position_values = self.calculate_position_values(self.user_draft_position)
        scarcity = {pos: self.calculate_scarcity(pos) for pos in needed_positions}
        combined_scores = {pos: position_values.get(pos, 0) * scarcity.get(pos, 1) for pos in needed_positions}
        # Sort positions based on combined scores
        sorted_positions = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)
        top_three = sorted_positions[:3]

        for pos, score in top_three:
            item = QListWidgetItem(f"{pos} (Score: {score:.2f})")
            self.top_three_recommendations.addItem(item)

    def auto_recommend_pick(self):
        # Display a message box with top three recommendations
        if self.top_three_recommendations.count() == 0:
            QMessageBox.information(self, "Recommendation", "No recommendations available.")
            return
        recommendations = []
        for index in range(self.top_three_recommendations.count()):
            recommendations.append(self.top_three_recommendations.item(index).text())
        rec_text = "\n".join(recommendations)
        QMessageBox.information(self, "Top 3 Recommendations", f"Based on your team needs and player availability, consider drafting:\n\n{rec_text}")

def main():
    app = QApplication(sys.argv)
    # Apply a stylesheet for better aesthetics
    app.setStyle("Fusion")
    stylesheet = """
        QMainWindow {
            background-color: #2E2E2E;
            color: #FFFFFF;
        }
        QLabel {
            color: #FFFFFF;
        }
        QListWidget {
            background-color: #3C3C3C;
            color: #FFFFFF;
            border: 1px solid #555555;
            padding: 5px;
        }
        QTableWidget {
            background-color: #3C3C3C;
            color: #FFFFFF;
            gridline-color: #555555;
        }
        QHeaderView::section {
            background-color: #555555;
            color: #FFFFFF;
            padding: 6px;
            border: 1px solid #2E2E2E;
            font-size: 14px;
        }
        QPushButton {
            font-size: 16px;
        }
        QComboBox {
            background-color: #555555;
            color: #FFFFFF;
            padding: 5px;
            border-radius: 3px;
        }
        QLineEdit {
            background-color: #555555;
            color: #FFFFFF;
            padding: 5px;
            border-radius: 3px;
        }
    """
    app.setStyleSheet(stylesheet)
    simulator = DraftSimulator()
    simulator.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
