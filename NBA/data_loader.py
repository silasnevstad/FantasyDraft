import pandas as pd
import os
from PyQt5.QtWidgets import QMessageBox


class DataLoader:
    def __init__(self, filepath='cleaned_players_data.csv'):
        """
        Initialize the DataLoader with the path to the player data CSV.
        """
        self.filepath = filepath
        self.data = None

    def load_data(self):
        """
        Load and preprocess the player data from the CSV file.
        """
        if not os.path.exists(self.filepath):
            QMessageBox.critical(None, "Error", f"The file '{self.filepath}' does not exist.")
            raise FileNotFoundError(f"The file '{self.filepath}' does not exist.")

        self.data = pd.read_csv(self.filepath)
        required_columns = {
            'Player', 'Team', 'Position List', 'Tier',
            'Adjusted VORP', 'Projected Fantasy Points',
            'Fantasy TOT', 'Fantasy AVG'
        }
        if not required_columns.issubset(set(self.data.columns)):
            missing = required_columns - set(self.data.columns)
            QMessageBox.critical(None, "Error", f"Missing columns in data: {', '.join(missing)}")
            raise ValueError(f"Missing columns in data: {', '.join(missing)}")

        # Assign unique PlayerID
        self.data.reset_index(inplace=True)
        self.data.rename(columns={'index': 'PlayerID'}, inplace=True)
        self.data['Position List'] = self.data['Position List'].apply(
            lambda x: eval(x) if isinstance(x, str) else x
        )
        self.data = self.data.sort_values(by='Adjusted VORP', ascending=False).reset_index(drop=True)
        return self.data
