import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
    QComboBox, QListWidget, QListWidgetItem, QInputDialog, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from data_loader import DataLoader
from draft_logic import DraftLogic, STATE_FILE


class DraftSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fantasy Draft Simulator")
        self.setGeometry(100, 100, 1800, 1000)

        # Initialize DataLoader and load data
        self.data_loader = DataLoader()
        self.data = self.data_loader.load_data()

        # Initialize DraftLogic
        self.logic = DraftLogic(self.data)

        # Setup UI
        self.setup_ui()

        # Initialize draft state
        self.initialize_draft_state()

        # Update UI elements
        self.update_player_table()
        self.update_roster_display()
        self.update_other_rosters_display()
        self.update_position_recommendation()
        self.update_current_pick_label()
        self.update_positional_requirements_chart()
        self.update_top_three_recommendations()
        self.update_recommendations_pie_chart()

    def initialize_draft_state(self):
        """
        Initialize the draft state by loading existing state or setting up a new draft.
        """
        if os.path.exists(STATE_FILE):
            choice = QMessageBox.question(
                self, "Resume Draft",
                "A saved draft state was found. Do you want to resume the previous draft?",
                QMessageBox.Yes | QMessageBox.No
            )
            if choice == QMessageBox.Yes:
                try:
                    self.logic.load_existing_draft_state()
                except:
                    QMessageBox.warning(self, "Error", "Failed to load saved draft state. Starting a new draft.")
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
        """
        Prompt the user to enter their draft position and initialize a new draft.
        """
        while True:
            draft_position, ok = QInputDialog.getInt(
                self, "Draft Position",
                f"Enter your draft position (1-{self.logic.num_teams}):", 1, 1, self.logic.num_teams, 1
            )
            if not ok:
                sys.exit(0)
            if 1 <= draft_position <= self.logic.num_teams:
                self.logic.initialize_new_draft(draft_position)
                break
            else:
                QMessageBox.warning(self, "Invalid Input", f"Please enter a number between 1 and {self.logic.num_teams}.")

    def setup_ui(self):
        """
        Set up the user interface components.
        """
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
        for pos in self.logic.roster_slots.keys():
            self.position_filter.addItem(pos)
        self.position_filter.currentIndexChanged.connect(self.update_player_table)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.position_filter)
        left_panel.addLayout(filter_layout)

        # Player table
        self.player_table = QTableWidget()
        self.player_table.setColumnCount(9)  # Updated to 9 columns (Added Combined Score)
        self.player_table.setHorizontalHeaderLabels(
            ['PlayerID', 'Player', 'Team', 'Position', 'Tier', 'Adjusted VORP', 'Projected FP', 'Fantasy AVG', 'Combined Score']
        )
        self.player_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.player_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.player_table.setSelectionMode(QTableWidget.SingleSelection)
        self.player_table.setStyleSheet("alternate-background-color: #f0f0f0;")
        self.player_table.setSortingEnabled(True)  # Enable sorting
        self.player_table.hideColumn(0)  # Hide PlayerID column
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
        self.save_button.clicked.connect(self.logic.save_draft_state)
        left_panel.addWidget(self.save_button)

        main_layout.addLayout(left_panel, 60)

        # Right panel: Rosters, Draft Info, Recommendations, and Visuals
        right_panel = QVBoxLayout()

        # Current Pick Info
        self.current_pick_label = QLabel("Current Pick: ")
        self.current_pick_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.current_pick_label.setStyleSheet("color: #FFD700;")  # Gold color for prominence
        right_panel.addWidget(self.current_pick_label)

        # Indicate if calculation is in progress
        self.calculation_label = QLabel("Calculating Metrics...")
        self.calculation_label.setFont(QFont("Arial", 14))
        self.calculation_label.setStyleSheet("color: #FF0000;")  # Red color
        self.calculation_label.hide()  # Hide initially
        right_panel.addWidget(self.calculation_label)

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
        self.figure, self.ax = plt.subplots(figsize=(6, 5))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_panel.addWidget(self.canvas)

        # Top Three Recommendations Pie Chart
        pie_chart_label = QLabel("Top 3 Recommendations Pie Chart:")
        pie_chart_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(pie_chart_label)
        self.pie_figure, self.pie_ax = plt.subplots(figsize=(4, 4))
        self.pie_canvas = FigureCanvas(self.pie_figure)
        self.pie_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_panel.addWidget(self.pie_canvas)

        # Position Recommendation Label
        self.position_recommendation_label = QLabel("Next Recommended Position: ")
        self.position_recommendation_label.setFont(QFont("Arial", 12))
        self.position_recommendation_label.setStyleSheet("color: #FFA500;")  # Orange color
        right_panel.addWidget(self.position_recommendation_label)

        # Best Projected Picks Section
        best_picks_label = QLabel("Best Projected Picks:")
        best_picks_label.setFont(QFont("Arial", 14, QFont.Bold))
        right_panel.addWidget(best_picks_label)
        self.best_picks_list = QListWidget()
        self.best_picks_list.setStyleSheet("background-color: #3C3C3C; color: #FFFFFF;")
        right_panel.addWidget(self.best_picks_list)

        main_layout.addLayout(right_panel, 40)

    def update_player_table(self):
        """
        Update the player table based on current filters and search criteria.
        """
        filter_pos = self.position_filter.currentText()
        search_text = self.search_bar.text().lower()

        if filter_pos == "All":
            filtered_players = self.logic.available_players
        else:
            # Adjust filter logic for flex positions
            if filter_pos == 'G':
                # G can be PG or SG
                filtered_players = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)
                ]
            elif filter_pos == 'F':
                # F can be SF or PF
                filtered_players = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)
                ]
            else:
                # For other specific positions (PG, SG, SF, PF, C)
                filtered_players = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: filter_pos in x)
                ]

        if search_text:
            filtered_players = filtered_players[
                filtered_players['Player'].str.lower().str.contains(search_text)
            ]

        self.player_table.setRowCount(len(filtered_players))

        for row_idx, (_, player) in enumerate(filtered_players.iterrows()):
            player_id_item = QTableWidgetItem(str(player['PlayerID']))
            player_name_item = QTableWidgetItem(player['Player'])
            team_item = QTableWidgetItem(player['Team'])
            position_item = QTableWidgetItem(', '.join(player['Position List']))
            tier_item = QTableWidgetItem(str(player['Tier']))
            vorp_item = QTableWidgetItem(f"{player['Adjusted VORP']:.2f}")
            fp_item = QTableWidgetItem(f"{player['Projected Fantasy Points']:.2f}")
            fp_avg_item = QTableWidgetItem(f"{player['Fantasy AVG']:.2f}")
            combined_score_item = QTableWidgetItem(f"{player['Combined Score']:.2f}")

            # Highlight top 10 players based on Combined Score
            if row_idx < 10:
                for item in [player_id_item, player_name_item, team_item, position_item, tier_item, vorp_item, fp_item, fp_avg_item, combined_score_item]:
                    item.setBackground(QBrush(QColor(255, 215, 0, 100)))  # Light Gold

            self.player_table.setItem(row_idx, 0, player_id_item)
            self.player_table.setItem(row_idx, 1, player_name_item)
            self.player_table.setItem(row_idx, 2, team_item)
            self.player_table.setItem(row_idx, 3, position_item)
            self.player_table.setItem(row_idx, 4, tier_item)
            self.player_table.setItem(row_idx, 5, vorp_item)
            self.player_table.setItem(row_idx, 6, fp_item)
            self.player_table.setItem(row_idx, 7, fp_avg_item)
            self.player_table.setItem(row_idx, 8, combined_score_item)

        self.player_table.resizeColumnsToContents()

        # Update Best Projected Picks based on Combined Score
        self.update_best_projected_picks()

    def handle_pick(self):
        """
        Handle the action when the user clicks the 'Pick Selected Player' button.
        """
        if self.logic.current_pick_index >= len(self.logic.draft_picks):
            QMessageBox.information(self, "Draft Completed", "All picks have been made.")
            return

        pick_info = self.logic.get_current_pick_info()
        if not pick_info[0]:
            QMessageBox.information(self, "Draft Completed", "All picks have been made.")
            return
        pick_num, round_num, team_num = pick_info

        selected_row = self.player_table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a player to pick.")
            return

        player_id_item = self.player_table.item(selected_row, 0)  # Column 0 is PlayerID
        if not player_id_item:
            QMessageBox.warning(self, "Selection Error", "Failed to retrieve PlayerID.")
            return

        try:
            player_id = int(player_id_item.text())
        except ValueError:
            QMessageBox.warning(self, "Selection Error", "Invalid PlayerID.")
            return

        try:
            self.logic.pick_player(player_id, team_num)
        except ValueError as e:
            QMessageBox.warning(self, "Selection Error", str(e))
            return

        # Update UI elements
        self.update_player_table()
        self.update_roster_display()
        self.update_other_rosters_display()
        self.update_position_recommendation()
        self.update_current_pick_label()
        self.update_positional_requirements_chart()
        self.update_top_three_recommendations()
        self.update_recommendations_pie_chart()

        # Auto-recommend next pick if it's the user's turn
        if team_num == self.logic.user_draft_position:
            self.auto_recommend_pick()

    def update_roster_display(self):
        """
        Update the display of the user's roster.
        """
        self.roster_list.clear()
        user_roster = self.logic.get_team_roster(self.logic.user_draft_position)
        for position, players in user_roster.items():
            players_str = ', '.join(players) if players else 'None'
            item = QListWidgetItem(f"{position}: {players_str}")
            self.roster_list.addItem(item)

    def update_other_rosters_display(self):
        """
        Update the display of other teams' rosters.
        """
        self.other_rosters_list.clear()
        all_rosters = self.logic.get_all_rosters()
        for team_num, roster in all_rosters.items():
            if team_num == self.logic.user_draft_position:
                continue  # Skip your own team
            roster_items = []
            for pos, players in roster.items():
                players_str = ', '.join(players) if players else 'None'
                roster_items.append(f"{pos}: {players_str}")
            roster_str = '; '.join(roster_items)
            item = QListWidgetItem(f"Team {team_num}: {roster_str}")
            self.other_rosters_list.addItem(item)

    def update_position_recommendation(self):
        """
        Update the next recommended position to draft.
        """
        recommendation = self.logic.get_position_recommendation()
        self.position_recommendation_label.setText(recommendation)

    def update_current_pick_label(self):
        """
        Update the label showing the current pick information.
        """
        pick_info = self.logic.get_current_pick_info()
        if pick_info[0]:
            pick_num, round_num, team_num = pick_info
            if team_num == self.logic.user_draft_position:
                pick_details = f"Pick #{pick_num} (Round {round_num}) - Your Pick"
                color = "#FFD700"  # Gold
            else:
                pick_details = f"Pick #{pick_num} (Round {round_num}) - Team {team_num}'s Pick"
                color = "#FFFFFF"  # White
            self.current_pick_label.setText(f"Current Pick: {pick_details}")
            self.current_pick_label.setStyleSheet(f"color: {color};")
        else:
            self.current_pick_label.setText("Draft Completed")
            self.current_pick_label.setStyleSheet("color: #FF0000;")  # Red

    def update_positional_requirements_chart(self):
        """
        Update the positional requirements chart based on needed positions and available players.
        """
        # Clear the previous plot
        self.ax.clear()

        # Calculate needed positions
        user_roster = self.logic.get_team_roster(self.logic.user_draft_position)
        needed_positions = self.logic.positions_needed(user_roster)

        # Count needed per position
        needed_counts = {pos: self.logic.roster_slots[pos] - len(user_roster[pos]) for pos in needed_positions}

        # Count available players per position
        available_counts = {}
        for pos in needed_positions:
            if pos == 'G':
                count = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: 'PG' in x or 'SG' in x)
                ].shape[0]
            elif pos == 'F':
                count = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: 'SF' in x or 'PF' in x)
                ].shape[0]
            else:
                count = self.logic.available_players[
                    self.logic.available_players['Position List'].apply(lambda x: pos in x)
                ].shape[0]
            available_counts[pos] = count

        positions_plot = list(needed_counts.keys())
        needed = list(needed_counts.values())
        available = [available_counts.get(pos, 0) for pos in positions_plot]

        x = range(len(positions_plot))
        self.ax.bar(x, needed, width=0.4, label='Needed', align='center', color='#FF6347')  # Tomato color
        self.ax.bar(x, available, width=0.4, bottom=needed, label='Available', align='center',
                    color='#4682B4')  # SteelBlue color

        self.ax.set_xticks(x)
        self.ax.set_xticklabels(positions_plot)
        self.ax.set_ylabel('Number of Players')
        self.ax.set_title('Positional Requirements vs Available Players')
        self.ax.legend()

        self.figure.tight_layout()
        self.canvas.draw()

    def update_top_three_recommendations(self):
        """
        Update the top three position recommendations list.
        """
        self.top_three_recommendations.clear()
        top_three = self.logic.generate_top_three_recommendations()
        if not top_three:
            item = QListWidgetItem("No positions needed.")
            self.top_three_recommendations.addItem(item)
            return

        for pos, score in top_three:
            item = QListWidgetItem(f"{pos} (Score: {score:.2f})")
            self.top_three_recommendations.addItem(item)

        # Update the pie chart after updating recommendations
        self.update_recommendations_pie_chart()

    def update_recommendations_pie_chart(self):
        """
        Update the pie chart based on the top three recommendations.
        """
        # Get top three recommendations
        top_three = self.logic.generate_top_three_recommendations()
        if not top_three:
            self.pie_ax.clear()
            self.pie_ax.text(0.5, 0.5, 'No Data', horizontalalignment='center', verticalalignment='center')
        else:
            positions_pie, scores_pie = self.logic.generate_recommendations_pie_data(top_three)
            self.pie_ax.clear()
            self.pie_ax.pie(scores_pie, labels=positions_pie, autopct='%1.1f%%', startangle=140)
            self.pie_ax.set_title('Top 3 Recommendations')
        self.pie_figure.tight_layout()
        self.pie_canvas.draw()

    def auto_recommend_pick(self):
        """
        Automatically recommend a pick to the user via a message box.
        """
        top_three = self.logic.generate_top_three_recommendations()
        if not top_three:
            QMessageBox.information(self, "Recommendation", "No recommendations available.")
            return
        recommendations = [f"{pos} (Score: {score:.2f})" for pos, score in top_three]
        rec_text = "\n".join(recommendations)
        QMessageBox.information(self, "Top 3 Recommendations",
                                f"Based on your team needs and player availability, consider drafting:\n\n{rec_text}")

    def update_best_projected_picks(self):
        """
        Update the Best Projected Picks list based on Combined Score and positional requirements.
        """
        self.best_picks_list.clear()
        user_roster = self.logic.get_team_roster(self.logic.user_draft_position)
        needed_positions = self.logic.positions_needed(user_roster)

        if not needed_positions:
            item = QListWidgetItem("No positions needed.")
            self.best_picks_list.addItem(item)
            return

        # Filter players who fit into any needed position
        def fits_needed(pos_list):
            return any(pos in pos_list for pos in needed_positions)

        best_picks = self.logic.available_players[
            self.logic.available_players['Position List'].apply(fits_needed)
        ].sort_values(by='Combined Score', ascending=False).head(10)  # Top 10 picks

        for _, player in best_picks.iterrows():
            player_info = (
                f"{player['Player']} | Team: {player['Team']} | Positions: {', '.join(player['Position List'])} | "
                f"Combined Score: {player['Combined Score']:.2f}"
            )
            item = QListWidgetItem(player_info)
            # Highlight the best pick
            if _ == best_picks.index[0]:
                item.setBackground(QBrush(QColor(255, 215, 0)))  # Gold color
            self.best_picks_list.addItem(item)

    def closeEvent(self, event):
        """
        Handle the event when the user attempts to close the application.
        """
        reply = QMessageBox.question(
            self, 'Quit', 'Do you want to save the draft before exiting?',
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.logic.save_draft_state()
            event.accept()
        elif reply == QMessageBox.No:
            event.accept()
        else:
            event.ignore()