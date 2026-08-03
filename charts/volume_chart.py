from charts.chart_widget import HistoryChart

class VolumeChart(HistoryChart):
    def __init__(self):
        super().__init__("Volume", "#42A5F5")
